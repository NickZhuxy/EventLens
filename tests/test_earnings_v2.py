"""Evidence boundaries, independent controls, budget reservation and reviewer provenance."""
from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
import json
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from eventlens.core import load_corpus, digest
from eventlens.extraction import extract
from eventlens.llm import MockAdapter, ProviderSettings
from eventlens.investigation import citation, explicit_conflicts, run_investigation, validate_conflicts
from eventlens.benchmark import BudgetJournal, RecordedAdapter, population, stable, summary
from eventlens.review import validate_export

ROOT=Path(__file__).resolve().parents[1]
CONFIG={'model':'fixture','max_calls':8,'max_tool_calls':7,'max_output_tokens_per_call':3200,'max_input_characters':180000}


class EarningsV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.sources=load_corpus(ROOT/'data/manifest.json')
        cls.cases=json.loads((ROOT/'data/cases.json').read_text());cls.case=cls.cases[0]

    def test_heldout_controls_do_not_require_successful_rule_extraction(self):
        sources,jobs=population(self.sources,self.cases)
        self.assertEqual(len(jobs),110)
        controls=[c for c in jobs if c.get('synthetic')]
        self.assertEqual(len(controls),72)
        self.assertEqual(len({c['parent_case_id'] for c in controls}),24)
        for c in controls:
            if c['challenge']=='missing_table':
                self.assertNotRegex(sources[c['new']].text,r'\d')
                self.assertTrue(c['transformation']['removed_spans'])
            if c['challenge']=='contradictory_commentary':
                for q in c['transformation']['expected_conflict_quotes']:self.assertIn(q,sources[c['new']].text)

    def test_stale_pair_never_touches_paid_adapter(self):
        adapter=Mock();case={**self.case,'new':self.case['old']}
        result=run_investigation(self.sources,case,'C',CONFIG,adapter)
        self.assertEqual(result['calls'],0);adapter.complete.assert_not_called()

    def test_controller_retrieves_two_opposing_spans_and_replays(self):
        source=self.sources[self.case['new']]
        a='Demand caused the FY2025 total revenue guidance revision on a reported basis.'
        b='Demand did not cause the FY2025 total revenue guidance revision on a reported basis.'
        text=source.text+'\n'+a+'\n'+b
        source=replace(source,text=text,content_hash=digest(text),snapshot_kind='SYNTHETIC test')
        data={**self.sources,source.source_id:source}
        replies=[{'action':'tool','name':'get_source','arguments':{'source_id':source.source_id,'start':len(text)-len(a)-len(b)-1,'end':len(text)},'reason':'Inspect both opposing statements'},
                 {'action':'finish','metrics':[None,None],'explanations':[], 'conflicts':[{'topic':'demand','reason':'Same horizon and basis, opposite assertion','statement_a':{'source_id':source.source_id,'quote':a},'statement_b':{'source_id':source.source_id,'quote':b}}]}]
        run=run_investigation(data,self.case,'C',CONFIG,MockAdapter(replies))
        self.assertEqual(run['conclusion'],'conflicting');self.assertEqual(run['calls'],2)
        self.assertEqual(len(run['conflicts'][0]['citations']),2)
        self.assertTrue(all(c['literal_valid'] and c['origin']=='synthetic' for c in run['conflicts'][0]['citations']))
        replay=run_investigation(data,self.case,'C',CONFIG,RecordedAdapter(run))
        self.assertEqual(stable(run),stable(replay))

    def test_controller_cannot_cite_unretrieved_source_text(self):
        s=self.sources[self.case['new']];q=s.text[:100]
        response={'action':'finish','metrics':[None,None],'explanations':[{'source_id':s.source_id,'quote':q}]}
        run=run_investigation(self.sources,self.case,'C',CONFIG,MockAdapter([response]))
        self.assertIn('citation_not_in_retrieved_context',run['errors']);self.assertFalse(run['explanations'])

    def test_conflict_rejects_identical_or_unseen_statements(self):
        sid=self.case['new'];s=self.sources[sid];q={'source_id':sid,'quote':s.text[:40]}
        c={'topic':'x','reason':'x','statement_a':q,'statement_b':q}
        with self.assertRaisesRegex(ValueError,'distinct'):validate_conflicts([c],{sid:s},{sid:[s.text]})
        with self.assertRaisesRegex(ValueError,'retrieved'):validate_conflicts([c],{sid:s},{sid:[]})

    def test_basis_or_horizon_difference_is_not_lexical_conflict(self):
        a='Demand caused the FY2025 revenue guidance revision on a reported basis.'
        b='Demand did not cause the FY2025 revenue guidance revision on a constant currency basis.'
        source=self.sources[self.case['new']];text=a+'\n'+b
        s=replace(source,text=text,content_hash=digest(text))
        claims=[{'source_id':s.source_id,'quote':q} for q in (a,b)]
        self.assertEqual(explicit_conflicts(claims,{s.source_id:s}),[])

    def test_missing_numerical_evidence_abstains_for_frozen_baselines(self):
        sources,jobs=population(self.sources,self.cases)
        case=next(c for c in jobs if c.get('challenge')=='missing_table')
        for method in ('A','D'):
            run=run_investigation(sources,case,method,CONFIG)
            self.assertEqual(run['conclusion'],'insufficient_evidence');self.assertIsNone(run['comparison']['calculation'])

    def test_provisional_outputs_have_no_accuracy(self):
        run=run_investigation(self.sources,self.case,'A',CONFIG)
        measured=summary([run])[0]
        self.assertEqual(measured['human_reviewed_cases'],0)
        for name in ('revision_precision','revision_recall','direction_accuracy','numeric_exact_match_rate'):
            self.assertIsNone(measured[name])


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Mock();self.adapter.model='fixture';self.adapter.kind='mock'
        self.adapter.settings=ProviderSettings('https://api.deepseek.com','low')
        self.adapter.complete.return_value={'usage':{'prompt_tokens':10,'completion_tokens':5},'choices':[]}
        self.pricing={'input_per_million':'0.30','output_per_million':'1.20'}
        self.messages=[{'role':'user','content':'fixture'}]
    def journal(self,cap):return BudgetJournal(Path(self.temp.name),self.adapter,cap,self.pricing).bind('case_B')

    def test_denies_before_spending_and_preserves_empty_ledger(self):
        journal=self.journal('0.000001')
        with self.assertRaisesRegex(RuntimeError,'budget_exhausted'):journal.complete(self.messages,3200)
        self.adapter.complete.assert_not_called();self.assertEqual(journal.spent(),0)

    def test_resume_uses_identical_saved_response_without_repayment(self):
        first=self.journal('1');response=first.complete(self.messages,3200);cost=first.spent()
        second=self.journal('1');self.assertEqual(second.complete(self.messages,3200),response)
        self.assertEqual(self.adapter.complete.call_count,1);self.assertEqual(second.spent(),cost)
        self.assertEqual(cost,Decimal('0.000009'))
        with self.assertRaisesRegex(ValueError,'request_changed'):
            self.journal('1').complete([{'role':'user','content':'different'}],3200)

    def test_uncertain_failure_keeps_reservation_and_cannot_auto_retry(self):
        self.adapter.complete.side_effect=RuntimeError('test transport failure')
        journal=self.journal('1')
        with self.assertRaisesRegex(RuntimeError,'reservation retained'):journal.complete(self.messages,3200)
        self.assertGreater(journal.spent(),0)
        with self.assertRaisesRegex(RuntimeError,'no automatic retry'):self.journal('1').complete(self.messages,3200)
        self.assertEqual(self.adapter.complete.call_count,1)


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        _,self.sources=load_corpus(ROOT/'data/manifest.json');self.case=json.loads((ROOT/'data/cases.json').read_text())[0]
        metrics=[asdict(extract(self.sources[self.case[k]],self.case['horizon'])[0]) for k in ('old','new')]
        self.label={'schema':'eventlens-review-v2','source_hashes':{sid:self.sources[sid].content_hash for sid in sorted(self.case[k] for k in ('old','new'))},
                    'cases':{self.case['case_id']:{'review_status':'reviewed','human_attestation':True,'reviewed_by':'Synthetic test reviewer',
                        'reviewed_at':'2026-10-13T00:00:00+00:00','direction':'raised','metrics':metrics,
                        'explanation_status':'none_found','explanation_conflict':'no','explanations':[],
                        'notes':'Synthetic unit-test review only; never persisted as Nick ground truth.'}}}
    def test_review_requires_attestation_identity_and_timestamp(self):
        for key,value in [('human_attestation',False),('reviewed_by',''),('reviewed_at',None)]:
            x=deepcopy(self.label);x['cases'][self.case['case_id']][key]=value
            with self.assertRaises(ValueError):validate_export(x,self.sources,[self.case])
    def test_validated_labels_derive_exact_values_in_python(self):
        result=validate_export(self.label,self.sources,[self.case]);row=result['cases'][self.case['case_id']]
        self.assertEqual(Decimal(row['expected_midpoint_delta_usd']),Decimal(125000000))
        run=run_investigation(self.sources,self.case,'A',CONFIG)
        self.assertEqual(summary([run],result)[0]['numeric_exact_match_rate'],1)
    def test_rejects_wrong_source_hash_nonliteral_quote_or_wrong_direction(self):
        for mode in ('hash','quote','direction'):
            x=deepcopy(self.label);row=x['cases'][self.case['case_id']]
            if mode=='hash':x['source_hashes'][self.case['old']]='0'*64
            elif mode=='quote':row['metrics'][0]['evidence']='invented'
            else:row['direction']='lowered'
            with self.assertRaises(ValueError):validate_export(x,self.sources,[self.case])

@unittest.skipUnless(shutil.which('node'), 'Node is optional for pure browser-validation checks')
class ReviewPageTests(unittest.TestCase):
    def test_browser_validation_agrees_with_review_gate(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        import earnings_review
        result=subprocess.run(['node',str(ROOT/'tests/review_page_checks.cjs')],
                              input=json.dumps({'page':earnings_review.PAGE,'data':earnings_review.payload()}),
                              text=True,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
