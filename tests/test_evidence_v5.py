"""Source/column binding tests; synthetic cases are not human ground truth."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from eventlens.core import Source, digest, compare
from eventlens.evidence_v5 import EvidenceTools, guidance_catalog, explanation_catalog

ROOT=Path(__file__).resolve().parents[1]
TABLE='''Second Quarter and Full Fiscal Year 2025 Financial Targets
(in millions except per share amounts)
 | Range for Three Months Ending | Range for Fiscal Year Ending |
 | April 30, 2025 | October 31, 2025 |
 | Low | High | Low | High |
Revenue | $ | 100 | $ | 110 | $ | 500 | $ | 550 |
'''


def source(text=TABLE, sid='TEST-new', horizon='FY2025'):
    return Source(sid,'TEST','https://example.org/disclosure','2025-05-01T00:00:00Z',
                  '2025-05-01T00:00:00Z','2025-05-02T00:00:00Z','FY2025-Q2',
                  [horizon],text,digest(text),'SYNTHETIC test fixture')


class EvidenceV5Tests(unittest.TestCase):
    def test_annual_columns_not_quarterly_and_exact_offsets(self):
        s=source(TABLE.replace('Range for Fiscal','Range\u00a0for\u00a0Fiscal'))
        found=guidance_catalog(s,'FY2025')
        self.assertEqual(len(found),1)
        c=found[0];self.assertEqual((c['metric']['lower'],c['metric']['upper']),('500','550'))
        for k in ('heading','period','date','unit','row','lower_cell','upper_cell'):
            p=c['proof'][k];self.assertEqual(s.text[p['start']:p['end']],p['quote'])
            self.assertEqual(p['source_hash'],s.content_hash)
        self.assertIn('\u00a0',c['proof']['period']['quote'])

    def test_annual_group_can_precede_quarterly_group(self):
        t=TABLE.replace('Range for Three Months Ending | Range for Fiscal Year Ending',
                        'Range for Fiscal Year Ending | Range for Three Months Ending')
        t=t.replace('April 30, 2025 | October 31, 2025','October 31, 2025 | April 30, 2025')
        c=guidance_catalog(source(t),'FY2025')[0]
        self.assertEqual(c['metric']['lower'],'100')
        self.assertEqual(c['proof']['group_index'],0)

    def test_ambiguous_columns_missing_units_currency_year_or_headers_abstain(self):
        variants=[TABLE.replace(' | High | Low |',' | Low | Low |'),
                  TABLE.replace('Fiscal Year','Three Months'),
                  TABLE.replace('October 31, 2025','October 31, 2024'),
                  TABLE.replace('(in millions except per share amounts)',''),
                  TABLE.replace('$ | 500','EUR | 500'),
                  TABLE.replace(' | $ | 550',''),
                  TABLE.replace('500 | $ | 550','600 | $ | 550'),
                  TABLE.replace('Revenue |','Segment Revenue |'),
                  TABLE.replace('Financial Targets','Actual Results'),
                  TABLE.replace('Financial Targets','Financial Targets (Canadian dollars)'),
                  TABLE.replace('Fiscal Year Ending','Fiscal Year Ending (constant currency)'),
                  TABLE.replace('Second Quarter and Full','Constant currency Full'),
                  TABLE.replace(' | April 30, 2025 | October 31, 2025 |\n',''),
                  TABLE.replace(' | Low | High | Low | High |',' | Estimated |\n | Low | High | Low | High |')]
        for text in variants:
            with self.subTest(text=text):self.assertEqual(guidance_catalog(source(text),'FY2025'),[])
        self.assertEqual(guidance_catalog(source(),'FY2024'),[])

    def test_unit_conversion_is_deterministic(self):
        a=guidance_catalog(source(),'FY2025')[0]
        b=guidance_catalog(source(TABLE.replace('millions','billions').replace('500 | $ | 550','0.500 | $ | 0.550')),'FY2025')[0]
        from eventlens.core import Metric
        self.assertEqual(compare(Metric(**a['metric']),Metric(**b['metric']))['reason'],'unchanged')

    def test_competing_current_ranges_cannot_be_silently_selected(self):
        s=source(TABLE+'\n'+TABLE.replace('500 | $ | 550','600 | $ | 650'))
        tools=EvidenceTools({s.source_id:s},[s.source_id],'2025-06-01T00:00:00Z','FY2025')
        out=tools.execute('inspect_guidance',{'source_id':s.source_id});tools.publish(out)
        self.assertTrue(out['ambiguous'])
        with self.assertRaisesRegex(ValueError,'ambiguous_guidance'):
            tools.resolve_metric(out['metric_candidates'][0]['metric_id'])

    def test_registry_rejects_unseen_foreign_and_tampered_references(self):
        s=source();tools=EvidenceTools({s.source_id:s},[s.source_id],'2025-06-01T00:00:00Z','FY2025')
        out=tools.execute('inspect_guidance',{'source_id':s.source_id})
        mid=out['metric_candidates'][0]['metric_id'];eid=out['metric_candidates'][0]['evidence']['evidence_id']
        with self.assertRaisesRegex(ValueError,'not_in_retrieved'):tools.resolve_metric(mid)
        with self.assertRaisesRegex(ValueError,'not_in_retrieved'):tools.resolve_citation(eid)
        with self.assertRaisesRegex(ValueError,'outside allowed'):tools.execute('inspect_guidance',{'source_id':'foreign'})
        tools.publish(out);tools.resolve_metric(mid)
        tools.visible_metrics[mid]['metric']['lower']='999'
        with self.assertRaisesRegex(ValueError,'registry_mismatch'):tools.resolve_metric(mid)

    def test_source_hash_and_cutoff_change_visibility(self):
        a=source();b=source(TABLE+'\n')
        self.assertNotEqual(guidance_catalog(a,'FY2025')[0]['metric_id'],guidance_catalog(b,'FY2025')[0]['metric_id'])
        t=EvidenceTools({a.source_id:a},[a.source_id],'2025-04-01T00:00:00Z','FY2025')
        with self.assertRaisesRegex(ValueError,'outside allowed'):t.execute('inspect_guidance',{'source_id':a.source_id})

    def test_whole_source_explanation_search_recovers_tail_and_paraphrases(self):
        examples=['Currency effects caused the FY2025 revenue guidance change.',
                  'Currency effects did not cause the FY2025 revenue guidance change.',
                  'The FY2025 revenue outlook increase is attributable to pricing.',
                  'The FY2025 revenue outlook increase is not attributable to pricing.']
        s=source(('Revenue guidance fiscal annual table details.\n'*1000)+'\n'.join(examples))
        returned={x['quote'] for x in explanation_catalog(s,'FY2025')}
        self.assertTrue(set(examples)<=returned)
        self.assertNotIn('conflicts',explanation_catalog(s,'FY2025')[0])

    def test_known_development_sources_and_four_conflict_controls(self):
        root=ROOT/'reports/earnings-v4-preflight-2026-10-15'
        sources={s['source_id']:Source(**s) for s in json.loads((root/'sources.json').read_text())}
        jobs=json.loads((root/'jobs.json').read_text())
        for job in jobs:
            for k in ('old','new'):
                found=guidance_catalog(sources[job[k]],job['horizon'])
                self.assertEqual(len(found),1,(job['case_id'],k))
            if job.get('synthetic'):
                quotes={c['quote'] for c in explanation_catalog(sources[job['new']],job['horizon'])}
                self.assertTrue(set(job['transformation']['expected_conflict_quotes'])<=quotes)

    def test_broad_numeric_mask_does_not_copy_old_guidance(self):
        import re
        s=source(re.sub(r'\d[\d,]*(?:\.\d+)?','[VALUE REMOVED]',TABLE))
        self.assertEqual(guidance_catalog(s,'FY2025'),[])

    def test_table_only_row_deletion_preserves_other_numbers_but_removes_candidate(self):
        # Isolated removal, unlike the earlier broad numeric mask. This is a
        # parser test, not a live-model table-only stress result.
        text=TABLE.replace('Revenue | $ | 100 | $ | 110 | $ | 500 | $ | 550 |\n','')
        text+='Actual quarterly revenue was $105 million.\n'
        self.assertIn('2025',text);self.assertIn('$105',text)
        self.assertEqual(guidance_catalog(source(text),'FY2025'),[])

    def test_different_basis_or_year_statements_remain_candidates_not_automatic_conflicts(self):
        text='Currency caused the FY2025 reported revenue guidance change.\n'
        text+='Currency did not cause the FY2024 constant-currency revenue outlook change.\n'
        found=explanation_catalog(source(text),'FY2025')
        self.assertEqual(len(found),2)
        self.assertTrue(all(x['semantic_review']=='pending' and 'conflict' not in x for x in found))


if __name__=='__main__':unittest.main()
