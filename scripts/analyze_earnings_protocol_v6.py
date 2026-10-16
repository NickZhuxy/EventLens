#!/usr/bin/env python3
"""Replay the complete v6 pilot and every matching v5 failure."""
import argparse
import json
from decimal import Decimal
from pathlib import Path
import earnings_protocol_v6 as v6
import earnings_protocol_v5 as v5
from analyze_earnings_protocol_v5 import outcome
from analyze_earnings_protocol_v4 import diagnostics
from eventlens.core import digest
from eventlens.benchmark import write_json
ROOT=v6.ROOT


def build(folder):
    _,jobs,_=v6.check(folder)
    previous=ROOT/'reports/earnings-v5-preflight-2026-10-15'
    replays={'v6':v6.replay(folder),'v5':v5.replay(previous)}
    summary=v6.aggregate(folder,jobs)
    if summary['completed_runs']!=8 or summary['uncertain_requests']:
        raise ValueError('incomplete_or_uncertain_pilot')
    pairs=[];runs=[];old=[]
    for path in sorted((folder/'runs').glob('*.json')):
        r=json.loads(path.read_text());p=json.loads((previous/'runs'/path.name).read_text())
        if p['case']!=r['case'] or p['source_hashes']!=r['source_hashes']:
            raise ValueError('paired_inputs_differ')
        pairs.append({'case_id':r['case']['case_id'],'method':r['method'],'v5':outcome(p),'v6':outcome(r)})
        runs.append(r);old.append(p)
    prior=sum((Decimal(json.loads((ROOT/p/'summary.json').read_text())['charged_upper_usd']) for p in [
        'reports/earnings-v3-preflight-2026-10-14','reports/earnings-v4-preflight-2026-10-15','reports/earnings-v5-preflight-2026-10-15']),Decimal(0))
    return {'scope':'Four exposed synthetic development controls, both B/C; operational evidence only.',
            'summary':summary,'previous_metrics':v6.metrics(old),'paired_cases':pairs,'diagnostics':diagnostics(runs),
            'replays':replays,'approval':json.loads((folder/'approval.json').read_text()),
            'combined_v3_to_v6_cost_usd':str(prior+Decimal(summary['charged_upper_usd'])),
            'analysis_script_sha256':digest(Path(__file__).read_bytes()),
            'bundle_hashes_sha256':{str(p.relative_to(ROOT)):digest((p/'bundle_hashes.json').read_bytes()) for p in (folder,previous)},
            'limits':['Both methods share the deterministic candidate parser; no agent superiority claim.',
                      'The statements are synthetic, not management contradictions.',
                      'One run per exposed case does not establish natural-conflict accuracy or generalization.',
                      'References and numerical outputs are validated; free-form model prose is unvalidated.',
                      'All natural labels and semantic judgments await Nick. Costs are conservative token estimates, not invoices.']}


def markdown(r):
    s=r['summary']
    lines=['# V6 conflict-reference pilot','',r['scope'],'',
           f"Completed {s['completed_runs']} B/C runs, {s['request_attempts']} requests, USD {s['charged_upper_usd']} conservative cost, zero uncertain requests. All v5/v6 requests and results replay exactly. Combined v3–v6 cost: USD {r['combined_v3_to_v6_cost_usd']}.",'',
           '| Version | Method | Cases | Valid two-citation flags | Numerical outputs | Errors | Calls |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for version,rows in [('v5',r['previous_metrics']),('v6',s['metrics'])]:
        for row in rows:
            lines.append(f"| {version} | {row['method']} | {row['cases']} | {row['valid_control_outcomes']} | {row['numeric_outputs']} | {row['terminal_errors']} | {row['calls']} |")
    lines+=['','## Every paired result','','| Case | Method | v5 flag | v6 flag | v6 calls |','| --- | --- | --- | --- | ---: |']
    for p in r['paired_cases']:
        name=p['case_id']+'_'+p['method']+'.json'
        lines.append(f"| [{p['case_id']}](../earnings-v6-preflight-2026-10-15/runs/{name}) | {p['method']} | {p['v5']['valid_two_citation_flag']} | {p['v6']['valid_two_citation_flag']} | {p['v6']['calls']} |")
    lines+=['','## Interpretation','','The explicit ID fields and per-request reference choices remove the observed quote/ID mismatch on this pilot. Both B and C succeed; the result does not show that the agent loop outperforms the single-pass method. Every earlier failure remains saved.','', '## Limits','']+['- '+x for x in r['limits']]
    lines+=['','## Reproduce','','```sh','python scripts/analyze_earnings_protocol_v6.py --check','```','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    folder=ROOT/'reports/earnings-v6-preflight-2026-10-15';out=ROOT/'reports/earnings-v6-analysis-2026-10-15'
    r=build(folder);md=markdown(r)
    if args.check:
        if json.loads((out/'analysis.json').read_text())!=r or (out/'analysis.md').read_text()!=md:
            raise ValueError('saved_analysis_differs')
    else:
        if out.exists():raise ValueError('preserve_existing_analysis')
        write_json(out/'analysis.json',r);(out/'analysis.md').write_text(md)
    print(json.dumps({'replayed':True,'runs':r['summary']['completed_runs'],'cost_usd':r['summary']['charged_upper_usd']}))


if __name__=='__main__':main()
