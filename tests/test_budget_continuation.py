"""Uncertain billing remains reserved; an identical wire request is never resent."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import sys
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    if str(ROOT/'scripts') not in sys.path:
        sys.path.insert(0,str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class BudgetContinuationTests(unittest.TestCase):
    def test_saved_failure_quarantines_without_resolving_charge(self):
        c=module('continue_earnings_v7')
        # Use only the immutable terminal failure, not a live runner's reservations.
        bundle=ROOT/'reports/earnings-v7-2026-10-15'
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            for name in ('requests/HUBS-FY2025-Q1-Q2_B.01.json','runs/HUBS-FY2025-Q1-Q2_B.json'):
                target=folder/name;target.parent.mkdir(exist_ok=True)
                shutil.copyfile(bundle/name,target)
            result=c.quarantined_failures(folder)
        self.assertEqual(len(result),1)
        self.assertEqual(Decimal(result[0]['retained_usd']),Decimal('0.0374805'))
        self.assertIn('HUBS-FY2025-Q1-Q2_B',result[0]['terminal_run'])

    def test_missing_terminal_run_blocks_continuation(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        c=module('continue_earnings_v7')
        with tempfile.TemporaryDirectory() as t:
            f=Path(t);(f/'requests').mkdir()
            (f/'requests/X_B.01.json').write_text(json.dumps({'state':'failed_or_uncertain'}))
            with self.assertRaisesRegex(ValueError,'without_saved_terminal_run'):
                c.quarantined_failures(f)

    def test_exact_uncertain_wire_request_cannot_reach_adapter(self):
        r=module('earnings_expansion_v8')
        config=json.loads((ROOT/'configs/earnings_expansion_v8.json').read_text())
        old=r.retained_records(config)[0]
        class Settings:
            def to_dict(self):return old['request']['provider_settings']
        class Adapter:
            model=old['request']['model'];kind='unit_test_not_model';settings=Settings();calls=0
            def complete(self,*args):
                self.calls+=1;raise AssertionError('must not resend')
        with tempfile.TemporaryDirectory() as t:
            adapter=Adapter();journal=r.ProtectedJournal(t,adapter,Decimal('1.50'),config['pricing'],config)
            with self.assertRaisesRegex(RuntimeError,'prior_uncertain_request_not_retried'):
                journal.bind('fixture').complete(old['request']['messages'],old['request']['max_output_tokens'])
            self.assertEqual(adapter.calls,0);self.assertEqual(journal.spent(),0)
            self.assertEqual(list(Path(t).glob('*.json')),[])


if __name__=='__main__':unittest.main()
