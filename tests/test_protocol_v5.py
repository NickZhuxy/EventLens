"""Scripted v5 controller behavior, explicitly not live model performance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from eventlens.core import Source
from eventlens.benchmark import RecordedAdapter, stable
from eventlens.evidence_v5 import EvidenceTools
from eventlens.protocol_v5 import run_native
from test_protocol_v3 import FixtureAdapter, native
from test_protocol_v4 import batch

ROOT=Path(__file__).resolve().parents[1]


def finish(**changes):
    return dict({'metric_ids':[],'explanation_ids':[],'conflicts':[],'comparability':[],
                 'unresolved':'Scripted fixture; no model or human judgments.'},**changes)


class ProtocolV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=ROOT/'reports/earnings-v4-preflight-2026-10-15'
        cls.sources={s['source_id']:Source(**s) for s in json.loads((folder/'sources.json').read_text())}
        jobs=json.loads((folder/'jobs.json').read_text())
        cls.case=next(c for c in jobs if c['case_id']=='SNPS-FY2025-Q1-Q2')
        cls.jobs=jobs
        cls.config=json.loads((ROOT/'configs/earnings_protocol_v5.json').read_text())

    def reviews(self,case=None):
        c=case or self.case
        return [native(name,{'source_id':c[k]},k+name) for k in ('old','new')
                for name in ('inspect_guidance','review_explanations')]

    def selection(self,case=None):
        c=case or self.case
        tools=EvidenceTools(self.sources,[c['old'],c['new']],c['cutoff'],c['horizon'])
        for k in ('old','new'):
            for name in ('inspect_guidance','review_explanations'):
                tools.publish(tools.execute(name,{'source_id':c[k]}))
        return finish(metric_ids=list(tools.visible_metrics)),tools

    def execute(self,replies,case=None,method='C'):
        adapter=FixtureAdapter(replies)
        r=run_native(self.sources,case or self.case,method,self.config,adapter)
        return r,adapter

    def test_mixed_table_success_and_disk_round_trip_exact_replay(self):
        selection,_=self.selection()
        r,_=self.execute([batch(*self.reviews()),native('finish',selection)])
        self.assertFalse(r['errors']);self.assertEqual(r['comparison']['reason'],'unchanged')
        self.assertEqual(r['comparison']['calculation']['old_lower'],'6745000000')
        self.assertEqual(r['evidence_coverage']['completed_reviews'],4)
        saved=json.loads(json.dumps(r))
        self.assertEqual(stable(saved),stable(run_native(self.sources,self.case,'C',self.config,RecordedAdapter(saved))))

    def test_cannot_finish_before_explanation_reviews(self):
        selection,_=self.selection()
        reads=self.reviews()
        r,_=self.execute([batch(reads[0],reads[2]),native('finish',selection),
                          batch(reads[1],reads[3]),native('finish',selection)])
        self.assertEqual(r['validation_failures'][0]['error'],'required_evidence_reviews_pending')
        self.assertFalse(r['errors']);self.assertTrue(r['comparison']['calculation'])

    def test_budget_reserved_for_required_reviews(self):
        search=[native('get_source',{'source_id':self.case['old'],'start':i,'end':i+100},str(i)) for i in range(4)]
        r,_=self.execute([batch(*search),batch(*self.reviews()),native('finish',finish())])
        self.assertEqual(r['validation_failures'][0]['error'],'retrieval_budget_reserved_for_required_reviews')
        self.assertEqual(sum(t['stage']=='tool_call' for t in r['trace']),4)
        self.assertFalse(r['errors'])

    def test_failed_batch_publishes_no_metric_or_citation(self):
        reads=self.reviews()
        r,_=self.execute([batch(reads[0],native('review_explanations',{'source_id':'foreign'},'bad')),
                          batch(*reads),native('finish',finish())])
        self.assertIn('outside allowed',r['validation_failures'][0]['error'])
        self.assertEqual(sum(t['stage']=='tool_call' for t in r['trace']),4)
        self.assertFalse(r['errors'])

    def test_invented_reference_rejected_without_partial_commit(self):
        selection,_=self.selection()
        bad=deepcopy(selection);bad['explanation_ids']=['e_invented']
        r,_=self.execute([batch(*self.reviews()),native('finish',bad),native('finish',finish())])
        self.assertEqual(r['validation_failures'][0]['error'],'citation_id_not_in_retrieved_context')
        self.assertEqual(r['extractions'],[])

    def test_b_receives_same_catalog_and_remains_one_model_call(self):
        selection,_=self.selection()
        r,a=self.execute([native('finish',selection)],method='B')
        self.assertFalse(r['errors']);self.assertEqual(r['calls'],1)
        h=json.loads(a.sent[0]['messages'][1]['content'])
        self.assertEqual(len(h['disclosures']),2);self.assertEqual(len(h['evidence_catalogs']),4)
        self.assertFalse(any(t['stage']=='tool_call' for t in r['trace']))

    def test_four_control_traces_use_real_retrieval_but_scripted_conflict_selection(self):
        for c in self.jobs:
            if not c.get('synthetic'):continue
            selection,tools=self.selection(c)
            expected=c['transformation']['expected_conflict_quotes']
            ids=[next(eid for eid,item in tools.citations.items() if item['quote']==q) for q in expected]
            selection['conflicts']=[{'topic':'demand','reason':'Scripted known opposite-polarity fixture.',
                                    'statement_a':ids[0],'statement_b':ids[1]}]
            r,_=self.execute([batch(*self.reviews(c)),native('finish',selection)],case=c)
            self.assertFalse(r['errors']);self.assertEqual(r['conclusion'],'conflicting')
            self.assertEqual({x['quote'] for x in r['conflicts'][0]['citations']},set(expected))
            self.assertTrue(r['comparison']['calculation'])

    def test_same_statement_cannot_be_its_own_conflict(self):
        selection,tools=self.selection()
        eid=next(iter(tools.citations))
        selection['conflicts']=[{'topic':'demand','reason':'fixture','statement_a':eid,'statement_b':eid}]
        r,_=self.execute([batch(*self.reviews()),native('finish',selection),native('finish',finish())])
        self.assertEqual(r['validation_failures'][0]['error'],'conflict_requires_distinct_opposing_statements')
        self.assertEqual(r['conflicts'],[])

    def test_stale_sources_reject_before_any_catalog_or_provider_work(self):
        c={**self.case,'new':self.case['old']}
        r,a=self.execute([],case=c)
        self.assertEqual(r['calls'],0);self.assertFalse(a.sent)
        self.assertEqual(r['errors'],['stale_or_reversed_disclosure_pair'])

    def test_duplicate_native_ids_and_mixed_finish_are_rejected(self):
        reads=self.reviews()
        for response,expected in [(batch(reads[0],reads[0]),'invalid_or_duplicate_native_call_id'),
                                  (batch(reads[0],native('finish',finish(),'done')),'finish_must_be_submitted_alone')]:
            r,_=self.execute([response,batch(*reads),native('finish',finish())])
            self.assertEqual(r['validation_failures'][0]['error'],expected)
            self.assertEqual(sum(t['stage']=='tool_call' for t in r['trace']),4)

    def test_new_preflight_rejects_prior_approval_and_fits_full_b_requests(self):
        import importlib.util
        import tempfile
        spec=importlib.util.spec_from_file_location('runner_v5',ROOT/'scripts/earnings_protocol_v5.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'bundle'
            estimate=runner.prepare(folder)
            _,jobs,config=runner.check(folder)
            self.assertEqual(len(jobs),16)
            self.assertEqual(estimate['planned_method_runs'],32)
            self.assertEqual(estimate['maximum_model_requests'],108)
            self.assertTrue(json.loads((folder/'initial_request_sizes.json').read_text())['all_initial_requests_fit'])
            with self.assertRaisesRegex(ValueError,'this_frozen_experiment'):
                runner.approved_cap(folder,ROOT/'reports/earnings-v4-preflight-2026-10-15/approval.json',config)


if __name__=='__main__':unittest.main()
