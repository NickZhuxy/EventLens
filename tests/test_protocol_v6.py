"""V6 reference contract checks; scripted fixtures are never live outcomes."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from eventlens.core import Source, canonical
from eventlens.benchmark import RecordedAdapter, stable
from eventlens.evidence_v5 import EvidenceTools
from eventlens.protocol_v6 import run_native, reference_schema, validate_shape, validate_finish
from test_protocol_v3 import FixtureAdapter, native
from test_protocol_v4 import batch

ROOT = Path(__file__).resolve().parents[1]


def finish(**changes):
    return dict(metric_ids=[], explanation_ids=[], conflicts=[], comparability=[],
                unresolved='SCRIPTED contract fixture.', **changes)


class ProtocolV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT/'reports/earnings-v5-preflight-2026-10-15'
        cls.sources = {s['source_id']: Source(**s) for s in json.loads((cls.folder/'sources.json').read_text())}
        cls.jobs = json.loads((cls.folder/'jobs.json').read_text())
        cls.case = next(c for c in cls.jobs if c.get('challenge') == 'contradictory_commentary')
        cls.config = json.loads((ROOT/'configs/earnings_protocol_v6.json').read_text())

    def tools(self, case=None, publish=True):
        c = case or self.case
        tools = EvidenceTools(self.sources, [c['old'], c['new']], c['cutoff'], c['horizon'])
        if publish:
            for sid in (c['old'], c['new']):
                for name in ('inspect_guidance', 'review_explanations'):
                    tools.publish(tools.execute(name, {'source_id': sid}))
        return tools

    def reads(self, case=None):
        c = case or self.case
        return batch(*[native(name, {'source_id': c[k]}, k+name) for k in ('old', 'new')
                       for name in ('inspect_guidance', 'review_explanations')])

    def test_schema_does_not_expose_unpublished_candidates(self):
        tools = self.tools(publish=False)
        schema = reference_schema(tools)['properties']
        self.assertTrue(any(tools.metrics.values()))
        self.assertEqual(schema['metric_ids']['items']['enum'], ['NO_VISIBLE_REFERENCE'])
        out = tools.execute('review_explanations', {'source_id': self.case['new']})
        self.assertEqual(reference_schema(tools)['properties']['explanation_ids']['items']['enum'], ['NO_VISIBLE_REFERENCE'])
        tools.publish(out)
        self.assertEqual(reference_schema(tools)['properties']['explanation_ids']['items']['enum'], sorted(tools.citations))

    def test_every_reference_field_uses_only_visible_ids(self):
        tools = self.tools()
        p = reference_schema(tools)['properties']
        self.assertEqual(p['metric_ids']['items']['enum'], sorted(tools.visible_metrics))
        nodes = [p['explanation_ids']['items'], p['comparability']['items']['properties']['evidence_ids']['items']]
        nodes += [p['conflicts']['items']['properties'][k] for k in ('statement_a_id', 'statement_b_id')]
        for node in nodes:
            self.assertEqual(node['enum'], sorted(tools.citations))
        self.assertNotIn('statement_a', p['conflicts']['items']['properties'])

    def test_recorded_v5_quote_arguments_rejected_with_specific_field_path(self):
        checked = 0
        for path in (self.folder/'runs').glob('*contradictory*.json'):
            run = json.loads(path.read_text())
            tools = self.tools(run['case'])
            for t in run['trace']:
                if t['stage'] != 'model_call':
                    continue
                for call in t['raw_response']['choices'][0]['message'].get('tool_calls', []):
                    if call['function']['name'] != 'finish':
                        continue
                    args = json.loads(call['function']['arguments'])
                    for c in args['conflicts']:
                        candidate = finish()
                        candidate['conflicts'] = [{'topic': c['topic'], 'reason': c['reason'],
                            'statement_a_id': c['statement_a'], 'statement_b_id': c['statement_b']}]
                        with self.assertRaisesRegex(ValueError, 'arguments.conflicts.0.statement_a_id: invalid_enum'):
                            validate_shape(candidate, reference_schema(tools))
                        checked += 1
        self.assertEqual(checked, 15)

    def test_fabricated_foreign_id_rejected_before_partial_output(self):
        args = finish()
        args['metric_ids'] = list(self.tools().visible_metrics)
        args['explanation_ids'] = ['e_not_visible']
        adapter = FixtureAdapter([self.reads(), native('finish', args), native('finish', finish())])
        r = run_native(self.sources, self.case, 'C', self.config, adapter)
        self.assertFalse(r['errors'])
        self.assertEqual(r['validation_failures'][0]['error'], 'arguments.explanation_ids.0: invalid_enum')
        self.assertEqual(r['extractions'], [])

    def test_empty_choices_allow_abstention_but_sentinel_cannot_be_evidence(self):
        tools = self.tools(publish=False)
        validate_shape(finish(), reference_schema(tools))
        # Empty catalogs on a digit-masked source are not replaced with fake metrics.
        case = next(c for c in self.jobs if c.get('challenge') == 'missing_numerical_evidence')
        tools = self.tools(case)
        self.assertFalse(tools.metrics[case['new']])
        args = finish()
        args['explanation_ids'] = ['NO_VISIBLE_REFERENCE']
        with self.assertRaisesRegex(ValueError, 'citation_id_not_in_retrieved_context'):
            validate_finish(args, [self.sources[case[k]] for k in ('old','new')], case, tools)

    def test_enum_refreshes_after_successful_optional_read(self):
        tools = self.tools()
        before = deepcopy(reference_schema(tools))
        out = tools.execute('get_source', {'source_id': self.case['old'], 'start': 0, 'end': 121})
        eid = out['citations'][0]['evidence_id']
        self.assertNotIn(eid, before['properties']['explanation_ids']['items']['enum'])
        tools.publish(out)
        self.assertIn(eid, reference_schema(tools)['properties']['explanation_ids']['items']['enum'])

    def test_failed_batch_publishes_no_references_into_next_schema(self):
        bad = batch(native('inspect_guidance', {'source_id': self.case['old']}, 'one'),
                    native('review_explanations', {'source_id': 'foreign'}, 'two'))
        a = FixtureAdapter([bad, self.reads(), native('finish', finish())])
        r = run_native(self.sources, self.case, 'C', self.config, a)
        self.assertFalse(r['errors'])
        schema = next(t['function']['parameters'] for t in a.sent[1]['tools'] if t['function']['name'] == 'finish')
        self.assertEqual(schema['properties']['metric_ids']['items']['enum'], ['NO_VISIBLE_REFERENCE'])

    def test_valid_scripted_conflicts_replay_and_wire_choices_remain_bound(self):
        for case in self.jobs:
            if case.get('challenge') != 'contradictory_commentary':
                continue
            tools = self.tools(case)
            ids = [next(eid for eid, c in tools.citations.items() if c['quote'] == q)
                   for q in case['transformation']['expected_conflict_quotes']]
            args = finish()
            args['metric_ids'] = list(tools.visible_metrics)
            args['conflicts'] = [{'topic': 'fixture', 'reason': 'Scripted known construction.',
                                  'statement_a_id': ids[0], 'statement_b_id': ids[1]}]
            for method in ('B','C'):
                a = FixtureAdapter(([self.reads(case)] if method == 'C' else [])+[native('finish', args)])
                r = run_native(self.sources, case, method, self.config, a)
                self.assertFalse(r['errors']); self.assertEqual(r['conclusion'], 'conflicting')
                self.assertTrue(r['comparison']['calculation'])
                saved = json.loads(canonical(r))
                self.assertEqual(stable(saved), stable(run_native(self.sources, case, method, self.config, RecordedAdapter(saved))))
                self.assertTrue(all(len(canonical(body).encode()) <= self.config['max_input_bytes'] for body in a.sent))

    def test_budgets_input_sizes_and_fresh_approval_binding(self):
        spec = importlib.util.spec_from_file_location('runner_v6', ROOT/'scripts/earnings_protocol_v6.py')
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'preflight'
            estimate = runner.prepare(folder)
            _, jobs, config = runner.check(folder)
            self.assertEqual(len(jobs), 4)
            self.assertEqual(estimate['planned_method_runs'], 8)
            self.assertEqual(estimate['maximum_model_requests'], 36)
            self.assertEqual(estimate['conservative_full_budget_bound_usd'], '1.6858368')
            with self.assertRaisesRegex(ValueError, 'this_frozen_experiment'):
                runner.approved_cap(folder, self.folder/'approval.json', config)


if __name__ == '__main__':
    unittest.main()
