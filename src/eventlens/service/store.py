"""Atomic SQLite jobs and source versions. No work is kept only in API memory."""
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from ..core import canonical, digest, now
from ..macro.records import MacroSource


class Conflict(ValueError):
    pass


class QueueFull(ValueError):
    pass


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            # SQLite can report SQLITE_BUSY immediately while two new connections
            # both change journal mode, despite the normal busy timeout.
            for attempt in range(100):
                try:
                    db.execute('PRAGMA journal_mode=WAL')
                    break
                except sqlite3.OperationalError as exc:
                    if 'locked' not in str(exc) or attempt == 99:
                        raise
                    time.sleep(0.05)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES (1);
                CREATE TABLE IF NOT EXISTS source_versions (
                    id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, document TEXT NOT NULL,
                    provenance TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, request TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE, request_hash TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    owner TEXT, heartbeat REAL, result TEXT, error TEXT);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, heartbeat REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                    observation_id TEXT NOT NULL, decision TEXT NOT NULL, reviewer TEXT NOT NULL,
                    note TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
            if db.execute('SELECT MAX(version) FROM schema_version').fetchone()[0] != 1:
                raise ValueError('unsupported service database schema')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_source(self, source, provenance):
        encoded = canonical(asdict(source))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT document FROM source_versions WHERE id=?', (source.source_id,)).fetchone()
            if old:
                # First retrieval time is preserved when the same version is fetched again.
                previous, current = json.loads(old[0]), json.loads(encoded)
                for value in (previous, current):
                    value.pop('retrieved_at')
                if previous != current:
                    raise Conflict('source ID already belongs to a different source version')
                return False
            db.execute('INSERT INTO source_versions VALUES (?,?,?,?,?)',
                       (source.source_id, source.content_hash, encoded, canonical(provenance), now()))
            return True

    def sources(self, ids=None):
        with self.connect() as db:
            if ids is None:
                rows = db.execute('SELECT document FROM source_versions ORDER BY created_at,id').fetchall()
            else:
                rows = [db.execute('SELECT document FROM source_versions WHERE id=?', (sid,)).fetchone() for sid in ids]
                if any(row is None for row in rows):
                    raise ValueError('unknown source ID')
        result = [MacroSource(**json.loads(row[0])) for row in rows]
        return {s.source_id: s for s in result}

    def source_details(self, sid):
        with self.connect() as db:
            row = db.execute('SELECT document,provenance FROM source_versions WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise KeyError(sid)
        return {'source': json.loads(row[0]), 'provenance': json.loads(row[1])}

    @staticmethod
    def decode(row):
        if row is None:
            raise KeyError('job not found')
        value = dict(row)
        for key in ('request', 'result'):
            value[key] = json.loads(value[key]) if value[key] else None
        value.pop('owner')
        value.pop('heartbeat')
        value.pop('request_hash')
        return value

    def submit(self, kind, request, key=None, max_pending=50, identity=None):
        fingerprint = digest(canonical({'kind': kind, 'request': request if identity is None else identity}))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if key:
                previous = db.execute('SELECT * FROM jobs WHERE idempotency_key=?', (key,)).fetchone()
                if previous:
                    if previous['request_hash'] != fingerprint:
                        raise Conflict('idempotency key already used for a different request')
                    return self.decode(previous)
            pending = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            if pending >= max_pending:
                raise QueueFull('job queue is full')
            job_id, created = str(uuid4()), now()
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (job_id, kind, canonical(request), key, fingerprint, 'queued', created, created,
                        None, None, None, None))
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def get(self, job_id):
        with self.connect() as db:
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def replay(self, kind, identity, key):
        if not key:
            return None
        fingerprint = digest(canonical({'kind': kind, 'request': identity}))
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE idempotency_key=?', (key,)).fetchone()
        if row is None:
            return None
        if row['request_hash'] != fingerprint:
            raise Conflict('idempotency key already used for a different request')
        return self.decode(row)

    def jobs(self, limit=50):
        with self.connect() as db:
            rows = db.execute('SELECT id,kind,status,created_at,updated_at,error FROM jobs '
                              'ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return [dict(row) for row in rows]

    def claim(self, owner, lease_seconds=60):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Do not silently repeat a model request after a crash: it may have incurred a charge.
            db.execute("UPDATE jobs SET status='failed',error='worker_interrupted',updated_at=? "
                       "WHERE status='running' AND heartbeat < ?", (now(), time.time()-lease_seconds))
            row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running',owner=?,heartbeat=?,updated_at=? WHERE id=?",
                       (owner, time.time(), now(), row[0]))
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (row[0],)).fetchone())

    def heartbeat(self, owner):
        with self.connect() as db:
            db.execute('INSERT INTO workers VALUES (?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat',
                       (owner, time.time()))
            db.execute("UPDATE jobs SET heartbeat=? WHERE owner=? AND status='running'", (time.time(), owner))
            db.execute('DELETE FROM workers WHERE heartbeat < ?', (time.time()-86400,))

    def remove_worker(self, owner):
        with self.connect() as db:
            db.execute('DELETE FROM workers WHERE id=?', (owner,))

    def finish(self, job_id, owner, result=None, error=None):
        with self.connect() as db:
            cursor = db.execute("UPDATE jobs SET status=?,result=?,error=?,updated_at=? "
                                "WHERE id=? AND owner=? AND status='running'",
                                ('failed' if error else 'succeeded', canonical(result) if result is not None else None,
                                 error, now(), job_id, owner))
            if cursor.rowcount != 1:
                raise Conflict('worker no longer owns this job')

    def health(self):
        with self.connect() as db:
            counts = {row[0]: row[1] for row in db.execute('SELECT status,count(*) FROM jobs GROUP BY status')}
            return {'sources': db.execute('SELECT count(*) FROM source_versions').fetchone()[0],
                    'workers': db.execute('SELECT count(*) FROM workers WHERE heartbeat >= ?', (time.time()-30,)).fetchone()[0],
                    'jobs': counts}

    def review(self, job_id, observation_id, decision, reviewer, note):
        job = self.get(job_id)
        queue = (job['result'] or {}).get('review_queue', [])
        if not any(row['observation_id'] == observation_id for row in queue):
            raise KeyError('observation not in this job')
        value = dict(id=str(uuid4()), job_id=job_id, observation_id=observation_id,
                     decision=decision, reviewer=reviewer, note=note, created_at=now())
        with self.connect() as db:
            db.execute('INSERT INTO reviews VALUES (?,?,?,?,?,?,?)', tuple(value.values()))
        return value

    def reviews(self, job_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM reviews WHERE job_id=? ORDER BY created_at', (job_id,))]
