import json
from dataclasses import replace, asdict
from pathlib import Path
import tempfile
import unittest
from eventlens.core import Source, Metric, Store, compare, digest, load_corpus
from eventlens.extraction import extract, validate_evidence, explanation_status
from eventlens.pipeline import run_pair
from eventlens.retrieval import ReadTools
from eventlens.llm import MockAdapter, strict_json


def source(sid='old', text=None, date='2025-06-01T00:00:00Z'):
    text = text or 'Fiscal year 2025 targets\nTotal revenue | $1.0 billion to $2.0 billion\n'
    return Source(sid, 'TEST', 'https://issuer.example/disclosure', date, date,
                  '2026-10-07T00:00:00Z', 'FY2025-Q2', ['FY2025'], text, digest(text))


def pair():
    old = source()
    new = source('new', 'Fiscal year 2025 targets\nTotal revenue | $1.5 billion to $2.5 billion\n', '2025-09-01T00:00:00Z')
    case = dict(case_id='test', issuer='TEST', old='old', new='new', horizon='FY2025', metric='revenue', cutoff='2025-09-02T00:00:00Z', split='development', synthetic=True)
    return {'old':old,'new':new}, case


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.sources, self.case = pair()
        self.old, _ = extract(self.sources['old'], 'FY2025')
        self.new, _ = extract(self.sources['new'], 'FY2025')

    def test_decimal_arithmetic(self):
        self.assertEqual(compare(self.old, self.new)['calculation']['midpoint_delta'], '500000000.0')

    def test_million_billion_normalization(self):
        m = replace(self.new, unit='million', lower='1500', upper='2500')
        self.assertEqual(compare(self.old, m)['calculation']['new_midpoint'], '2000000000')

    def test_point_estimates(self):
        result = compare(replace(self.old, lower='2', upper='2'), replace(self.new, lower='3', upper='3'))
        self.assertEqual(result['calculation']['midpoint_delta'], '1000000000')

    def test_margin_is_percentage_points(self):
        a = replace(self.old, metric='operating_margin', currency=None, unit='percent', basis='non-GAAP', definition='operating_margin', lower='20', upper='22')
        b = replace(a, source_id='new', lower='21', upper='23')
        self.assertEqual(compare(a,b)['calculation']['midpoint_delta'], '1')
        self.assertEqual(compare(a,b)['calculation']['delta_unit'], 'percentage_points')

    def test_incompatible_fields(self):
        for attr, value in [('horizon','FY2026'), ('currency','EUR'), ('basis','non-GAAP'), ('definition','new_definition'), ('issuer','OTHER')]:
            with self.subTest(attr=attr):
                self.assertEqual(compare(self.old,replace(self.new,**{attr:value}))['reason'], 'incompatible_'+attr)

    def test_fiscal_calendar_mismatch(self):
        self.assertEqual(compare(self.old,replace(self.new,horizon='CY2025',calendar='calendar'))['status'],'insufficient_evidence')

    def test_missing_is_not_zero(self):
        self.assertIsNone(compare(self.old,None)['calculation'])
        with self.assertRaises(ValueError): replace(self.old,status='missing')

    def test_withdrawn(self):
        b=replace(self.new,status='withdrawn',lower=None,upper=None)
        self.assertEqual(compare(self.old,b)['reason'],'guidance_withdrawn')
        self.assertIsNone(compare(self.old,b)['calculation'])

    def test_unknown_basis(self):
        self.assertEqual(compare(replace(self.old,basis='unknown'),replace(self.new,basis='unknown'))['status'],'insufficient_evidence')

    def test_zero_denominator(self):
        self.assertIsNone(compare(replace(self.old,lower='0',upper='0'),self.new)['calculation']['relative_midpoint_change_percent'])

    def test_mixed_range_not_mislabeled_raise(self):
        self.assertEqual(compare(self.old,replace(self.new,lower='0.5',upper='3'))['reason'],'mixed_range')

    def test_malformed_values(self):
        for v in ['NaN','Infinity','bogus',None,True]:
            with self.subTest(v=v),self.assertRaises(ValueError): replace(self.old,lower=v)
        with self.assertRaises(ValueError): replace(self.old,lower='99')
        with self.assertRaises(ValueError): replace(self.old,unit='unknown')
        with self.assertRaises(ValueError): replace(self.old,horizon='FY25')

    def test_hash_and_dates(self):
        with self.assertRaises(ValueError): replace(self.sources['old'],text='changed')
        with self.assertRaises(ValueError): replace(self.sources['old'],published_at='2025-01-01')
        with self.assertRaises(ValueError): replace(self.sources['old'],available_at='2024-01-01T00:00:00Z')

    def test_idempotence_and_collision(self):
        with tempfile.TemporaryDirectory() as d:
            db=Store(Path(d)/'test.sqlite')
            try:
                self.assertTrue(db.ingest(self.sources['old']))
                self.assertFalse(db.ingest(self.sources['old']))
                with self.assertRaises(ValueError): db.ingest(source(text='different'))
                self.assertEqual(db.db.execute('select count(*) from sources').fetchone()[0],1)
                for _ in range(2): db.save_run(run_pair(self.sources,self.case))
                self.assertEqual(db.db.execute('select count(*) from runs').fetchone()[0],2)
            finally:db.close()

    def test_evidence_literal_and_semantic(self):
        self.assertEqual(validate_evidence(self.old,self.sources['old'])['semantic_screen'],'pass')
        bad=replace(self.old,lower='77',upper='78')
        self.assertIn('value_not_in_quote',validate_evidence(bad,self.sources['old'])['errors'])
        self.assertTrue(validate_evidence(bad,self.sources['old'])['literal_valid'])
        self.assertIn('nonliteral_evidence',validate_evidence(replace(self.old,evidence='invented'),self.sources['old'])['errors'])
        self.assertIn('unit_not_in_quote',validate_evidence(replace(self.old,unit='million'),self.sources['old'])['errors'])

    def test_quarterly_guidance_is_not_annual(self):
        s=source(text='Third quarter fiscal year 2025 targets\nTotal revenue | $1 billion to $2 billion\n')
        self.assertIsNone(extract(s,'FY2025')[0])
        m=replace(self.old,evidence=s.text.splitlines()[1],horizon_evidence=s.text)
        self.assertIn('quarterly_or_ambiguous_horizon',validate_evidence(m,s)['errors'])

    def test_missing_table(self):
        s=source(text='Fiscal year 2025 targets\n(table missing)\n')
        self.assertIsNone(extract(s,'FY2025')[0])

    def test_conflicting_ranges(self):
        s=source(text='Fiscal year 2025 targets\nTotal revenue | $1 billion to $2 billion\nTotal revenue | $3 billion to $4 billion\n')
        self.assertIn('conflicting_guidance_ranges',extract(s,'FY2025')[1])

    def test_cutoff_consistency(self):
        tools=ReadTools(self.sources,['old','new'],'2025-07-01T00:00:00Z')
        with self.assertRaises(ValueError): tools.execute('search_passages',dict(source_id='new',query='revenue'))
        with self.assertRaises(ValueError): tools.execute('get_source',dict(source_id='new',start=0,end=10))
        self.assertEqual(run_pair(self.sources,{**self.case,'cutoff':'2025-07-01T00:00:00Z'})['comparison']['reason'],'source_after_cutoff')
        self.assertEqual(run_pair(self.sources,self.case,cutoff_mode='snapshot')['comparison']['reason'],'source_after_cutoff')

    def test_stale_reversed_pair(self):
        self.assertEqual(run_pair(self.sources,{**self.case,'old':'new','new':'old'})['comparison']['reason'],'stale_or_reversed_disclosure_pair')

    def test_read_only_tool_validation(self):
        t=ReadTools(self.sources,['old','new'],self.case['cutoff'])
        for name,args in [('shell',{'command':'rm'}),('get_source',{'source_id':'../secret','start':0,'end':1}),('get_source',{'source_id':'old','start':False,'end':1}),('search_passages',{'source_id':'old','query':'x','cutoff':'2099'})]:
            with self.subTest(name=name),self.assertRaises(ValueError):t.execute(name,args)
        r=t.execute('search_passages',dict(source_id='old',query='revenue'))
        self.assertIn('Total revenue',r['passages'][0]['quote'])

    def test_contradictory_explanations(self):
        claims=[dict(quote='Demand drove the raised guidance.'),dict(quote='Demand did not cause the raised guidance.')]
        self.assertEqual(explanation_status(claims)['status'],'conflicting')

    def test_mock_single_pass_not_live(self):
        adapter=MockAdapter([dict(action='finish',metrics=[asdict(self.old),asdict(self.new)],explanations=[])])
        r=run_pair(self.sources,self.case,'B',adapter)
        self.assertEqual(r['execution_kind'],'mock')
        self.assertEqual(r['calls'],1)
        self.assertIsNone(r['tokens'])
        self.assertEqual(r['comparison']['reason'],'raised')

    def test_mock_controller_uses_real_tools(self):
        replies=[dict(action='tool',name='search_passages',arguments=dict(source_id=sid,query='fiscal year 2025 total revenue'),reason='Find annual targets') for sid in ['old','new']]
        replies += [dict(action='finish',metrics=[asdict(self.old),asdict(self.new)],explanations=[])]
        r=run_pair(self.sources,self.case,'C',MockAdapter(replies))
        self.assertEqual(r['calls'],3)
        self.assertEqual(sum(t['stage']=='tool_call' for t in r['trace']),2)
        self.assertEqual(r['comparison']['reason'],'raised')

    def test_controller_cannot_cite_unseen_text(self):
        r=run_pair(self.sources,self.case,'C',MockAdapter([dict(action='finish',metrics=[asdict(self.old),asdict(self.new)])]))
        self.assertIn('citation_not_in_supplied_context',r['errors'])
        self.assertEqual(r['conclusion'],'insufficient_evidence')

    def test_controller_budget(self):
        replies=[dict(action='tool',name='search_passages',arguments=dict(source_id='old',query='revenue'))]*3
        r=run_pair(self.sources,self.case,'C',MockAdapter(replies),{'max_calls':2,'max_tool_calls':1})
        self.assertEqual(r['calls'],2)
        self.assertEqual(r['conclusion'],'insufficient_evidence')

    def test_invalid_model_output_preserved(self):
        r=run_pair(self.sources,self.case,'B',MockAdapter([dict(action='finish',metrics=[])]))
        self.assertTrue(r['errors'])
        self.assertIn('raw_response',r['trace'][0])

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):strict_json('{"a":1,"a":2}')


if __name__=='__main__':unittest.main()

class EndToEndChallengeTests(unittest.TestCase):
    def test_development_controls(self):
        from eventlens.challenges import make_challenges
        root=Path(__file__).resolve().parents[1]
        _,sources=load_corpus(root/'data/manifest.json')
        case=json.loads((root/'data/cases.json').read_text())[0]
        for data,c in make_challenges(sources,case):
            with self.subTest(case=c['case_id']):
                r=run_pair(data,c)
                self.assertEqual(r['conclusion'],c['expected_status'])
                if c['case_id'].endswith('prompt_injection'):
                    self.assertEqual(r['comparison']['calculation']['midpoint_delta'],'125000000.00')
