"""Atomic native batches, budget boundaries and regression against saved failures."""
from copy import deepcopy
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

from eventlens.benchmark import RecordedAdapter, stable
from eventlens.protocol_v4 import run_native
import test_protocol_v3 as fixtures
from test_protocol_v3 import FixtureAdapter, native, finish

ROOT = Path(__file__).resolve().parents[1]


def batch(*responses):
    result = deepcopy(responses[0])
    result['choices'][0]['message']['tool_calls'] = [c for r in responses
        for c in r['choices'][0]['message']['tool_calls']]
    return result


class ProtocolV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ProtocolV3Tests.setUpClass()
        cls.sources, cls.case, cls.config = fixtures.ProtocolV3Tests.sources, fixtures.ProtocolV3Tests.case, fixtures.ProtocolV3Tests.config

    def reads(self):
        return [native('get_source', {'source_id': self.case[k], 'start': 0, 'end': 100}, k)
                for k in ('old', 'new')]

    def execute(self, replies, config=None):
        adapter = FixtureAdapter(replies)
        return run_native(self.sources, self.case, 'C', config or self.config, adapter), adapter

    def test_two_reads_share_one_model_call_and_replay_exactly(self):
        run, adapter = self.execute([batch(*self.reads()), native('finish', finish(), 'done')])
        self.assertFalse(run['errors'])
        self.assertFalse(run['validation_failures'])
        self.assertEqual(run['calls'], 2)
        events = [t for t in run['trace'] if t['stage'] == 'tool_call']
        self.assertEqual(len(events), 2)
        self.assertEqual({e['batch_model_call'] for e in events}, {1})
        self.assertEqual([m['tool_call_id'] for m in adapter.sent[1]['messages'] if m['role']=='tool'], ['old', 'new'])
        self.assertEqual(stable(run), stable(run_native(self.sources,self.case,'C',self.config,RecordedAdapter(run))))

    def test_atomic_batch_does_not_expose_partial_results_for_outside_source(self):
        first, second = self.reads()
        second = native('get_source', {'source_id': 'NOT-ALLOWED', 'start': 0, 'end': 100}, 'outside')
        quote = self.sources[self.case['old']].text[:100]
        candidate = finish(explanations=[{'source_id': self.case['old'], 'quote': quote}])
        run, adapter = self.execute([batch(first, second), native('finish', candidate), native('finish', finish())])
        self.assertFalse(run['errors'])
        self.assertEqual(len(run['validation_failures']), 2)
        self.assertEqual(run['validation_failures'][1]['error'], 'citation_not_in_retrieved_context')
        self.assertFalse(any(t['stage']=='tool_call' for t in run['trace']))
        feedback = [m for m in adapter.sent[1]['messages'] if m['role']=='tool']
        self.assertEqual(len(feedback), 2)
        self.assertTrue(all('validation_error' in m['content'] for m in feedback))

    def test_remaining_budget_counts_each_retrieval(self):
        config = {**self.config, 'max_calls': 4, 'max_tool_calls': 2}
        run, adapter = self.execute([batch(*self.reads()), self.reads()[0], native('finish', finish())], config)
        self.assertFalse(run['errors'])
        self.assertEqual(run['validation_failures'][0]['error'], 'finish_required_at_budget_boundary')
        self.assertEqual(sum(t['stage']=='tool_call' for t in run['trace']), 2)

    def test_over_budget_batch_is_rejected_before_exposing_any_result(self):
        config = {**self.config, 'max_calls': 4, 'max_tool_calls': 2}
        run, _ = self.execute([self.reads()[0], batch(*self.reads()), native('finish', finish())], config)
        self.assertEqual(run['validation_failures'][0]['error'], 'retrieval_batch_exceeds_remaining_tool_budget')
        self.assertEqual(sum(t['stage']=='tool_call' for t in run['trace']), 1)

    def test_finish_cannot_mix_with_retrieval(self):
        run, _ = self.execute([batch(self.reads()[0], native('finish',finish(),'done')), native('finish',finish())])
        self.assertEqual(run['validation_failures'][0]['error'], 'finish_must_be_submitted_alone')
        self.assertFalse(any(t['stage']=='tool_call' for t in run['trace']))

    def test_duplicate_ids_and_malformed_arguments_do_not_execute(self):
        variants = [batch(self.reads()[0],self.reads()[0]),
                    batch(self.reads()[0],native('get_source','{} trailing','bad'))]
        for reply in variants:
            with self.subTest(reply=reply):
                run, _ = self.execute([reply,native('finish',finish())])
                self.assertEqual(len(run['validation_failures']), 1)
                self.assertFalse(any(t['stage']=='tool_call' for t in run['trace']))

    def test_all_recorded_multi_search_responses_execute_within_original_budget(self):
        folder = ROOT/'reports/earnings-v3-preflight-2026-10-14'
        from eventlens.core import Source
        sources = {s['source_id']:Source(**s) for s in json.loads((folder/'sources.json').read_text())}
        config = json.loads((folder/'config.json').read_text())
        count = 0
        for path in sorted((folder/'runs').glob('*_C.json')):
            original = json.loads(path.read_text())
            for record in original['trace']:
                if record['stage'] != 'model_call' or record.get('validation_error') != 'expected_one_native_tool_call':
                    continue
                # Reuse only the saved action envelope. The next finish is SCRIPTED;
                # this does not replay the changed model conversation or prove quality.
                adapter = FixtureAdapter([record['raw_response'],native('finish',finish(),'fixture-finish')])
                run = run_native(sources,original['case'],'C',config,adapter)
                self.assertFalse(run['errors'],path.name)
                self.assertFalse(run['validation_failures'],path.name)
                self.assertEqual(sum(t['stage']=='tool_call' for t in run['trace']),2)
                count += 1
        self.assertEqual(count,18)

    def test_focused_pilot_has_eight_c_jobs_and_rejects_v3_approval(self):
        spec = importlib.util.spec_from_file_location('runner_v4',ROOT/'scripts/earnings_protocol_v4.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'pilot'
            estimate = runner.prepare(folder)
            sources, jobs, config = runner.check(folder)
            self.assertEqual(len(jobs),8)
            self.assertEqual(config['methods'],['C'])
            self.assertEqual(estimate['maximum_model_requests'],64)
            self.assertEqual(estimate['planned_method_runs'],8)
            self.assertEqual(runner.aggregate(folder,jobs)['planned_runs'],8)
            old = ROOT/'reports/earnings-v3-preflight-2026-10-14/approval.json'
            with self.assertRaisesRegex(ValueError,'this_frozen_experiment'):
                runner.approved_cap(folder,old,config)


if __name__ == '__main__':
    unittest.main()
