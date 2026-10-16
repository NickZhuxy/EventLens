"""The expanded stress run keeps original inputs and rejects stale inputs offline."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import earnings_stress_v9 as runner


class StressV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads((ROOT/'configs/earnings_stress_v9.json').read_text())
        cls.sources,cls.jobs=runner.population(None,None,cls.config)

    def test_exact_original_jobs_and_sources(self):
        old=ROOT/'reports/earnings-v2-2026-10-13'
        jobs=json.loads((old/'jobs.json').read_text())
        sources={s['source_id']:s for s in json.loads((old/'sources.json').read_text())}
        self.assertEqual(len(self.jobs),74)
        self.assertEqual(sum(c['split']=='supplemental_natural' for c in self.jobs),2)
        for case in self.jobs:
            self.assertIn(case,jobs)
        for sid,s in self.sources.items():
            self.assertEqual(runner.asdict(s),sources[sid])

    def test_stale_controls_never_reach_adapter(self):
        class FailIfCalled:
            model='offline-test';kind='not_model_inference'
            def complete(self,*args):raise AssertionError('stale input reached adapter')
        stale=[c for c in self.jobs if c.get('challenge')=='stale_disclosure']
        self.assertEqual(len(stale),24)
        for case in stale:
            for method in self.config['methods']:
                r=runner.run_native(self.sources,case,method,self.config,FailIfCalled())
                self.assertEqual(r['calls'],0)
                self.assertEqual(r['comparison']['reason'],'stale_or_reversed_disclosure_pair')

    def test_cost_bound_excludes_stale_calls_and_deterministic_methods(self):
        estimate=runner.estimate(self.jobs,self.config)
        self.assertEqual(estimate['planned_method_runs'],296)
        self.assertEqual(estimate['maximum_model_requests'],450)
        self.assertEqual(estimate['planning_scenario_usd'],'0.81978250')

    def test_oversized_baseline_is_recorded_without_changing_its_limit(self):
        c=next(x for x in self.jobs if x['case_id']=='CRM-FY2024-Q1-Q2~v2-missing_table')
        result=runner.initial_request_sizes(self.sources,[c],self.config)
        self.assertFalse(result['all_initial_requests_fit'])
        self.assertEqual(result['known_pre_request_failures'],{c['case_id']+'_B':'input_context_budget_exhausted'})
        self.assertIsNone(result['initial_wire_bytes'][c['case_id']+'_B'])
        self.assertEqual(result['network_calls'],0)
        self.assertEqual(self.config['max_input_bytes'],128000)


if __name__=='__main__':unittest.main()
