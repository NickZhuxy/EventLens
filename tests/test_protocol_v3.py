"""Native protocol fixtures verify behavior, not live model quality."""
from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventlens.core import digest, load_corpus
from eventlens.benchmark import BudgetJournal, RecordedAdapter, stable, write_json
from eventlens.extraction import extract
from eventlens.llm import ProviderSettings
from eventlens.protocol_v3 import NativeAdapter, SCHEMAS, request_body, run_native, validate_shape

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v3_runner', ROOT/'scripts/earnings_protocol_v3.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def native(name, args, ident='call-1'):
    return {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None,
            'tool_calls': [{'id': ident, 'type': 'function', 'function': {'name': name,
                           'arguments': args if isinstance(args, str) else json.dumps(args)}}]}}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 30, 'total_tokens': 80}}


def finish(**changes):
    return dict({'metrics': [], 'explanations': [], 'conflicts': [], 'comparability': [],
                 'unresolved': 'Fixture abstention, no human review.'}, **changes)


class FixtureAdapter:
    model = 'deepseek-flash'
    kind = 'scripted_test_fixture_not_an_LLM'
    settings = ProviderSettings('https://api.deepseek.com/beta', 'none')

    def __init__(self, responses):
        self.responses = iter(responses)
        self.sent = []

    def complete(self, payload, max_output):
        self.sent.append(deepcopy(payload))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return deepcopy(response)


