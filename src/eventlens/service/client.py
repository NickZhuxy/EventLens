"""Small authenticated client for the deployed service; no model credentials needed."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener
from uuid import uuid4
from zoneinfo import ZoneInfo

from ..llm import NoProviderRedirect


class Client:
    def __init__(self, url, token):
        parsed = urlparse(url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or (parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('service URL must use HTTPS, or HTTP on the local loopback interface')
        if not token:
            raise ValueError('set EVENTLENS_SERVICE_TOKEN')
        self.url, self.token = url.rstrip('/'), token
        self.opener = build_opener(NoProviderRedirect())

    def request(self, path, body=None, key=None):
        headers = {'Authorization': 'Bearer '+self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if key:
            headers['Idempotency-Key'] = key
        request = Request(self.url+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise RuntimeError(f'service_http_error_{status}; check server configuration and request fields') from None

    def wait(self, job, timeout=1800):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            job = self.request('/v1/jobs/'+job['id'])
            if job['status'] in {'succeeded', 'failed'}:
                return job
            time.sleep(1)
        raise RuntimeError('job wait timed out; the server continues processing the saved job')


def request_brief(args):
    destination = args.out.resolve()
    if destination.exists():
        raise ValueError('use a new output directory')
    if not 1 <= args.days <= 32:
        raise ValueError('days must be 1..32')
    client = Client(args.url, os.getenv('EVENTLENS_SERVICE_TOKEN'))
    refresh = None
    if args.refresh:
        refresh = client.wait(client.request('/v1/refresh', {'limit': 8}))
        if refresh['status'] != 'succeeded':
            raise RuntimeError('source refresh failed; inspect job '+refresh['id'])
    cutoff = datetime.now(timezone.utc)
    start = cutoff.astimezone(ZoneInfo('America/New_York')).date()
    body = {'as_of': cutoff.isoformat(), 'start_date': start.isoformat(),
            'end_date': (start+timedelta(days=args.days-1)).isoformat(),
            'cutoff_mode': 'snapshot', 'method': args.method, 'markets': getattr(args, 'markets', ['GLOBAL'])}
    if refresh:
        body['refresh_job_id'] = refresh['id']
        if (refresh.get('result') or {}).get('errors'):
            print(json.dumps({'refresh_job':refresh['id'], 'collection_errors':refresh['result']['errors']}), flush=True)
    job = client.request('/v1/briefs', body, str(uuid4()))
    destination.mkdir(parents=True)
    if refresh:
        (destination/'refresh.json').write_text(json.dumps(refresh, indent=2)+'\n')
    (destination/'job.json').write_text(json.dumps(job, indent=2)+'\n')
    print(json.dumps({'job_id': job['id'], 'status': job['status']}), flush=True)
    job = client.wait(job)
    (destination/'job.json').write_text(json.dumps(job, indent=2)+'\n')
    result = job['result'] or {}
    for field, filename in [('run', 'run.json'), ('review_queue', 'review_queue.json')]:
        if field in result:
            (destination/filename).write_text(json.dumps(result[field], indent=2)+'\n')
    if 'calendar_csv' in result:
        (destination/'calendar.csv').write_text(result['calendar_csv'], encoding='utf-8-sig')
    if 'brief_markdown' in result:
        (destination/'brief.md').write_text(result['brief_markdown'])
    print(json.dumps({'job_id': job['id'], 'status': job['status'], 'run_status': result.get('run', {}).get('status'),
                      'output': str(destination)}))
    return 1 if job['status'] == 'failed' else 0
