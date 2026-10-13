"""Provider protocol and service integration tests; no real model calls or keys."""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from eventlens.llm import LiveAdapter, ProviderSettings
from eventlens.macro.demo import scripted_adapter
from eventlens.macro.records import load_sources
from eventlens.service.api import create_app
from eventlens.service.settings import Settings
from eventlens.service.store import Database
from eventlens.service.worker import Worker

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://api.deepseek.com'
TOKEN = 'fixture-service-token-not-a-real-secret'
ENV = {'DEEPSEEK_API_KEY': 'fixture-deepseek-key', 'OPENAI_API_KEY': 'fixture-openai-key'}
BODY = {'as_of': '2025-07-25T20:00:00Z', 'start_date': '2025-07-28', 'end_date': '2025-08-01',
        'method': 'agent', 'cutoff_mode': 'publication', 'markets': ['US'], 'include_watchlist': False}


class DeepSeekTests(unittest.TestCase):
    def test_provider_keys_are_scoped_to_exact_https_host(self):
        cases = [(ENDPOINT, 'fixture-deepseek-key'), ('https://api.openai.com/v1', 'fixture-openai-key'),
                 ('https://api.deepseek.com.evil.example', None), ('https://proxy.example/v1', None),
                 ('https://api.deepseek.com:8443', None)]
        with patch.dict('os.environ', ENV, clear=True):
            for endpoint, expected in cases:
                with self.subTest(endpoint=endpoint):
                    self.assertEqual(ProviderSettings(endpoint).credential(), expected)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'must-not-reach-deepseek'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'No API key'):
                LiveAdapter('deepseek-flash', ENDPOINT)
        with patch.dict('os.environ', {**ENV, 'EVENTLENS_API_KEY': 'explicit-key'}, clear=True):
            self.assertEqual(ProviderSettings(ENDPOINT).credential(), 'explicit-key')

    def test_deepseek_json_request_and_reasoning_controls(self):
        messages = [{'role': 'user', 'content': 'Return a JSON research action.'}]
        raw = {'choices': [{'message': {'content': '{"action":"finish"}',
                                      'reasoning_content': 'Provider reasoning field.'}, 'finish_reason': 'stop'}],
               'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'total_tokens': 50}}
        for effort in [None, 'none', 'low', 'high', 'max']:
            with self.subTest(effort=effort), patch.dict('os.environ', ENV, clear=True):
                adapter = LiveAdapter('deepseek-flash', ENDPOINT, reasoning_effort=effort)
                with patch.object(adapter.opener, 'open', return_value=BytesIO(json.dumps(raw).encode())) as call:
                    result = adapter.complete(messages, 6000)
                req = call.call_args.args[0]
                body = json.loads(req.data)
                self.assertEqual(req.full_url, ENDPOINT+'/chat/completions')
                self.assertEqual(req.get_header('Authorization'), 'Bearer fixture-deepseek-key')
                self.assertEqual(body['messages'], messages)
                self.assertEqual(body['max_tokens'], 6000)
                self.assertEqual(body['response_format'], {'type': 'json_object'})
                self.assertEqual(body['thinking']['type'], 'disabled' if effort == 'none' else 'enabled')
                self.assertEqual(body.get('reasoning_effort'), None if effort == 'none' else effort or 'low')
                self.assertNotIn('store', body)
                self.assertNotIn('max_completion_tokens', body)
                self.assertNotIn('tools', body)  # EventLens uses JSON actions, not native tool calls.
                self.assertEqual(result['usage'], raw['usage'])
                self.assertEqual(result['choices'], raw['choices'])
                self.assertEqual(result['_eventlens_transport']['provider'], 'deepseek')
                self.assertNotIn('fixture-deepseek-key', json.dumps(result))

    def test_openai_payload_remains_compatible(self):
        with patch.dict('os.environ', ENV, clear=True):
            adapter = LiveAdapter('test-model', 'https://api.openai.com/v1')
            with patch.object(adapter.opener, 'open', return_value=BytesIO(b'{}')) as call:
                adapter.complete([], 500)
        body = json.loads(call.call_args.args[0].data)
        self.assertEqual(body['max_completion_tokens'], 500)
        self.assertFalse(body['store'])
        self.assertNotIn('thinking', body)
        self.assertNotIn('max_tokens', body)

    def test_invalid_settings_fail_before_network_access(self):
        for endpoint in ['http://api.deepseek.com', 'https://key@api.deepseek.com',
                         ENDPOINT+'?key=secret', ENDPOINT+'#fragment']:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                ProviderSettings(endpoint)
        with self.assertRaisesRegex(ValueError, 'reasoning effort'):
            ProviderSettings(ENDPOINT, 'typo')
        with self.assertRaisesRegex(ValueError, 'only for DeepSeek'):
            ProviderSettings('https://api.openai.com/v1', 'low')


class DeepSeekServiceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.settings = Settings(Path(folder.name), TOKEN, 'deepseek-flash', provider=ProviderSettings(ENDPOINT))
        self.db = Database(self.settings.database)
        _, sources = load_sources(ROOT/'data/macro/manifest.json')
        for source in sources.values():
            self.db.add_source(source, {'method': 'public-test-fixture'})
        self.client = TestClient(create_app(self.settings), headers={'Authorization': 'Bearer '+TOKEN})
        self.addCleanup(self.client.close)

    def test_status_and_admission_use_selected_provider_key(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'wrong-provider'}, clear=True):
            self.assertFalse(self.client.get('/v1/status').json()['model_configured'])
            self.assertEqual(self.client.post('/v1/briefs', json=BODY).status_code, 503)
        with patch.dict('os.environ', ENV, clear=True):
            status = self.client.get('/v1/status').json()
            self.assertTrue(status['model_configured'])
            self.assertEqual(status['provider'], 'deepseek')
            self.assertNotIn('fixture-deepseek-key', json.dumps(status))
            self.assertEqual(self.client.post('/v1/briefs', json={**BODY, 'provider_config': {}}).status_code, 422)

    def test_worker_uses_frozen_settings_through_retrieval_and_repair(self):
        with patch.dict('os.environ', ENV, clear=True):
            job = self.client.post('/v1/briefs', json=BODY).json()
            request = job['request']
            self.assertEqual(request['provider_config'], {'base_url': ENDPOINT, 'reasoning_effort': 'low'})
            scripted = scripted_adapter(self.db.sources(request['source_ids']), request['case'], repair=True)
            requests = []

            def respond(req, timeout):
                payload = json.loads(req.data)
                requests.append(payload)
                response = scripted.complete(payload['messages'], payload['max_tokens'])
                response['model'] = 'deepseek-flash'
                response['choices'][0]['message']['reasoning_content'] = 'Fixture reasoning.'
                return BytesIO(json.dumps(response).encode())

            opener = Mock()
            opener.open.side_effect = respond
            # New defaults do not alter an already queued job's reasoning setting.
            settings = replace(self.settings, provider=ProviderSettings(ENDPOINT, 'high'))
            with patch('eventlens.llm.build_opener', return_value=opener):
                Worker(settings).tick()
        result = self.db.get(job['id'])
        self.assertEqual(result['status'], 'succeeded')
        run = result['result']['run']
        self.assertEqual([x['valid'] for x in run['trace'] if x['stage'] == 'draft_validation'], [False, True])
        self.assertGreater(run['tool_calls'], 0)
        self.assertTrue(all(r['reasoning_effort'] == 'low' for r in requests))
        self.assertTrue(all('reasoning_content' not in m for r in requests for m in r['messages']))
        self.assertEqual(run['provider_config'], request['provider_config'])
        self.assertNotIn('fixture-deepseek-key', json.dumps(result))

    def test_changed_worker_endpoint_rejects_queued_model_job(self):
        with patch.dict('os.environ', ENV, clear=True):
            job = self.client.post('/v1/briefs', json=BODY).json()
            changed = replace(self.settings, provider=ProviderSettings('https://api.openai.com/v1'))
            with patch('eventlens.service.worker.LiveAdapter') as adapter:
                Worker(changed).tick()
            adapter.assert_not_called()
        self.assertEqual(self.db.get(job['id'])['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
