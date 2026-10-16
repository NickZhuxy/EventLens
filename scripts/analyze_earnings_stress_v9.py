#!/usr/bin/env python3
"""Reproduce stress outcomes on identical v2 inputs, with all failed attempts retained."""
from collections import Counter
import argparse
import json
from pathlib import Path
import earnings_stress_v9 as runner
import earnings_benchmark as original
from eventlens.benchmark import write_json
from eventlens.core import digest
ROOT=runner.ROOT


def valid_control(run):
    kind=run['case'].get('challenge')
    if kind=='stale_disclosure':
        return run['calls']==0 and run['comparison']['reason']=='stale_or_reversed_disclosure_pair'
    if run['errors']:return False
    if kind=='missing_table':
        return (run['conclusion']=='insufficient_evidence' and not run['comparison']['calculation']
                and not any(x['metric']['source_id']==run['case']['new'] and x['metric']['status']=='provided'
                            for x in run['extractions']))
    if kind=='contradictory_commentary':
        expected=set(run['case']['transformation']['expected_conflict_quotes'])
        return any({c['quote'] for c in x['citations']}==expected for x in run['conflicts'])
    return None


def build():
    folder=ROOT/'reports/earnings-v9-2026-10-15';old=ROOT/'reports/earnings-v2-2026-10-13'
    sources,jobs,config=runner.check(folder);replay=runner.replay(folder);old_replay=original.replay(old)
    summary=runner.aggregate(folder,jobs)
    if summary['completed_runs']!=summary['planned_runs'] or summary['uncertain_requests']:
        raise ValueError('incomplete_or_uncertain_v9_requires_explicit_review')
    pairs=[];errors=Counter();natural=[];references=0
    for case in jobs:
        for method in config['methods']:
            name=case['case_id']+'_'+method+'.json'
            new=json.loads((folder/'runs'/name).read_text());before=json.loads((old/'runs'/name).read_text())
            if new['case']!=before['case'] or new['source_hashes']!=before['source_hashes']:
                raise ValueError('input_pair_changed')
            if method in {'A','D'} and (new['comparison']!=before['comparison'] or new['errors']!=before['errors'] or new['conflicts']!=before['conflicts']):
                raise ValueError('deterministic_baseline_changed')
            for conflict in new['conflicts']:
                for citation in conflict['citations']:
                    source=sources[citation['source_id']]
                    if citation['quote'] not in source.text:raise ValueError('nonliteral_conflict_quote')
                    if 'source_hash' in citation and (citation['source_hash']!=source.content_hash or source.text[citation['start']:citation['end']]!=citation['quote']):
                        raise ValueError('conflict_binding_changed')
                    references+=1
            row={'case_id':case['case_id'],'method':method,'challenge':case.get('challenge','natural'),
                 'v2_valid_control':valid_control(before),'v9_valid_control':valid_control(new),
                 'v2_errors':before['errors'],'v9_errors':new['errors'],
                 'v2_comparison':before['comparison'],'v9_comparison':new['comparison'],
                 'v9_conflicts':new['conflicts'],'v9_calls':new['calls'],'validation_failures':new['validation_failures']}
            pairs.append(row);errors.update(new['errors'])
            if case['split']=='supplemental_natural':natural.append(row)
    control_rows=[]
    for kind in ('stale_disclosure','missing_table','contradictory_commentary'):
        for method in config['methods']:
            rows=[x for x in pairs if x['challenge']==kind and x['method']==method]
            control_rows.append({'challenge':kind,'method':method,'cases':len(rows),
                'v2_valid_outcomes':sum(x['v2_valid_control'] for x in rows),
                'v9_valid_outcomes':sum(x['v9_valid_control'] for x in rows),
                'v9_failed_attempts':sum(bool(x['v9_errors']) and kind!='stale_disclosure' for x in rows),
                'calls':sum(x['v9_calls'] for x in rows)})
    return {'scope':'Known synthetic controls and two natural supplemental cases; no human-reviewed accuracy or unseen test.',
            'summary':summary,'replay':replay,'original_replay':old_replay,'control_metrics':control_rows,
            'paired_outcomes':pairs,'natural_supplemental':natural,'terminal_errors':dict(errors),
            'literal_conflict_references_checked':references,'all_A_D_outputs_unchanged':True,
            'preflight':json.loads((folder/'initial_request_sizes.json').read_text()),
            'approval':json.loads((folder/'approval.json').read_text()),
            'analysis_script_sha256':digest(Path(__file__).read_bytes()),
            'bundle_hashes_sha256':digest((folder/'bundle_hashes.json').read_bytes()),
            'v2_bundle_hashes_sha256':digest((old/'bundle_hashes.json').read_bytes()),
            'limitations':['The original missing_table transformation removes all numbers, not just tables; v7/v8 evaluate table-row removal separately.',
                'Conflict statements are generated opposite-polarity controls, not management contradictions.',
                'The original held-out cases are now exposed regression cases. Labels and natural explanation support still require Nick.',
                'B/C use the same frozen v8 parser and reference interface. A/D retain their original parsers; this does not isolate agent reasoning.',
                'A failed or context-blocked model attempt is not credited as an appropriate abstention. Stale guards are expected pre-model rejections.',
                'Literal source matches and deterministic arithmetic do not validate free-form model prose.']}


def markdown(r):
    s=r['summary'];lines=['# V9: original stress regression','',r['scope'],'',
        f"Saved {s['completed_runs']} run outcomes and {s['request_attempts']} provider request records; conservative cost USD {s['charged_upper_usd']}. Every result and request replays offline. There are {s['uncertain_requests']} new uncertain requests. Earlier uncertain reservations remain in the cumulative budget.",'',
        '| Control | Method | n | v2 valid | v9 valid | v9 failed attempts | Calls |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for x in r['control_metrics']:
        lines.append(f"| {x['challenge']} | {x['method']} | {x['cases']} | {x['v2_valid_outcomes']} | {x['v9_valid_outcomes']} | {x['v9_failed_attempts']} | {x['calls']} |")
    lines+=['','## Natural supplemental cases','','| Case | Method | v9 reason | Errors |','| --- | --- | --- | --- |']
    for x in r['natural_supplemental']:
        lines.append(f"| {x['case_id']} | {x['method']} | {x['v9_comparison']['reason']} | {', '.join(x['v9_errors']) or 'none'} |")
    lines+=['','The natural cases are the original withdrawal and fiscal-rollover examples. These are operational outputs, not human-reviewed accuracy.','',
        'Terminal error inventory: '+json.dumps(r['terminal_errors'],sort_keys=True)+'.','',
        'The preflight record identifies full-document B inputs that exceed the fixed input limit. They stay in the denominator. A and D match the original v2 outputs exactly.','',
        '## Limits','']+['- '+x for x in r['limitations']]+['','## Reproduce','','```sh','python scripts/analyze_earnings_stress_v9.py --check','```','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    r=build();md=markdown(r);out=ROOT/'reports/earnings-v9-analysis-2026-10-15'
    if a.check:
        if json.loads((out/'analysis.json').read_text())!=r or (out/'analysis.md').read_text()!=md:raise ValueError('saved_analysis_differs')
    else:
        if out.exists():raise ValueError('preserve_saved_analysis')
        write_json(out/'analysis.json',r);(out/'analysis.md').write_text(md)
    print(json.dumps({'all_results_reproduced':True,'runs':r['summary']['completed_runs'],'cost_usd':r['summary']['charged_upper_usd']}))


if __name__=='__main__':main()