class ProtocolV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.sources = load_corpus(ROOT/'data/manifest.json')
        cls.cases = json.loads((ROOT/'data/cases.json').read_text())
        cls.case = cls.cases[0]  # Original Adobe pair has literal, extractable annual rows.
        cls.config = json.loads((ROOT/'configs/earnings_protocol_v3.json').read_text())

    def run_case(self, responses, method='C', config=None, case=None, sources=None):
        adapter = FixtureAdapter(responses)
        result = run_native(sources or self.sources, case or self.case, method,
                            config or self.config, adapter)
        return result, adapter

    def test_wire_uses_non_thinking_native_strict_tools_for_both_methods(self):
        for method in 'BC':
            wire = request_body([], method, self.config)
            self.assertEqual(wire['thinking'], {'type': 'disabled'})
            self.assertEqual(wire['max_tokens'], 6000)
            self.assertNotIn('response_format', wire)
            for tool in wire['tools']:
                self.assertTrue(tool['function']['strict'])
                self.assertFalse(tool['function']['parameters']['additionalProperties'])
            self.assertEqual(wire['tool_choice'], 'required' if method == 'C' else
                             {'type': 'function', 'function': {'name': 'finish'}})

    def test_json_text_is_never_executed_as_a_tool(self):
        text = {'choices': [{'finish_reason': 'stop', 'message': {'content':
                json.dumps({'action': 'tool', 'name': 'get_source', 'arguments': {}})}}]}
        run, adapter = self.run_case([text, native('finish', finish())])
        self.assertEqual(run['calls'], 2)
        self.assertEqual(len(run['validation_failures']), 1)
        self.assertFalse(run['errors'])
        self.assertFalse(any(e['stage'] == 'tool_call' for e in run['trace']))
        self.assertEqual(run['trace'][0]['raw_response'], text)

    def test_malformed_function_arguments_repaired_without_executing_prefix(self):
        invalid = native('get_source', '{"source_id":"outside","start":0,"end":1} trailing')
        run, adapter = self.run_case([invalid, native('finish', finish())])
        self.assertFalse(run['errors'])
        self.assertEqual(adapter.sent[1]['messages'][-1]['role'], 'tool')
        self.assertFalse(any(e['stage'] == 'tool_call' for e in run['trace']))
        self.assertEqual(run['trace'][0]['raw_response'], invalid)

    def test_unretrieved_citation_requires_actual_retrieval_before_acceptance(self):
        source = self.sources[self.case['new']]
        quote = source.text[:100]
        answer = finish(explanations=[{'source_id': source.source_id, 'quote': quote}])
        run, adapter = self.run_case([native('finish', answer), native('get_source', {
            'source_id': source.source_id, 'start': 0, 'end': 100}, 'read-1'),
            native('finish', answer, 'finish-2')])
        self.assertEqual(run['validation_failures'][0]['error'], 'citation_not_in_retrieved_context')
        self.assertFalse(run['errors'])
        self.assertTrue(run['explanations'][0]['literal_valid'])
        self.assertEqual(run['explanations'][0]['semantic_review'], 'pending')
        replay = RecordedAdapter(run)
        self.assertEqual(stable(run), stable(run_native(self.sources, self.case, 'C', self.config, replay)))
        changed = deepcopy(run)
        changed['trace'][0]['messages']['tools'][0]['function']['strict'] = False
        with self.assertRaisesRegex(AssertionError, 'request_mismatch'):
            run_native(self.sources, self.case, 'C', self.config, RecordedAdapter(changed))

    def test_repair_budget_is_finite_and_failure_is_not_valid_abstention(self):
        bad = native('finish', finish(explanations=[{'source_id': 'OUTSIDE', 'quote': 'invented'}]))
        run, adapter = self.run_case([bad, bad, bad])
        self.assertEqual(run['calls'], 3)
        self.assertTrue(run['errors'])
        self.assertFalse(run['explanations'])
        self.assertEqual(runner.metrics([run])[0]['completed_without_errors'], 0)

    def test_single_pass_baseline_gets_no_repair(self):
        run, adapter = self.run_case([native('finish', finish(explanations=[
            {'source_id': self.case['new'], 'quote': 'not an actual quote'}]))], 'B')
        self.assertEqual(run['calls'], 1)
        self.assertTrue(run['errors'])

    def test_no_transport_retry_or_validation_feedback_on_uncertain_billing(self):
        run, adapter = self.run_case([RuntimeError('provider_call_failed; reservation retained')])
        self.assertEqual(run['calls'], 1)
        self.assertFalse(run['validation_failures'])
        self.assertIn('reservation retained', run['errors'][0])

    def test_stale_and_future_sources_never_touch_adapter(self):
        for case in ({**self.case, 'new': self.case['old']},
                     {**self.case, 'cutoff': self.sources[self.case['old']].available_at}):
            adapter = Mock()
            run = run_native(self.sources, case, 'C', self.config, adapter)
            adapter.complete.assert_not_called()
            self.assertEqual(run['calls'], 0)

    def test_local_schema_rejects_bool_offsets_and_extra_fields(self):
        for args in ({'source_id': 'x', 'start': False, 'end': 10},
                     {'source_id': 'x', 'start': 0, 'end': 10, 'url': 'https://example.com'}):
            with self.assertRaises(ValueError):
                validate_shape(args, SCHEMAS['get_source'])

    def test_last_call_forces_finish_and_prevents_extra_retrieval(self):
        request = native('get_source', {'source_id': self.case['new'], 'start': 0, 'end': 100})
        config = {**self.config, 'max_calls': 2, 'max_tool_calls': 1}
        run, adapter = self.run_case([request, request], config=config)
        self.assertEqual(run['calls'], 2)
        self.assertEqual(sum(e['stage'] == 'tool_call' for e in run['trace']), 1)
        self.assertEqual(adapter.sent[-1]['tool_choice']['function']['name'], 'finish')
        self.assertIn('finish_required_at_budget_boundary', run['errors'])

    def test_literal_metrics_still_use_original_validator_and_decimal(self):
        values = [asdict(extract(self.sources[self.case[k]], self.case['horizon'])[0]) for k in ('old', 'new')]
        run, adapter = self.run_case([native('finish', finish(metrics=values))], 'B')
        self.assertFalse(run['errors'])
        self.assertEqual(Decimal(run['comparison']['calculation']['midpoint_delta']), Decimal('125000000'))
        for field, value in [('calendar', 'calendar'), ('lower', '999'), ('horizon', 'FY2026')]:
            bad = deepcopy(values)
            bad[0][field] = value
            run, _ = self.run_case([native('finish', finish(metrics=bad))], 'B')
            self.assertTrue(run['errors'])
            self.assertIsNone(run['comparison']['calculation'])

    def test_missing_value_cannot_be_promoted_to_zero(self):
        sources, jobs = runner.population(self.sources, self.cases, self.config)
        case = next(c for c in jobs if c.get('challenge') == 'missing_numerical_evidence')
        run, _ = self.run_case([native('finish', finish())], 'B', case=case, sources=sources)
        self.assertFalse(run['errors'])
        self.assertIsNone(run['comparison']['calculation'])
        self.assertEqual(runner.metrics([run])[0]['valid_control_outcomes'], 1)

    def test_conflict_requires_both_retrieved_synthetic_quotes(self):
        sources, jobs = runner.population(self.sources, self.cases, self.config)
        case = next(c for c in jobs if c.get('challenge') == 'contradictory_commentary')
        source = sources[case['new']]
        a, b = case['transformation']['expected_conflict_quotes']
        answer = finish(conflicts=[{'topic': 'demand', 'reason': 'Opposite synthetic assertions',
                    'statement_a': {'source_id': source.source_id, 'quote': a},
                    'statement_b': {'source_id': source.source_id, 'quote': b}}])
        run, _ = self.run_case([native('get_source', {'source_id': source.source_id,
            'start': source.text.index(a), 'end': len(source.text)}), native('finish', answer)],
            case=case, sources=sources)
        self.assertFalse(run['errors'])
        self.assertEqual(runner.metrics([run])[0]['valid_control_outcomes'], 1)
        self.assertTrue(all(c['origin'] == 'synthetic' for c in run['conflicts'][0]['citations']))

    def test_scope_warning_abstains_with_citations(self):
        source = self.sources[self.case['new']]
        run, _ = self.run_case([native('finish', finish(comparability=[{
            'status': 'not_comparable', 'reason': 'Fixture candidate requires human judgment',
            'evidence': [{'source_id': source.source_id, 'quote': source.text[:100]}]}]))], 'B')
        self.assertFalse(run['errors'])
        self.assertIsNone(run['comparison']['calculation'])
        self.assertEqual(run['comparability']['semantic_review'], 'pending')

    def test_byte_budget_counts_full_tool_schema_and_unicode(self):
        run, adapter = self.run_case([], config={**self.config, 'max_input_bytes': 1000})
        self.assertEqual(run['calls'], 0)
        self.assertFalse(adapter.sent)
        self.assertEqual(run['errors'], ['input_context_budget_exhausted'])

    def test_population_never_uses_heldout_and_estimate_covers_all_calls(self):
        sources, jobs = runner.population(self.sources, self.cases, self.config)
        self.assertEqual(len(jobs), 16)
        self.assertEqual({c['issuer'] for c in jobs}, {'ADBE', 'INTU', 'SNPS', 'BOX'})
        estimate = runner.estimate(jobs, self.config)
        self.assertEqual(estimate['maximum_model_requests'], 108)
        self.assertLess(Decimal(estimate['conservative_full_budget_bound_usd']), Decimal('6'))
        sizes = runner.initial_request_sizes(sources, jobs, self.config)
        self.assertTrue(sizes['all_initial_requests_fit'])
        self.assertEqual(len(sizes['initial_wire_bytes']), 32)
        bad = {**self.config, 'case_ids': [next(c['case_id'] for c in self.cases if c['split'] == 'heldout')]}
        with self.assertRaisesRegex(ValueError, 'development'):
            runner.population(self.sources, self.cases, bad)

    def test_native_journal_reserves_schema_and_reuses_exact_wire_body(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter = FixtureAdapter([native('finish', finish())])
            wire = request_body([], 'C', self.config)
            journal = BudgetJournal(temp, adapter, '1', self.config['pricing']).bind('test_C')
            journal.complete(wire, 6000)
            journal.bind('test_C').complete(wire, 6000)
            self.assertEqual(len(adapter.sent), 1)
            saved = json.loads((Path(temp)/'test_C.01.json').read_text())
            self.assertGreater(saved['input_token_bound'], len(json.dumps(wire['tools'])))
            changed = deepcopy(wire)
            changed['tool_choice'] = 'auto'
            with self.assertRaisesRegex(ValueError, 'request_changed'):
                journal.bind('test_C').complete(changed, 6000)
            adapter.sent.clear()
            journal = BudgetJournal(Path(temp)/'denied', adapter, '0.000001', self.config['pricing']).bind('test_C')
            with self.assertRaisesRegex(RuntimeError, 'budget_exhausted'):
                journal.complete(wire, 6000)
            self.assertFalse(adapter.sent)

    def test_old_approval_cannot_authorize_new_pilot(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'bundle'
            runner.prepare(folder)
            approval = Path(temp)/'approval.json'
            write_json(approval, {'approved': True, 'approved_by': 'Nick', 'max_usd': '8', 'config_sha256': 'old-v2'})
            with self.assertRaisesRegex(ValueError, 'this_frozen_experiment'):
                runner.approved_cap(folder, approval, self.config)

    def test_saved_native_bundle_replays_and_rejects_changed_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'bundle'
            runner.prepare(folder)
            sources, jobs, config = runner.check(folder)
            adapter = FixtureAdapter([native('finish', finish())])
            journal = BudgetJournal(folder/'requests', adapter, '1', config['pricing'])
            case = jobs[0]
            run = run_native(sources, case, 'B', config, journal.bind(case['case_id']+'_B'))
            write_json(folder/'runs'/(case['case_id']+'_B.json'), run)
            runner.save_state(folder, jobs)
            self.assertEqual(runner.replay(folder)['replayed_runs'], 1)
            write_json(folder/'summary.json', {})
            with self.assertRaisesRegex(ValueError, 'hash_mismatch'):
                runner.replay(folder)

    def test_native_transport_has_no_automatic_retries(self):
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'unit-test-placeholder'}):
            adapter = NativeAdapter(self.config)
        self.assertEqual(adapter.max_retries, 0)
        adapter.opener = Mock()
        adapter.opener.open.side_effect = TimeoutError()
        with self.assertRaisesRegex(RuntimeError, 'transport_error'):
            adapter.complete(request_body([], 'B', self.config), 6000)
        self.assertEqual(adapter.opener.open.call_count, 1)

    def test_crash_after_response_preserves_pending_request_for_exact_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'bundle'
            runner.prepare(folder)
            sources, jobs, config = runner.check(folder)
            runner.save_state(folder, jobs)
            adapter = FixtureAdapter([native('finish', finish())])
            journal = BudgetJournal(folder/'requests', adapter, '1', config['pricing'])
            case = jobs[0]
            prefix = case['case_id']+'_B'
            first = run_native(sources, case, 'B', config, journal.bind(prefix))
            # Simulate a crash after the response journal, before the run/summary save.
            with self.assertRaisesRegex(ValueError, 'inventory_changed'):
                runner.replay(folder)
            runner.replay(folder, allow_pending=True)
            second = run_native(sources, case, 'B', config, journal.bind(prefix))
            self.assertEqual(stable(first), stable(second))
            self.assertEqual(len(adapter.sent), 1)
            write_json(folder/'runs'/(prefix+'.json'), second)
            runner.save_state(folder, jobs)
            self.assertEqual(runner.replay(folder)['journalled_requests'], 1)


if __name__ == '__main__':
    unittest.main()
