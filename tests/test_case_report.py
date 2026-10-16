"""User-facing arithmetic cannot repeat a model's erroneous numerical narration."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import earnings_case_report as report


class CaseReportTests(unittest.TestCase):
    def test_box_asymmetric_changes_come_from_decimal(self):
        text=report.render(ROOT/'reports/earnings-v5-preflight-2026-10-15','BOX-FY2025-Q1-Q2','C',ROOT/'work/test.md')
        self.assertIn('11,000,000',text);self.assertIn('10,000,000',text)
        self.assertIn('10,500,000',text)
        self.assertNotIn('Both bounds',text)
        self.assertIn('Human review',text)

    def test_synthetic_statements_are_identified_as_test_data(self):
        text=report.render(ROOT/'reports/earnings-v6-preflight-2026-10-15','SNPS-FY2025-Q1-Q2~v3-contradictory_commentary','C',ROOT/'work/test.md')
        self.assertIn('Injected statements must not be attributed to management',text)
        self.assertIn('Demand caused the FY2025',text)
        self.assertIn('Demand did not cause the FY2025',text)
        self.assertIn('Parent disclosure URL',text)

    def test_missing_values_are_not_rendered_as_zero(self):
        text=report.render(ROOT/'reports/earnings-v5-preflight-2026-10-15','BOX-FY2025-Q1-Q2~v3-missing_numerical_evidence','C',ROOT/'work/test.md')
        self.assertIn('Missing values remain missing',text)
        self.assertNotIn('| Midpoint',text)

    def test_tampered_arithmetic_is_rejected_even_if_file_is_resealed(self):
        source=ROOT/'reports/earnings-v5-preflight-2026-10-15'
        name='runs/BOX-FY2025-Q1-Q2_C.json'
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);(folder/'runs').mkdir()
            for f in ('sources.json','bundle_hashes.json',name):shutil.copyfile(source/f,folder/f)
            run=json.loads((folder/name).read_text());run['comparison']['calculation']['upper_delta']='11000000'
            (folder/name).write_text(json.dumps(run));seals=json.loads((folder/'bundle_hashes.json').read_text())
            seals[name]=report.digest((folder/name).read_bytes());(folder/'bundle_hashes.json').write_text(json.dumps(seals))
            with self.assertRaisesRegex(ValueError,'does_not_recompute'):
                report.render(folder,'BOX-FY2025-Q1-Q2','C',folder/'report.md')


if __name__=='__main__':unittest.main()
