#!/usr/bin/env python3
"""Exercise a real HTTP server and worker; optionally use live sources and a model."""
import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='Use a running service instead of temporary local processes')
    parser.add_argument('--refresh', action='store_true', help='Refresh official multi-market sources instead of saved fixtures')
    parser.add_argument('--live', action='store_true', help='Use the configured real LLM instead of rules')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    children = []
    token = os.getenv('EVENTLENS_SERVICE_TOKEN') if args.url else secrets.token_urlsafe(32)
    if not token:
        parser.error('EVENTLENS_SERVICE_TOKEN is required for --url')
    report = {'test': 'service-http-acceptance', 'created_at': datetime.now(timezone.utc).isoformat(),
              'model_execution': 'live' if args.live else 'deterministic',
              'source_input': 'live-official-calendars' if args.refresh else 'saved-public-fixtures', 'success': False}
    with tempfile.TemporaryDirectory(prefix='eventlens-smoke-') as folder:
        log = open(Path(folder)/'process.log', 'w+')
        try:
            if args.url:
                url = args.url.rstrip('/')
            else:
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
                url = f'http://127.0.0.1:{port}'
                env = {**os.environ, 'EVENTLENS_STATE_DIR': folder, 'EVENTLENS_SERVICE_TOKEN': token}
                for command in [['serve', '--port', str(port)], ['worker']]:
                    children.append(subprocess.Popen([sys.executable, '-m', 'eventlens.service.cli', *command],
                                                     env=env, stdout=log, stderr=log))
            def request(path, body=None, key=None):
                headers = {'Authorization': 'Bearer '+token}
                if body is not None:
                    headers['Content-Type'] = 'application/json'
                if key:
                    headers['Idempotency-Key'] = key
                req = Request(url+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
                with urlopen(req, timeout=20) as response:
                    content = response.read().decode()
                    return json.loads(content) if response.headers.get_content_type() == 'application/json' else content
            def wait_job(job):
                deadline = time.monotonic()+1200
                while time.monotonic() < deadline:
                    current = request('/v1/jobs/'+job['id'])
                    if current['status'] in {'succeeded', 'failed'}:
                        return current
                    time.sleep(0.25)
                raise RuntimeError('job timeout')
            for _ in range(100):
                try:
                    request('/health/ready')
                    break
                except (OSError, HTTPError):
                    time.sleep(0.1)
            else:
                raise RuntimeError('service did not become ready')
            try:
                urlopen(url+'/v1/jobs', timeout=10)
                raise AssertionError('unauthenticated request was allowed')
            except HTTPError as error:
                assert error.code == 401
            assert '/v1/briefs' in request('/openapi.json')['paths']
            if args.refresh:
                refresh = wait_job(request('/v1/refresh', {'limit': 4}))
                assert refresh['status'] == 'succeeded', refresh.get('error')
                source_ids = refresh['result']['source_ids']
                report['refresh'] = {k: v for k, v in refresh['result'].items() if k != 'source_ids'}
                as_of = datetime.now(timezone.utc)
                start = as_of.astimezone(ZoneInfo('America/New_York')).date()
                body = {'as_of': as_of.isoformat(), 'start_date': start.isoformat(),
                        'end_date': (start+timedelta(days=31)).isoformat(), 'cutoff_mode': 'snapshot',
                        'refresh_job_id': refresh['id']}
            else:
                from eventlens.macro.records import load_sources
                _, sources = load_sources(ROOT/'data/macro/manifest.json')
                source_ids = []
                for source in sources.values():
                    data = {k: v for k, v in asdict(source).items() if k not in {'source_id', 'content_hash', 'retrieved_at', 'markets'}}
                    source_ids.append(request('/v1/sources', data)['source_id'])
                body = {'as_of': '2025-07-25T20:00:00Z', 'start_date': '2025-07-28',
                        'end_date': '2025-08-01', 'cutoff_mode': 'publication', 'markets':['US'], 'include_watchlist':False}
            body.update(source_ids=source_ids, method='agent' if args.live else 'rules')
            key = 'smoke-'+secrets.token_hex(12)
            job = request('/v1/briefs', body, key)
            assert request('/v1/briefs', body, key)['id'] == job['id']
            job = wait_job(job)
            assert job['status'] == 'succeeded', job.get('error')
            result = job['result']; run = result['run']
            assert run['status'] in {'ready_for_review', 'partial'}, run['status']
            assert run['validation']['valid'] and len(run['calendar']) >= 1
            assert run['execution_kind'] == ('live' if args.live else 'deterministic')
            assert 'Macro-event brief' in request('/v1/jobs/'+job['id']+'/brief')
            assert 'Historical impact' in request('/v1/jobs/'+job['id']+'/calendar.csv')
            if args.refresh:
                verified = [e for e in run['calendar'] if e.get('date_status') != 'watchlist']
                assert len({e.get('family_id', 'fomc') for e in verified}) >= 3, 'multi-provider coverage missing'
            queue = result['review_queue']; assert queue
            decision = request('/v1/jobs/'+job['id']+'/reviews', {
                'observation_id': queue[0]['observation_id'], 'decision': 'uncertain',
                'reviewer': 'automated-service-smoke', 'note': 'API persistence check only; no semantic approval.'})
            assert decision['decision'] == 'uncertain'
            assert request('/v1/jobs/'+job['id']+'/reviews')[0]['id'] == decision['id']
            report.update(success=True, job_id=job['id'], run_status=run['status'], source_count=len(source_ids),
                          model=run['model'], provider_config=run.get('provider_config'),
                          response_models=sorted({t['raw_response']['model'] for t in run['trace']
                                                  if 'raw_response' in t and 'model' in t['raw_response']}),
                          events=[{'id': e['event_id'], 'start': e['start_date'], 'end': e['end_date']} for e in run['calendar']],
                          model_calls=run['calls'], tool_calls=run['tool_calls'], tokens=run['tokens'],
                          checks=['authentication', 'OpenAPI', 'source ingestion', 'durable job execution',
                                  'idempotency', 'evidence validation', 'brief download', 'review persistence'])
        except Exception:
            log.flush()
            log.seek(0)
            print(log.read(), file=sys.stderr)
            raise
        finally:
            for child in children:
                child.terminate()
            for child in children:
                try:
                    child.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()
            log.close()
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
