"""Human-review gates must not turn drafts or altered evidence into scored facts."""
from copy import deepcopy
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('semantic_review',Path(__file__).resolve().parents[1]/'scripts/review_earnings_explanations.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


class SemanticReviewTests(unittest.TestCase):
    def fixture(self):
        rows={}
        for i in range(3):
            rows[str(i)]={'evidence':{'method':'C','kind':'explanation','quote':f'Exact source quotation {i}'},
                'decision':'pending','human_attestation':False,'reviewed_by':None,'reviewed_at':None,'notes':''}
        return {'schema':'test','bundle_hashes_sha256':'frozen-example',
            'allowed_decisions':['pending','supported','unsupported','uncertain'],
            'population':[{'method':'C','kind':'explanation','eligible_candidates':9,'sampled_candidates':3}],
            'reviews':rows}

    def approve(self,item,decision):
        item.update(decision=decision,human_attestation=True,reviewed_by='Synthetic fixture reviewer',
                    reviewed_at='2026-10-13T20:00:00-04:00',notes='Test fixture only; never persisted as real review.')

    def test_pending_is_never_ground_truth_and_uncertain_stays_in_denominator(self):
        expected=self.fixture();draft=deepcopy(expected)
        result=review.score(draft,expected)['metrics'][0]
        self.assertEqual(result['reviewed_candidates'],0)
        self.assertIsNone(result['supported_rate_among_reviewed'])
        self.approve(draft['reviews']['0'],'supported');self.approve(draft['reviews']['1'],'uncertain')
        result=review.score(draft,expected)['metrics'][0]
        self.assertEqual((result['reviewed_candidates'],result['pending'],result['supported_rate_among_reviewed']),(2,1,0.5))

    def test_judgment_requires_personal_attestation_and_a_dated_explanation(self):
        expected=self.fixture()
        for field,value in [('human_attestation',False),('reviewed_by',''),('notes',''),('reviewed_at','2026-10-13T20:00:00')]:
            with self.subTest(field=field):
                draft=deepcopy(expected);self.approve(draft['reviews']['0'],'supported');draft['reviews']['0'][field]=value
                with self.assertRaises(ValueError):review.score(draft,expected)

    def test_changed_evidence_or_dropped_candidates_cannot_improve_the_score(self):
        expected=self.fixture();draft=deepcopy(expected)
        draft['reviews']['0']['evidence']['quote']='A different statement'
        with self.assertRaisesRegex(ValueError,'evidence differs'):review.score(draft,expected)
        draft=deepcopy(expected);del draft['reviews']['0']
        with self.assertRaisesRegex(ValueError,'inventory differs'):review.score(draft,expected)

    def test_zero_emission_methods_remain_visible_without_a_support_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle=Path(folder);hashes={}
            for name in ('sources.json','jobs.json','review_queue.json'):
                (bundle/name).write_text('[]\n');hashes[name]=hashlib.sha256((bundle/name).read_bytes()).hexdigest()
            (bundle/'bundle_hashes.json').write_text(json.dumps(hashes))
            expected=review.template(bundle);result=review.score(expected,expected)
            self.assertEqual({m['method'] for m in result['metrics']},set('ABCD'))
            self.assertEqual(len(result['metrics']),8)
            self.assertTrue(all(m['sampled_candidates']==0 and m['supported_rate_among_reviewed'] is None for m in result['metrics']))


if __name__=='__main__':unittest.main()
