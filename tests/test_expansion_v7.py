"""Independent ablation, four-method parity, and budget allocation checks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('expansion_v7',ROOT/'scripts/earnings_expansion_v7.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class ExpansionV7Tests(unittest.TestCase):
    def test_only_pipe_rows_removed_prose_numbers_and_continuations_retained(self):
        text='FY2025 revenue guidance is $5–$6 billion.\n| Quarter | Year |\n| $1 | $6 |\n2025 continuation without a pipe\nActual revenue was $4 billion.\n'
        actual,spans=runner.table_rows_only(text)
        expected='FY2025 revenue guidance is $5–$6 billion.\n\n\n2025 continuation without a pipe\nActual revenue was $4 billion.\n'
        self.assertEqual(actual,expected)
        for span in spans:self.assertEqual(text[span['start']:span['end']],span['text'])
        rebuilt=text
        for span in reversed(spans):rebuilt=rebuilt[:span['start']]+rebuilt[span['end']:]
        self.assertEqual(rebuilt,actual)

    def test_entire_corpus_has_paired_ablation_and_preserved_source_identity(self):
        _,sources=runner.load_corpus(ROOT/'data/manifest.json')
        cases=json.loads((ROOT/'data/cases.json').read_text())
        config=json.loads((ROOT/'configs/earnings_expansion_v7.json').read_text())
        data,jobs=runner.population(sources,cases,config)
        self.assertEqual(len(jobs),72);self.assertEqual(jobs[:36],cases)
        for c in jobs[36:]:
            parent=next(x for x in cases if x['case_id']==c['parent_case_id'])
            self.assertEqual(data[c['old']],sources[parent['old']])
            self.assertEqual(c['parent_source_hash'],sources[parent['new']].content_hash)
            self.assertNotIn('|',data[c['new']].text)
            self.assertIsNone(c['transformation']['expected_status'])
            self.assertEqual(c['split'],'synthetic_'+parent['split'])

    def test_full_preflight_has_no_paid_calls_and_counts_only_B_C_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle'
            result=runner.prepare(folder)
            self.assertEqual(result['planned_method_runs'],288)
            self.assertEqual(result['maximum_model_requests'],648)
            self.assertEqual(Decimal(result['planning_scenario_usd']),Decimal('1.1804868'))
            self.assertFalse((folder/'requests').exists())
            sizes=json.loads((folder/'initial_request_sizes.json').read_text())
            self.assertTrue(sizes['all_initial_requests_fit'])
            self.assertTrue(all(v==0 for k,v in sizes['initial_wire_bytes'].items() if k.endswith(('_A','_D'))))

    def test_reserve_uses_request_ledger_and_includes_prior_costs(self):
        config=json.loads((ROOT/'configs/earnings_expansion_v7.json').read_text())
        self.assertEqual(runner.budget_remaining(config),Decimal('4.9052296'))

    def test_changed_budget_authorization_cannot_be_used(self):
        config=json.loads((ROOT/'configs/earnings_expansion_v7.json').read_text())
        config['budget_authorization_sha256']='incorrect'
        with self.assertRaisesRegex(ValueError,'budget_authorization_changed'):
            runner.budget_remaining(config)

    def test_overallocation_stops_before_provider_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';runner.prepare(folder)
            approval=Path(tmp)/'fixture-approval.json'
            runner.write_json(approval,{'approved':True,'approved_by':'Nick','max_usd':'3.25',
                'freeze_sha256':runner.digest((folder/'freeze.json').read_bytes()),
                'kind':'Unit-test fixture, not real paid authorization'})
            with patch.object(runner,'budget_remaining',return_value=Decimal('0.01')), patch.object(runner,'NativeAdapter') as adapter:
                with self.assertRaisesRegex(ValueError,'exceeds_remaining_authorized_budget'):
                    runner.execute_locked(folder,approval)
                adapter.assert_not_called()

    def test_uncertain_prior_charge_cannot_be_reallocated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            runner.write_json(root/'policy.json',{'maximum_total_improvement_spend_usd':'5.50'})
            runner.write_json(root/'previous/requests/one.json',{'state':'failed_or_uncertain','charged_upper_usd':'0.04'})
            cfg={'budget_authorization':'policy.json','budget_authorization_sha256':runner.digest((root/'policy.json').read_bytes()),'prior_paid_bundles':['previous']}
            with patch.object(runner,'ROOT',root), self.assertRaisesRegex(ValueError,'prior_uncertain_charge'):
                runner.budget_remaining(cfg)


if __name__=='__main__':unittest.main()
