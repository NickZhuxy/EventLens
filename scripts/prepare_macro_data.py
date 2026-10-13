#!/usr/bin/env python3
"""Normalize saved Federal Reserve web-reader captures. No network access.

The raw captures are reader output, not original HTTP bytes. The manifest records
the selected body range, both hashes, and independent minutes-release evidence.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'data/macro'
SOURCES = [
    ('fed-2025-06-statement', 'June 2025 FOMC statement', '2025-06-18', '2025-06-18', 'statement', 8, 19),
    ('fed-2025-06-minutes', 'June 2025 FOMC minutes', '2025-07-09', '2025-06-18', 'minutes', 8, 143),
    ('fed-2025-07-statement', 'July 2025 FOMC statement', '2025-07-30', '2025-07-30', 'statement', 8, 19),
    ('fed-2025-07-minutes', 'July 2025 FOMC minutes', '2025-08-20', '2025-07-30', 'minutes', 8, 147),
    ('fed-2025-09-statement', 'September 2025 FOMC statement', '2025-09-17', '2025-09-17', 'statement', 8, 19),
]

def digest(value):
    return sha256(value.encode()).hexdigest()

def normalize(capture, first, last):
    # A second overlapping capture completes the long minutes. Later lines win.
    lines = {}
    for match in re.finditer(r'L(\d+):\s?(.*?)(?=L\d+:|\Z)', capture, re.S):
        number = int(match[1])
        if first <= number <= last:
            value = re.sub(r'cite[^†]*†(.*?)', r'\1', match[2])
            value = re.sub(r'[^]*', '', value)
            value = re.sub(r'^\s*(?:>\s*|#+\s*)', '', value)
            lines[number] = re.sub(r'\s+', ' ', value).strip()
    missing = set(range(first, last + 1)) - lines.keys()
    if missing:
        raise ValueError(f'missing captured lines: {sorted(missing)}')
    return '\n'.join(lines[i] for i in range(first, last + 1) if lines[i]) + '\n'

def main():
    manifest_path = ROOT / 'manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    retrieved = old.get('captured_at', datetime.now(timezone.utc).isoformat())
    manifest = {'schema_version': 1, 'captured_at': retrieved,
                'snapshot_kind': 'normalized_web_reader_text',
                'limitation': 'Retrieved in 2026. Publication-time replay is not proof of a 2025 point-in-time archive. Original HTTP bytes are unavailable.',
                'sources': []}
    (ROOT / 'snapshots').mkdir(exist_ok=True)
    for sid, title, published, document_date, kind, first, last in SOURCES:
        capture_path = ROOT / 'captures' / (sid + '.web.txt')
        capture = capture_path.read_text()
        url = capture.splitlines()[0].rsplit('(', 1)[1].rstrip(')')
        content = normalize(capture, first, last)
        (ROOT / 'snapshots' / (sid + '.txt')).write_text(content)
        record = dict(source_id=sid, title=title, publisher='Federal Reserve Board', url=url,
                      published_at=published+'T18:00:00Z', available_at=published+'T18:00:00Z',
                      retrieved_at=retrieved, document_date=document_date, kind=kind,
                      markets=['US'], topics=['monetary_policy'], content_hash=digest(content),
                      path='snapshots/'+sid+'.txt', capture_path='captures/'+sid+'.web.txt',
                      capture_hash=digest(capture), capture_lines=[first, last])
        if kind == 'minutes':
            release_id = 'release-june-minutes' if '06-minutes' in sid else 'release-july-minutes'
            release = (ROOT/'captures'/f'{release_id}.web.txt').read_text()
            record['release_evidence'] = {'path':f'captures/{release_id}.web.txt', 'hash':digest(release),
                                        'url': release.splitlines()[0].rsplit('(', 1)[1].rstrip(')')}
        manifest['sources'].append(record)
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'sources':len(manifest['sources']), 'manifest':str(manifest_path)}))

if __name__ == '__main__':
    main()
