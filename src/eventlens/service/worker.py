"""Worker process with leases, graceful shutdown, and structured operational logs."""
import json
import logging
from pathlib import Path
import signal
import threading
from uuid import uuid4

from ..core import digest
from ..llm import LiveAdapter
from ..macro.agent import run_brief
from ..macro.report import render_brief, review_queue, render_calendar_csv
from .providers import refresh_calendars
from .settings import Settings
from .store import Database

logger = logging.getLogger('eventlens.worker')


class InterruptibleAdapter:
    def __init__(self, adapter, stop):
        self.adapter, self.stop = adapter, stop
        self.kind, self.model = adapter.kind, adapter.model

    def complete(self, messages, max_output_tokens):
        if self.stop.is_set():
            raise RuntimeError('worker_shutdown')
        return self.adapter.complete(messages, max_output_tokens)


class Worker:
    def __init__(self, settings, adapter_factory=None):
        self.settings = settings
        self.database = Database(settings.database)
        self.adapter_factory = adapter_factory
        self.owner = str(uuid4())
        self.stop = threading.Event()

    def tick(self):
        db = self.database
        db.heartbeat(self.owner)
        job = db.claim(self.owner)
        if job is None:
            return False
        logger.info(json.dumps({'event': 'job_started', 'job_id': job['id'], 'kind': job['kind']}))
        try:
            request = job['request']
            error = None
            if job['kind'] == 'refresh':
                result = refresh_calendars(db, request.get('providers', ['fed']), request['limit'])
                if result['errors'] and not result['source_ids']:
                    error = 'source_refresh_incomplete'
            elif job['kind'] == 'brief':
                sources = db.sources(request['source_ids'])
                provider_config = request.get('provider_config', self.settings.provider.to_dict())
                adapter = None
                if request['method'] != 'rules':
                    if self.adapter_factory:
                        adapter = self.adapter_factory(request['config']['model'])
                    else:
                        # A changed endpoint can imply a different credential in the environment.
                        if provider_config['base_url'] != self.settings.provider.base_url:
                            raise ValueError('queued_provider_endpoint_changed')
                        adapter = LiveAdapter(request['config']['model'], **provider_config)
                    adapter = InterruptibleAdapter(adapter, self.stop)
                run = run_brief(sources, request['case'], request['method'], request['config'], adapter, request['cutoff_mode'], request.get('include_watchlist'))
                if adapter is not None:
                    run['provider_config'] = provider_config
                run['collection_report'] = request.get('collection_report', {})
                package = Path(__file__).parents[1]
                run['code_hashes'] = {str(p.relative_to(package)): digest(p.read_bytes()) for p in sorted(package.rglob('*.py'))}
                result = {'run': run, 'brief_markdown': render_brief(run, sources),
                          'review_queue': review_queue(run, sources), 'calendar_csv': render_calendar_csv(run, sources)}
                if run['status'] == 'failed':
                    error = 'research_failed'
            else:
                raise ValueError('unknown job kind')
            db.finish(job['id'], self.owner, result, error)
        except Exception as exc:
            # Exception bodies can contain provider response text or secrets. Store a category only.
            error = 'execution_error_' + type(exc).__name__
            db.finish(job['id'], self.owner, error=error)
        logger.info(json.dumps({'event': 'job_finished', 'job_id': job['id'], 'error': error}))
        return True

    def run(self, once=False):
        heartbeat_stop = threading.Event()

        def pulse():
            while not heartbeat_stop.is_set():
                try:
                    self.database.heartbeat(self.owner)
                except Exception:
                    logger.error(json.dumps({'event': 'heartbeat_failed'}))
                    self.stop.set()
                    return
                heartbeat_stop.wait(5)

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        try:
            while not self.stop.is_set():
                worked = self.tick()
                if once:
                    break
                if not worked:
                    self.stop.wait(1)
        finally:
            heartbeat_stop.set()
            thread.join(timeout=10)
            self.database.remove_worker(self.owner)


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    worker = Worker(Settings.from_env())
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: worker.stop.set())
    worker.run()


if __name__ == '__main__':
    main()
