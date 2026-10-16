#!/usr/bin/env python3
"""Replay non-withdrawal v8/v9 recordings through v10; no fresh model inference."""
import argparse
import json
from pathlib import Path
import earnings_withdrawal_v10 as v10
import earnings_expansion_v8 as v8
import earnings_stress_v9 as v9
from eventlens.benchmark import RecordedAdapter,stable,write_json
from eventlens.core import digest
ROOT=v10.ROOT


def build():
    folder=ROOT/'reports/earnings-v10-2026-10-15';v10.check(folder)
    rows=[]
    fields=('comparison','extractions','explanations','conflicts','comparability','unresolved','errors',
            'validation_failures','calls','tokens','evidence_coverage','evidence_selection','trace')
    for version,runner in ((8,v8),(9,v9)):
        prior=ROOT/f'reports/earnings-v{version}-2026-10-15'
        sources,jobs,config=runner.check(prior);runner.replay(prior)
        for p in sorted((prior/'runs').glob('*.json')):
            saved=json.loads(p.read_text())
            if saved['method'] not in {'B','C'} or saved['case']['case_id']=='SNPS-FY2025-Q2-WITHDRAWAL':continue
            adapter=RecordedAdapter(saved)
            result=v10.run_native(sources,saved['case'],saved['method'],config,adapter)
            actual_stable,saved_stable=stable(result),stable(saved)
            for key in fields:
                if actual_stable.get(key)!=saved_stable.get(key):
                    raise ValueError('regression_changed: '+str(p)+' '+key)
            if adapter.used!=len(adapter.records):raise ValueError('unused_recorded_response')
            rows.append({'version':version,'case_id':saved['case']['case_id'],'method':saved['method'],
                         'run_sha256':digest(p.read_bytes()),'recorded_responses':adapter.used})
    return {'kind':'Re-execution of saved model responses with new controller; not fresh inference or human review.',
            'unchanged_runs':len(rows),'network_calls':0,'paid_calls':0,'checked_fields':list(fields),
            'v10_freeze_sha256':digest((folder/'freeze.json').read_bytes()),
            'verifier_sha256':digest(Path(__file__).read_bytes()),'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    result=build();out=ROOT/'reports/earnings-v10-validation-2026-10-15/recorded-regression.json'
    if a.check:
        if json.loads(out.read_text())!=result:raise ValueError('saved_regression_differs')
    else:
        if out.exists():raise ValueError('preserve_existing_regression')
        write_json(out,result)
    print(json.dumps({'unchanged_recorded_runs':result['unchanged_runs'],'paid_calls':0}))


if __name__=='__main__':main()
