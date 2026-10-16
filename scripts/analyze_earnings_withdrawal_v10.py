#!/usr/bin/env python3
"""Compare the four natural supplemental outcomes with their original v9 records."""
import argparse
import json
from pathlib import Path
import earnings_withdrawal_v10 as runner
from eventlens.core import digest
from eventlens.benchmark import write_json
ROOT=runner.ROOT


def build():
    folder=ROOT/'reports/earnings-v10-2026-10-15';sources,jobs,config=runner.check(folder)
    replay=runner.replay(folder);summary=runner.aggregate(folder,jobs)
    if summary['completed_runs']!=4 or summary['uncertain_requests']:raise ValueError('incomplete_or_uncertain_v10')
    rows=[]
    for c in jobs:
        for method in config['methods']:
            name=c['case_id']+'_'+method+'.json'
            before=json.loads((ROOT/'reports/earnings-v9-2026-10-15/runs'/name).read_text())
            after=json.loads((folder/'runs'/name).read_text())
            if before['case']!=after['case'] or before['source_hashes']!=after['source_hashes']:raise ValueError('paired_input_changed')
            withdrawals=[x for x in after['extractions'] if x['metric']['status']=='withdrawn']
            for x in withdrawals:
                if x['metric']['lower'] is not None or x['metric']['upper'] is not None:raise ValueError('withdrawal_has_numbers')
            rows.append({'case_id':c['case_id'],'method':method,'v9_comparison':before['comparison'],
                         'v10_comparison':after['comparison'],'v10_errors':after['errors'],
                         'v10_calls':after['calls'],'withdrawal_records':withdrawals})
    regression=ROOT/'reports/earnings-v10-validation-2026-10-15/recorded-regression.json'
    reg=json.loads(regression.read_text())
    if reg['verifier_sha256']!=digest((ROOT/'scripts/verify_earnings_withdrawal_regression_v10.py').read_bytes()):raise ValueError('regression_verifier_changed')
    return {'scope':'Four live outcomes on two exposed natural supplemental cases; no human-reviewed accuracy.',
        'summary':summary,'replay':replay,'paired_results':rows,'non_withdrawal_recorded_regression_runs':reg['unchanged_runs'],
        'recorded_regression_sha256':digest(regression.read_bytes()),'analysis_script_sha256':digest(Path(__file__).read_bytes()),
        'bundle_hashes_sha256':digest((folder/'bundle_hashes.json').read_bytes()),
        'limits':['The withdrawal rule is narrow: an explicit suspension/withdrawal of financial guidance for the full fiscal year, optionally alongside its quarter.',
                  'The unique prior revenue target supplies currency, basis, definition and units. The source proves withdrawal, not a replacement value.',
                  'Negated, conditional, partial-metric, quarterly-only and unsupported wording abstain. Natural semantic review remains pending.',
                  'Recorded regression reuses prior model responses; it is not fresh inference on the full corpus.',
                  'The rollover case remains an abstention; the system does not compare different fiscal-year targets.']}


def markdown(r):
    s=r['summary'];lines=['# V10: explicit annual guidance withdrawal','',r['scope'],'',
        f"Completed {s['completed_runs']} outcomes and {s['request_attempts']} provider requests for USD {s['charged_upper_usd']}; {s['uncertain_requests']} uncertain requests. All requests and results replay offline.",'',
        '| Case | Method | v9 reason | v10 reason | Errors | Calls |','| --- | --- | --- | --- | --- | ---: |']
    for x in r['paired_results']:
        lines.append(f"| {x['case_id']} | {x['method']} | {x['v9_comparison']['reason']} | {x['v10_comparison']['reason']} | {', '.join(x['v10_errors']) or 'none'} | {x['v10_calls']} |")
    lines+=['',f"The new code also replays {r['non_withdrawal_recorded_regression_runs']} non-withdrawal B/C recordings from v8/v9 with identical requests, traces, evidence and outcomes. This is controller regression using saved responses, not new model inference.",'',
        '## Limits','']+['- '+x for x in r['limits']]+['','## Reproduce','','```sh','python scripts/analyze_earnings_withdrawal_v10.py --check','```','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    r=build();md=markdown(r);out=ROOT/'reports/earnings-v10-analysis-2026-10-15'
    if a.check:
        if json.loads((out/'analysis.json').read_text())!=r or (out/'analysis.md').read_text()!=md:raise ValueError('saved_analysis_differs')
    else:
        if out.exists():raise ValueError('preserve_saved_analysis')
        write_json(out/'analysis.json',r);(out/'analysis.md').write_text(md)
    print(json.dumps({'replayed':True,'runs':4,'cost_usd':r['summary']['charged_upper_usd']}))


if __name__=='__main__':main()
