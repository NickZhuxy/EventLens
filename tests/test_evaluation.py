import contextlib
import io
import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from eventlens.core import load_corpus
from eventlens.pipeline import run_pair
from eventlens.evaluation import score
from eventlens.cli import main

ROOT=Path(__file__).resolve().parents[1]

class EvaluationTests(unittest.TestCase):
    def test_real_draft_denominators(self):
        _,sources=load_corpus(ROOT/'data/manifest.json')
        cases=json.loads((ROOT/'data/cases.json').read_text())
        labels=json.loads((ROOT/'data/labels.draft.json').read_text())
        results=score([run_pair(sources,c) for c in cases],labels)
        heldout=next(x for x in results if x['split']=='heldout')
        self.assertEqual(heldout['extraction_true_positive'],2)
        self.assertEqual(heldout['extraction_false_negative'],2)
        self.assertEqual(heldout['numerically_scored_comparisons'],1)
        self.assertEqual(heldout['abstentions'],1)
        self.assertIsNone(heldout['human_evidence_support_errors'])
        self.assertTrue(heldout['provisional'])

    def test_false_values_count_as_error_not_just_literal_success(self):
        _,sources=load_corpus(ROOT/'data/manifest.json')
        case=json.loads((ROOT/'data/cases.json').read_text())[0]
        labels=json.loads((ROOT/'data/labels.draft.json').read_text())
        run=run_pair(sources,case)
        run['extractions'][0]['metric']['lower']='23.40'
        run['comparison']['calculation']['midpoint_delta']='999'
        s=score([run],labels)[0]
        self.assertEqual(s['extraction_false_positive'],1)
        self.assertEqual(s['extraction_false_negative'],1)
        self.assertEqual(s['numerical_comparison_errors'],1)

    def test_human_label_status_requires_provenance(self):
        labels=json.loads((ROOT/'data/labels.draft.json').read_text());labels['status']='human_reviewed'
        with self.assertRaises(ValueError):score([],labels)

    def test_validate_cli(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):rc=main(['--root',str(ROOT),'validate'])
        self.assertEqual(rc,0)
        self.assertEqual(json.loads(output.getvalue())['eligible_comparisons'],3)

    def test_live_requires_model_and_key(self):
        from unittest.mock import patch
        output=io.StringIO()
        with patch.dict('os.environ',{},clear=True),contextlib.redirect_stderr(output):
            rc=main(['--root',str(ROOT),'compare','--case','ADBE-FY2025-Q2-Q3','--method','B'])
        self.assertEqual(rc,2)
        self.assertIn('model identifier',output.getvalue())

    def test_path_traversal_and_tampered_source_rejected(self):
        manifest=json.loads((ROOT/'data/manifest.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json'
            manifest['sources'][0]['path']='../outside.txt'
            p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'outside manifest'):load_corpus(p)

    def test_synthetic_emissions_are_counted_but_not_falsely_scored(self):
        from eventlens.challenges import make_challenges
        _,sources=load_corpus(ROOT/'data/manifest.json')
        case=json.loads((ROOT/'data/cases.json').read_text())[0]
        labels=json.loads((ROOT/'data/labels.draft.json').read_text())
        runs=[run_pair(d,c) for d,c in make_challenges(sources,case)]
        summary=score(runs,labels)[0]
        self.assertEqual(summary['case_count'],9)
        self.assertEqual(summary['status_correct'],9)
        self.assertEqual(summary['emitted_numerical_comparisons'],2)
        self.assertEqual(summary['numerically_scored_comparisons'],0)
        self.assertIsNone(summary['numerical_comparison_errors'])
        self.assertEqual(summary['appropriate_abstentions'],6)

if __name__=='__main__':unittest.main()

class ConfiguredContextTests(unittest.TestCase):
    def test_every_real_pair_fits_single_pass_context_budget(self):
        from eventlens.llm import MockAdapter
        _,sources=load_corpus(ROOT/'data/manifest.json')
        config=json.loads((ROOT/'configs/model.json').read_text())
        for case in json.loads((ROOT/'data/cases.json').read_text()):
            with self.subTest(case=case['case_id']):
                r=run_pair(sources,case,'B',MockAdapter([{'action':'finish','metrics':[None,None],'explanations':[]}]),config)
                self.assertEqual(r['calls'],1)
                self.assertEqual(r['errors'],[])
                self.assertEqual(r['context_characters'],sum(len(sources[case[k]].text) for k in ['old','new']))
