import json
from dataclasses import replace
from pathlib import Path
import unittest
from eventlens.core import Source, digest, load_corpus
from eventlens.pipeline import run_pair
from eventlens.document_diff import sentences
from eventlens.corpus import normalize_capture

ROOT=Path(__file__).resolve().parents[1]


def pair(old, new, horizon='FY2025'):
    sources={sid:Source(sid,'TEST','https://example.org/'+sid,date,date,'2026-10-13T00:00:00Z',
                       'FY2025-Q1',['FY2025','FY2026'],text,digest(text))
             for sid,date,text in [('old','2025-01-01T00:00:00Z',old),('new','2025-04-01T00:00:00Z',new)]}
    case=dict(case_id='test',issuer='TEST',old='old',new='new',horizon=horizon,metric='revenue',
              cutoff='2025-04-02T00:00:00Z',split='development',synthetic=True)
    return run_pair(sources,case,'D')


class DocumentDiffTests(unittest.TestCase):
    def test_real_development_adobe(self):
        _,sources=load_corpus(ROOT/'data/manifest.json')
        case=json.loads((ROOT/'data/cases.json').read_text())[0]
        r=run_pair(sources,case,'D')
        self.assertEqual(r['comparison']['calculation']['midpoint_delta'],'125000000.00')
        self.assertEqual(r['calls'],0)
        self.assertEqual(r['trace'][0]['selected_alignment'],'replace')

    def test_prose_and_one_sided_range_change(self):
        r=pair('For fiscal year 2025, we expect total revenue of $10 million to $12 million.',
               'For fiscal year 2025, we expect total revenue of $11 million to $12 million.')
        self.assertEqual(r['comparison']['reason'],'raised')
        self.assertEqual(r['comparison']['calculation']['midpoint_delta'],'500000')
        for x in r['extractions']:self.assertEqual(x['validation']['errors'],[])

    def test_rpo_headline_is_not_a_revenue_forecast(self):
        r=pair('Fiscal year 2025 guidance\nTotal revenue $10 million to $12 million',
               'Raises fiscal year 2025 revenue targets\nCompany reports record revenue and RPO surpasses $20 billion')
        self.assertEqual(r['conclusion'],'insufficient_evidence')

    def test_equal_guidance_with_changed_other_numbers(self):
        s='Fiscal year 2025 guidance\nTotal revenue $10 million to $12 million\n'
        r=pair(s+'Cash $40 million',s+'Cash $80 million')
        self.assertEqual(r['comparison']['reason'],'unchanged')
        self.assertEqual(r['trace'][0]['selected_alignment'],'equal')

    def test_quarterly_and_actual_values_do_not_substitute(self):
        old='Fiscal year 2025 guidance\nTotal revenue $10 million to $12 million'
        for new in ['First quarter fiscal year 2025 guidance\nTotal revenue $1 million to $2 million',
                    'Fiscal year 2025 results\nTotal revenue $11 million',
                    'Fiscal year 2026 guidance\nTotal revenue $11 million to $12 million']:
            with self.subTest(new=new):self.assertEqual(pair(old,new)['conclusion'],'insufficient_evidence')

    def test_multiple_columns_abstain(self):
        s='Fiscal year 2025 guidance\nTotal revenue $10 million to $12 million | $11 million to $13 million'
        self.assertEqual(pair(s,s)['conclusion'],'insufficient_evidence')

    def test_competing_ranges_abstain(self):
        s='Fiscal year 2025 guidance\nTotal revenue $10 million to $12 million\nTotal revenue $15 million to $16 million'
        self.assertEqual(pair(s,s)['conclusion'],'insufficient_evidence')

    def test_units_normalize_without_false_revision(self):
        r=pair('Fiscal year 2025 guidance\nTotal revenue $1 billion to $2 billion',
               'Fiscal year 2025 guidance\nTotal revenue $1000 million to $2000 million')
        self.assertEqual(r['comparison']['reason'],'unchanged')

    def test_withdrawal_has_no_invented_bounds(self):
        r=pair('Fiscal year 2025 guidance\nTotal revenue $1 billion to $2 billion',
               'For fiscal year 2025, we withdraw revenue guidance.')
        self.assertEqual(r['comparison']['reason'],'guidance_withdrawn')
        self.assertIsNone(r['comparison']['calculation'])

    def test_sentence_offsets_and_decimals(self):
        text='We expect $2.25 billion. This is guidance.\nRevenue | $1.5 to $2.0 billion'
        parts=sentences(text)
        self.assertEqual(len(parts),3)
        for part in parts:self.assertEqual(text[part.start:part.end],part.text)

    def test_stale_pair_gates_diff(self):
        _,sources=load_corpus(ROOT/'data/manifest.json')
        c=json.loads((ROOT/'data/cases.json').read_text())[0]
        r=run_pair(sources,{**c,'old':c['new'],'new':c['old']},'D')
        self.assertEqual(r['comparison']['reason'],'stale_or_reversed_disclosure_pair')
        self.assertFalse(any(t['stage']=='document_diff' for t in r['trace']))


class CorpusCaptureTests(unittest.TestCase):
    def test_rebuild_all_captures_and_hashes(self):
        audit=json.loads((ROOT/'data/capture_audit_v2.json').read_text())
        self.assertGreaterEqual(len(audit),40)
        for row in audit:
            p=ROOT/'data'/row['raw_capture']
            self.assertEqual(digest(p.read_bytes()),row['raw_sha256'])
            text,coverage=normalize_capture(json.loads(p.read_text()))
            self.assertEqual(digest(text),row['content_hash'])
            self.assertTrue(coverage['complete'])

    def test_missing_conflicting_or_wrong_url_captures_rejected(self):
        base='https://example.org Total lines: 2\nL0: first\nL1: second'
        for pages in [[base.replace('L1: second','')], [base,base.replace('second','changed')],
                      [base.replace('example.org','other.org')]]:
            with self.assertRaises(ValueError):normalize_capture({'url':'https://example.org','pages':pages})

    def test_split_and_quarter_adjacency(self):
        cases=json.loads((ROOT/'data/cases.json').read_text())
        split=json.loads((ROOT/'configs/corpus_v2_split.json').read_text())
        self.assertGreaterEqual(len(cases),30)
        self.assertGreaterEqual(len({c['issuer'] for c in cases}),12)
        self.assertFalse(set(split['development_issuers']) & set(split['heldout_issuers']))
        pairs=set()
        for c in cases:
            self.assertIn(c['issuer'],split[c['split']+'_issuers'])
            old,new=[c[k].removesuffix('-SEC').split('-') for k in ['old','new']]
            a=int(old[1])*4+int(old[2][1:]);b=int(new[1])*4+int(new[2][1:])
            self.assertEqual(b-a,1)
            identity=(c['issuer'],a,b)
            self.assertNotIn(identity,pairs);pairs.add(identity)
