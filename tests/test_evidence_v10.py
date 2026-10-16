"""Withdrawal is an explicit scope decision with no invented replacement values."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from eventlens.core import Source,digest,compare
from eventlens.evidence_v8 import guidance_catalog
from eventlens.evidence_v10 import EvidenceTools,withdrawal_candidate,KIND
ROOT=Path(__file__).resolve().parents[1]


class WithdrawalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=ROOT/'reports/earnings-v9-2026-10-15'
        cls.sources={s['source_id']:Source(**s) for s in json.loads((folder/'sources.json').read_text())}
        cls.jobs=json.loads((folder/'jobs.json').read_text())
        cls.case=next(c for c in cls.jobs if c['case_id']=='SNPS-FY2025-Q2-WITHDRAWAL')
        cls.old=cls.sources[cls.case['old']];cls.new=cls.sources[cls.case['new']]
        cls.prior=guidance_catalog(cls.old,'FY2025')[0]

    def test_actual_notice_uses_explicit_annual_scope_and_prior_identity(self):
        c=withdrawal_candidate(self.new,self.prior,'FY2025')
        self.assertEqual(c['proof']['kind'],KIND)
        self.assertEqual(c['metric']['status'],'withdrawn')
        self.assertIsNone(c['metric']['lower']);self.assertIsNone(c['metric']['upper'])
        for field in ('issuer','currency','unit','basis','horizon','definition'):
            self.assertEqual(c['metric'][field],self.prior['metric'][field])
        self.assertEqual(c['proof']['prior_guidance']['source_hash'],self.old.content_hash)
        self.assertIn(c['metric']['evidence'],self.new.text)

    def test_completed_scope_produces_withdrawn_not_zero_change(self):
        t=EvidenceTools(self.sources,[self.case['old'],self.case['new']],self.case['cutoff'],'FY2025')
        metrics=[]
        for sid in (self.case['old'],self.case['new']):
            t.publish(t.execute('inspect_guidance',{'source_id':sid}))
            metrics.append(t.resolve_metric(t.metrics[sid][0]['metric_id'])[0])
        r=compare(*metrics)
        self.assertEqual(r['reason'],'guidance_withdrawn');self.assertIsNone(r['calculation'])

    def test_negation_hypothesis_wrong_year_and_partial_scopes_abstain(self):
        for text in ['The company has not suspended its financial guidance for full fiscal year 2025.',
                     'If the company has suspended its financial guidance for full fiscal year 2025.',
                     'The company has suspended its financial guidance for the third quarter of fiscal year 2025.',
                     'The company has suspended its financial guidance for full fiscal year 2024.',
                     'The company has suspended its EPS guidance for full fiscal year 2025.',
                     'The company has suspended its financial guidance for EPS in full fiscal year 2025.',
                     'The company has suspended its financial guidance for full fiscal year 2025 except revenue.']:
            with self.subTest(text=text):
                s=replace(self.new,text=text,content_hash=digest(text))
                self.assertIsNone(withdrawal_candidate(s,self.prior,'FY2025'))

    def test_metadata_and_prior_target_are_required(self):
        self.assertIsNone(withdrawal_candidate(replace(self.new,forecast_horizons=['FY2024']),self.prior,'FY2025'))
        prior=deepcopy(self.prior);prior['metric']['status']='withdrawn';prior['metric']['lower']=None;prior['metric']['upper']=None
        self.assertIsNone(withdrawal_candidate(self.new,prior,'FY2025'))

    def test_tampered_inherited_identity_is_rejected(self):
        t=EvidenceTools(self.sources,[self.case['old'],self.case['new']],self.case['cutoff'],'FY2025')
        t.publish(t.execute('inspect_guidance',{'source_id':self.case['new']}))
        mid=t.metrics[self.case['new']][0]['metric_id']
        t.visible_metrics[mid]=deepcopy(t.visible_metrics[mid]);t.visible_metrics[mid]['metric']['currency']='EUR'
        with self.assertRaisesRegex(ValueError,'withdrawal_registry_mismatch'):t.resolve_metric(mid)

    def test_all_other_original_stress_catalogs_stay_identical(self):
        for c in self.jobs:
            t=EvidenceTools(self.sources,[c['old'],c['new']],c['cutoff'],c['horizon'])
            for sid in set((c['old'],c['new'])):
                if c['case_id']==self.case['case_id'] and sid==c['new']:continue
                self.assertEqual(t.metrics[sid],guidance_catalog(self.sources[sid],c['horizon']))

    def test_all_corpus_and_table_ablation_catalogs_stay_identical(self):
        folder=ROOT/'reports/earnings-v8-2026-10-15'
        sources={s['source_id']:Source(**s) for s in json.loads((folder/'sources.json').read_text())}
        for c in json.loads((folder/'jobs.json').read_text()):
            t=EvidenceTools(sources,[c['old'],c['new']],c['cutoff'],c['horizon'])
            for sid in (c['old'],c['new']):
                self.assertEqual(t.metrics[sid],guidance_catalog(sources[sid],c['horizon']))


if __name__=='__main__':unittest.main()
