"""Legacy macro replay permits named earnings changes, never shared-code drift."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('macro_replay',ROOT/'scripts/verify_live_run.py')
# The fresh verification project historically copied data/code but not scripts.
# Normal repository/CI tests exercise these replay checks.


@unittest.skipUnless((ROOT/'scripts/verify_live_run.py').exists(),'script absent in legacy copied-project verification')
class ReplayGuardTests(unittest.TestCase):
    def setUp(self):
        self.module=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(self.module)
        self.bundle=ROOT/'reports/deepseek-live-2026-10-08'

    def test_earnings_exception_replays_all_saved_model_responses(self):
        result=self.module.verify(self.bundle,allow_earnings_changes=True)
        self.assertTrue(result['success'])
        self.assertEqual(result['paid_model_calls'],0)
        self.assertEqual(result['recorded_model_responses'],5)
        self.assertEqual(set(result['unrelated_earnings_code_changes']),{'cli.py','evaluation.py','pipeline.py'})

    def test_strict_mode_still_rejects_changed_earnings_code(self):
        with self.assertRaisesRegex(AssertionError,'package differs'):
            self.module.verify(self.bundle)

    def test_exception_does_not_allow_shared_model_adapter_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)
            for name in ['run.json','job.json','sources.json']:
                data=json.loads((self.bundle/name).read_text())
                if name=='run.json':data['code_hashes']['llm.py']='0'*64
                (target/name).write_text(json.dumps(data))
            with self.assertRaisesRegex(AssertionError,'llm.py'):
                self.module.verify(target,allow_earnings_changes=True)
