from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient

from eventlens.core import now, timestamp
from eventlens.llm import LiveAdapter, NoProviderRedirect
from eventlens.macro.agent import run_brief
from eventlens.macro.demo import scripted_adapter
from eventlens.macro.records import load_sources
from eventlens.service.api import create_app
from eventlens.service.ingestion import Article, FED_FEED, check_fed_url, make_source, refresh_fed
from eventlens.service.settings import Settings
from eventlens.service.store import Conflict, Database, QueueFull
from eventlens.service.worker import Worker

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'test-token-never-use-for-deployment'
BODY = {'as_of': '2025-07-25T20:00:00Z', 'start_date': '2025-07-28', 'end_date': '2025-08-01',
        'method': 'rules', 'cutoff_mode': 'publication', 'markets':['US'], 'include_watchlist':False}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(Path(self.temp.name), TOKEN, 'test-model')
        self.db = Database(self.settings.database)
        _, self.sources = load_sources(ROOT/'data/macro/manifest.json')
        for source in self.sources.values():
            self.db.add_source(source, {'method': 'test-fixture'})
        self.client = TestClient(create_app(self.settings))
        self.addCleanup(self.client.close)
        self.client.headers['Authorization'] = 'Bearer '+TOKEN

    def submit(self, **changes):
        response = self.client.post('/v1/briefs', json={**BODY, **changes})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def test_authentication_and_openapi(self):
        for url in ['/v1/sources', '/v1/jobs', '/openapi.json', '/v1/status']:
            response = self.client.get(url, headers={'Authorization': 'Bearer wrong'})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get('/health/live').status_code, 200)
        schema = self.client.get('/openapi.json').json()
        self.assertIn('/v1/briefs', schema['paths'])
        self.assertEqual(schema['paths']['/v1/briefs']['post']['security'], [{'HTTPBearer': []}])

    def test_readiness_requires_worker(self):
        self.assertEqual(self.client.get('/health/ready').status_code, 503)
        self.db.heartbeat('healthy')
        self.assertEqual(self.client.get('/health/ready').status_code, 200)
        self.db.remove_worker('healthy')
        self.assertEqual(self.client.get('/health/ready').status_code, 503)

    def test_real_rules_job_and_append_only_review(self):
        job = self.submit()
        self.assertEqual(job['status'], 'queued')
        worker = Worker(self.settings)
        self.assertTrue(worker.tick())
        result = self.client.get('/v1/jobs/'+job['id']).json()
        self.assertEqual(result['status'], 'succeeded')
        run = result['result']['run']
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(run['execution_kind'], 'deterministic')
        self.assertEqual(len(run['calendar']), 1)
        self.assertIn('source_hashes', run)
        self.assertIn('service/worker.py', run['code_hashes'])
        self.assertIn('Macro-event brief', self.client.get('/v1/jobs/'+job['id']+'/brief').text)
        observation = result['result']['review_queue'][0]['observation_id']
        payload = dict(observation_id=observation, decision='supports', reviewer='Test analyst', note='Checked literal support.')
        url = '/v1/jobs/'+job['id']+'/reviews'
        self.assertEqual(self.client.post(url, json=payload).status_code, 201)
        self.assertEqual(self.client.post(url, json={**payload, 'decision': 'uncertain'}).status_code, 201)
        self.assertEqual(len(self.client.get(url).json()), 2)
        self.assertEqual(self.db.get(job['id'])['result'], result['result'])
        self.assertEqual(self.client.post(url, json={**payload, 'observation_id': 'a'*64}).status_code, 404)

    def test_agent_job_executes_tools_repairs_and_keeps_mock_label(self):
        with patch.dict('os.environ', {'EVENTLENS_API_KEY': 'fixture-key'}):
            job = self.submit(method='agent')
        request = job['request']
        sources = self.db.sources(request['source_ids'])
        worker = Worker(self.settings, adapter_factory=lambda model: scripted_adapter(sources, request['case'], repair=True))
        worker.tick()
        run = self.db.get(job['id'])['result']['run']
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(run['execution_kind'], 'mock')
        self.assertEqual([x['valid'] for x in run['trace'] if x['stage'] == 'draft_validation'], [False, True])

    def test_source_selection_excludes_future_before_model_access(self):
        job = self.submit()
        self.assertEqual(set(job['request']['source_ids']), {'fed-2025-06-minutes', 'fed-2025-06-statement'})
        job = self.submit(cutoff_mode='snapshot')
        self.assertEqual(job['request']['source_ids'], [])
        Worker(self.settings).tick()  # first job
        Worker(self.settings).tick()
        self.assertEqual(self.db.get(job['id'])['result']['run']['status'], 'insufficient_evidence')

    def test_model_config_is_required_and_cannot_be_submitted(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(self.client.post('/v1/briefs', json={**BODY, 'method': 'agent'}).status_code, 503)
        self.assertEqual(self.client.post('/v1/briefs', json={**BODY, 'model': 'override'}).status_code, 422)
        self.assertEqual(self.client.post('/v1/briefs', json={**BODY, 'source_ids': ['missing']}).status_code, 422)

    def test_model_job_replay_survives_configuration_change(self):
        headers = {'Idempotency-Key': 'model-retry'}
        body = {**BODY, 'method': 'agent'}
        with patch.dict('os.environ', {'EVENTLENS_API_KEY': 'test-key'}):
            original = self.client.post('/v1/briefs', json=body, headers=headers)
        with patch.dict('os.environ', {}, clear=True):
            repeated = self.client.post('/v1/briefs', json=body, headers=headers)
        self.assertEqual(repeated.status_code, 202)
        self.assertEqual(original.json()['id'], repeated.json()['id'])

    def test_empty_calendar_does_not_spend_model_calls(self):
        from eventlens.llm import MockAdapter
        case = json.loads((ROOT/'data/macro/cases.json').read_text())[0]
        run = run_brief({}, case, 'agent', self.settings.config, MockAdapter([]), 'snapshot')
        self.assertEqual(run['calls'], 0)
        self.assertEqual(run['status'], 'insufficient_evidence')

    def test_idempotency_survives_source_refresh_and_restart(self):
        headers = {'Idempotency-Key': 'request-001'}
        original = self.client.post('/v1/briefs', json=BODY, headers=headers).json()
        source = self.sources['fed-2025-06-minutes']
        self.db.add_source(replace(source, source_id='additional-copy'), {'method': 'fixture'})
        client = TestClient(create_app(self.settings), headers={'Authorization': 'Bearer '+TOKEN})
        self.addCleanup(client.close)
        repeated = client.post('/v1/briefs', json=BODY, headers=headers).json()
        self.assertEqual(original['id'], repeated['id'])
        self.assertEqual(original['request']['source_ids'], repeated['request']['source_ids'])
        changed = client.post('/v1/briefs', json={**BODY, 'end_date': '2025-08-02'}, headers=headers)
        self.assertEqual(changed.status_code, 409)

    def test_invalid_case_and_large_request(self):
        for changes in [{'end_date': '2027-01-01'}, {'as_of': '2025-07-25'}, {'start_date': 'bad'}]:
            self.assertEqual(self.client.post('/v1/briefs', json={**BODY, **changes}).status_code, 422)
        self.assertEqual(self.client.post('/v1/sources', content='x'*2_000_001).status_code, 413)
        response = self.client.post('/v1/briefs', json={**BODY, 'secret': 'do-not-echo'})
        self.assertNotIn('do-not-echo', response.text)

    def test_import_deduplicates_without_changing_retrieval_time(self):
        source = self.sources['fed-2025-06-statement']
        body = {k: v for k, v in asdict(source).items() if k not in {'source_id', 'retrieved_at', 'content_hash', 'markets'}}
        first = self.client.post('/v1/sources', json=body)
        self.assertEqual(first.status_code, 201)
        sid = first.json()['source_id']
        before = self.db.sources([sid])[sid].retrieved_at
        second = self.client.post('/v1/sources', json=body)
        self.assertFalse(second.json()['added'])
        self.assertEqual(before, self.db.sources([sid])[sid].retrieved_at)
        body['text'] += ' New version.'
        third = self.client.post('/v1/sources', json=body)
        self.assertNotEqual(sid, third.json()['source_id'])

    def test_failed_job_records_category_not_secret(self):
        with patch.dict('os.environ', {'EVENTLENS_API_KEY': 'fixture-key'}):
            job = self.submit(method='agent')
        def fail(model):
            raise RuntimeError('SECRET-EXCEPTION-CONTENT')
        Worker(self.settings, adapter_factory=fail).tick()
        result = self.db.get(job['id'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error'], 'execution_error_RuntimeError')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_concurrent_workers_claim_each_job_once(self):
        jobs = [self.db.submit('refresh', {'limit': i}) for i in range(1, 9)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            claimed = list(pool.map(lambda i: self.db.claim('worker-'+str(i)), range(8)))
        self.assertEqual({j['id'] for j in jobs}, {j['id'] for j in claimed})
        self.assertIsNone(self.db.claim('extra'))

    def test_concurrent_database_initialization(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'new.sqlite'
            with ThreadPoolExecutor(max_workers=8) as pool:
                databases = list(pool.map(lambda _: Database(path), range(8)))
            self.assertTrue(all(db.health()['sources'] == 0 for db in databases))

    def test_crash_does_not_replay_paid_calls(self):
        job = self.submit()
        self.db.claim('old-worker')
        with self.db.connect() as conn:
            conn.execute('UPDATE jobs SET heartbeat=? WHERE id=?', (time.time()-120, job['id']))
        self.assertIsNone(self.db.claim('new-worker'))
        self.assertEqual(self.db.get(job['id'])['error'], 'worker_interrupted')
        with self.assertRaises(Conflict):
            self.db.finish(job['id'], 'old-worker', {'late': True})

    def test_queue_capacity_and_source_identity(self):
        self.db.submit('refresh', {'limit': 1}, max_pending=1)
        with self.assertRaises(QueueFull):
            self.db.submit('refresh', {'limit': 2}, max_pending=1)
        original = self.sources['fed-2025-06-statement']
        with self.assertRaises(Conflict):
            self.db.add_source(replace(original, title='different'), {})
        with self.assertRaises(ValueError):
            Settings(Path(self.temp.name), 'short')


class IngestionTests(unittest.TestCase):
    def test_parser_keeps_paragraphs_and_excludes_navigation_and_scripts(self):
        parser = Article()
        parser.feed('<nav>Ignore navigation</nav><div id="article"><p>'+('Policy context. '*10)+
                    '<br/>More context.</p><script>injected code</script><p>Second paragraph.</p></div><footer>Ignore footer</footer>')
        text = parser.text()
        self.assertIn('Second paragraph.', text)
        self.assertIn('\n\n', text)
        for term in ['navigation', 'injected', 'footer']:
            self.assertNotIn(term, text)

    def test_fetch_scope_rejects_arbitrary_hosts_and_paths(self):
        for url in ['http://www.federalreserve.gov/feeds/press_monetary.xml',
                    'https://evil.example/feeds/press_monetary.xml',
                    'https://www.federalreserve.gov@127.0.0.1/feeds/press_monetary.xml',
                    'https://www.federalreserve.gov/feeds/press_monetary.xml?url=other',
                    'https://www.federalreserve.gov:444/feeds/press_monetary.xml']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                check_fed_url(url)
        check_fed_url(FED_FEED)

    def test_refresh_uses_release_date_not_meeting_date_and_retains_provenance(self):
        feed = '''<rss><channel><item><title>Minutes of the Federal Open Market Committee, June 17-18, 2025</title>
            <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20250709a.htm</link>
            <pubDate>Wed, 09 Jul 2025 18:00:00 GMT</pubDate></item></channel></rss>'''
        release = '<div id="article"><a href="/monetarypolicy/fomcminutes20250618.htm">Minutes</a></div>'
        minutes = '<div id="article"><p>It was agreed that the next meeting of the Committee would be held on Tuesday–Wednesday, July 29–30, 2025.</p></div>'
        def fetch(url):
            return feed if url == FED_FEED else minutes if '/fomcminutes' in url else release
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder)/'state.sqlite')
            result = refresh_fed(db, fetch=fetch)
            self.assertEqual(result['added'], 1)
            self.assertFalse(result['errors'])
            sid = result['source_ids'][0]
            source = db.sources([sid])[sid]
            self.assertEqual(source.document_date, '2025-06-18')
            self.assertEqual(source.published_at, '2025-07-09T18:00:00+00:00')
            self.assertEqual(len(db.source_details(sid)['provenance']['captures']), 2)
            self.assertEqual(refresh_fed(db, fetch=fetch)['unchanged'], 1)
            def broken(url):
                return feed if url == FED_FEED else '<html>Unexpected page</html>'
            self.assertEqual(len(refresh_fed(db, fetch=broken)['errors']), 1)

    def test_future_import_rejected(self):
        with self.assertRaisesRegex(ValueError, 'future'):
            make_source(title='Future', publisher='Source', url='https://example.com/data',
                        published_at=(timestamp(now())+timedelta(days=2)).isoformat(),
                        document_date='2025-01-01', kind='statement', text='Future statement '*20)


class ProviderTests(unittest.TestCase):
    def adapter(self, **kwargs):
        with patch.dict('os.environ', {'EVENTLENS_API_KEY': 'test-provider-key'}):
            return LiveAdapter('test-model', **kwargs)

    def test_transient_retry_is_bounded_and_traceable(self):
        adapter = self.adapter()
        response = BytesIO(b'{"choices": []}')
        error = HTTPError(adapter.base_url, 429, 'limited', {}, BytesIO(b'secret provider body'))
        with patch.object(adapter.opener, 'open', side_effect=[error, response]) as call, patch('eventlens.llm.time.sleep'):
            result = adapter.complete([], 100)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(len(result['_eventlens_transport']['attempts']), 2)
        self.assertNotIn('secret', json.dumps(result))

    def test_auth_error_is_not_retried_or_disclosed(self):
        adapter = self.adapter()
        error = HTTPError(adapter.base_url, 401, 'secret message', {}, BytesIO(b'secret body'))
        with patch.object(adapter.opener, 'open', side_effect=error) as call:
            with self.assertRaisesRegex(RuntimeError, 'provider_http_error_401; attempts=1'):
                adapter.complete([], 100)
        self.assertEqual(call.call_count, 1)

    def test_network_retry_limit(self):
        adapter = self.adapter()
        with patch.object(adapter.opener, 'open', side_effect=URLError('secret')) as call, patch('eventlens.llm.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'attempts=3'):
                adapter.complete([], 100)
        self.assertEqual(call.call_count, 3)

    def test_invalid_json_and_oversized_response(self):
        for body, message in [(b'<html>Bad gateway</html>', 'provider_invalid_json'), (b'x'*4_000_001, 'too_large')]:
            adapter = self.adapter()
            with patch.object(adapter.opener, 'open', return_value=BytesIO(body)):
                with self.assertRaisesRegex(RuntimeError, message):
                    adapter.complete([], 100)

    def test_redirects_and_insecure_endpoints_rejected(self):
        with self.assertRaises(RuntimeError):
            NoProviderRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example')
        with self.assertRaises(ValueError):
            self.adapter(base_url='http://127.0.0.1:8080/v1')
        with patch.dict('os.environ', {'EVENTLENS_ALLOW_LOCAL_HTTP': '1'}):
            self.adapter(base_url='http://127.0.0.1:8080/v1')
            with self.assertRaises(ValueError):
                self.adapter(base_url='http://example.com/v1')


if __name__ == '__main__':
    unittest.main()
