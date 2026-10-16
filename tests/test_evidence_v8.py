"""Observed development impact error plus independent point/range controls."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from eventlens.core import Source
from eventlens import evidence_v5 as old
from eventlens.evidence_v8 import guidance_catalog,rejected_candidates,point_target_issue,EvidenceTools
from test_evidence_v5 import source

ROOT=Path(__file__).resolve().parents[1]


class EvidenceV8Tests(unittest.TestCase):
    def test_actual_adobe_headwind_is_not_total_revenue(self):
        sources={s['source_id']:Source(**s) for s in json.loads((ROOT/'reports/earnings-v7-2026-10-15/sources.json').read_text())}
        s=sources['ADBE-2024-Q4']
        self.assertEqual(len(old.guidance_catalog(s,'FY2025')),2)
        candidates=guidance_catalog(s,'FY2025')
        self.assertEqual(len(candidates),1)
        self.assertEqual((candidates[0]['metric']['lower'],candidates[0]['metric']['upper']),('23.30','23.55'))
        rejected=rejected_candidates(s,'FY2025')
        self.assertEqual(rejected[0]['metric']['lower'],'200')
        self.assertEqual(rejected[0]['reason'],'point_amount_describes_impact_or_change')

    def test_point_target_retained_with_growth_commentary(self):
        text='Fiscal year 2025 outlook: total revenue is expected to be $5 billion, representing 10 percent growth.\n'
        c=guidance_catalog(source(text),'FY2025')
        self.assertEqual(len(c),1);self.assertEqual(c[0]['metric']['lower'],'5')

    def test_amount_before_revenue_requires_abstention_not_inference(self):
        s=source('We expect approximately $200 million for fiscal year 2025 revenue.\n')
        for c in old.guidance_catalog(s,'FY2025'):
            self.assertEqual(point_target_issue(c['metric']),'point_target_requires_revenue_before_amount')
        self.assertEqual(guidance_catalog(s,'FY2025'),[])

    def test_impact_and_change_amounts_fail_without_creating_replacement_values(self):
        metric={'status':'provided','lower':'200','upper':'200','unit':'million','evidence':''}
        for sentence in ['Revenue headwind of $200 million.','Revenue increase of $200 million.',
                         'Revenue impact of $200 million.','An approximate $200 million headwind to revenue.']:
            m={**metric,'evidence':sentence}
            self.assertEqual(point_target_issue(m),'point_amount_describes_impact_or_change')

    def test_equal_endpoint_range_is_not_reinterpreted_as_an_impact(self):
        m={'status':'provided','lower':'5','upper':'5','unit':'billion','evidence':'FY2025 revenue guidance: $5 billion to $5 billion.'}
        self.assertIsNone(point_target_issue(m))

    def test_filtered_candidate_cannot_be_reintroduced_through_registry(self):
        s=source('We expect an approximate $200 million headwind to fiscal year 2025 revenue.\n')
        original=old.guidance_catalog(s,'FY2025')[0]
        tools=EvidenceTools({s.source_id:s},[s.source_id],'2025-06-01T00:00:00Z','FY2025')
        self.assertEqual(tools.metrics[s.source_id],[])
        tools.metrics[s.source_id]=[deepcopy(original)];tools.visible_metrics[original['metric_id']]=deepcopy(original)
        with self.assertRaisesRegex(ValueError,'registry_mismatch'):
            tools.resolve_metric(original['metric_id'])


if __name__=='__main__':unittest.main()
