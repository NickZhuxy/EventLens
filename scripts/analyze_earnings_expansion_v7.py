#!/usr/bin/env python3
"""Replay every v7 method and report corpus/ablation coverage without gold labels."""
from collections import Counter,defaultdict
from decimal import Decimal
import argparse
import json
from pathlib import Path
import earnings_expansion_v7 as v7
import earnings_benchmark as v2
from continue_earnings_v7 import quarantined_failures
from eventlens.core import Metric,compare,digest
from eventlens.evidence_v5 import guidance_catalog
from eventlens.benchmark import write_json
ROOT=v7.ROOT


def candidate_control(sources,case):
    found={sid:guidance_catalog(sources[sid],case['horizon']) for sid in (case['old'],case['new'])}
    metrics=[Metric(**found[case[k]][0]['metric']) if len(found[case[k]])==1 else None for k in ('old','new')]
    return {'case_id':case['case_id'],'split':case['split'],'challenge':case.get('challenge','real'),
            'candidate_counts':{sid:len(c) for sid,c in found.items()},
            'candidate_proof_kinds':{sid:[c['proof']['kind'] for c in cs] for sid,cs in found.items()},
            'comparison':compare(*metrics),
            'meaning':'Deterministic shared-parser control, not gold labels or model performance.'}


def build(folder):
    sources,jobs,config=v7.check(folder);replay=v7.replay(folder)
    summary=v7.aggregate(folder,jobs)
    if summary['completed_runs']!=summary['planned_runs']:
        raise ValueError('incomplete_run')
    quarantined=quarantined_failures(folder) if summary['uncertain_requests'] else []
    if len(quarantined)!=summary['uncertain_requests']:
        raise ValueError('uncertain_request_not_quarantined')
    continuation=json.loads((folder/'continuations/terminal-failure-continuation.json').read_text())
    if continuation['quarantined_failures']!=quarantined or continuation['helper_sha256']!=digest((ROOT/'scripts/continue_earnings_v7.py').read_bytes()):
        raise ValueError('continuation_checkpoint_changed')
    preserved=0
    for name,h in continuation['bundle_hashes_at_stop'].items():
        if name=='summary.json':continue
        if digest((folder/name).read_bytes())!=h:raise ValueError('previous_record_changed_after_continuation')
        preserved+=1
    old=ROOT/'reports/earnings-v2-2026-10-13';previous_replay=v2.replay(old)
    runs=[json.loads(p.read_text()) for p in sorted((folder/'runs').glob('*.json'))]
    lookup={(r['case']['case_id'],r['method']):r for r in runs}
    catalog={c['case_id']:candidate_control(sources,c) for c in jobs}
    pairs=[];errors=Counter();reference_checks=0
    for r in runs:
        errors.update(r['errors'])
        for item in r['explanations']:
            if 'source_hash' in item:
                s=sources[item['source_id']]
                if item['source_hash']!=s.content_hash or item['quote']!=s.text[item['start']:item['end']]:
                    raise ValueError('accepted_reference_not_literal')
                reference_checks+=1
    for c in jobs:
        if c.get('synthetic'):continue
        row={'case_id':c['case_id'],'split':c['split'],'source_hashes':lookup[c['case_id'],'C']['source_hashes'],'methods':{}}
        for method in config['methods']:
            current=lookup[c['case_id'],method]
            previous=json.loads((old/'runs'/(c['case_id']+'_'+method+'.json')).read_text())
            if previous['case']!=current['case'] or previous['source_hashes']!=current['source_hashes']:
                raise ValueError('real_pair_changed')
            ablated=lookup[c['case_id']+'~v7-table_rows_only',method]
            row['methods'][method]={'v2_numeric':bool(previous['comparison']['calculation']),
                'v7_numeric':bool(current['comparison']['calculation']),'v7_errors':current['errors'],
                'table_rows_removed_numeric':bool(ablated['comparison']['calculation']),
                'table_rows_removed_errors':ablated['errors'],
                'v7_comparison':current['comparison'],'ablated_comparison':ablated['comparison'],
                'v7_calls':current['calls'],'ablated_calls':ablated['calls'],
                'v7_conflict_count':len(current['conflicts']),'ablated_conflict_count':len(ablated['conflicts'])}
            if method in {'A','D'} and (current['comparison']!=previous['comparison'] or current['errors']!=previous['errors']):
                raise ValueError('frozen_deterministic_baseline_changed')
        pairs.append(row)
    parser_groups=defaultdict(list)
    for c in catalog.values():parser_groups[c['split'],c['challenge']].append(c)
    parser_rows=[{'split':s,'challenge':c,'cases':len(rs),'numeric_outputs':sum(bool(r['comparison']['calculation']) for r in rs)}
                 for (s,c),rs in sorted(parser_groups.items())]
    diagnostics=[]
    for r in runs:
        if r['method'] not in {'B','C'}:continue
        c=catalog[r['case']['case_id']]
        diagnostics.append({'case_id':r['case']['case_id'],'method':r['method'],
            'errors':r['errors'],'validation_failures':r['validation_failures'],
            'candidate_counts':c['candidate_counts'],
            'numeric_output':bool(r['comparison']['calculation']),
            'two_candidates_but_no_numeric':bool(c['comparison']['calculation']) and not bool(r['comparison']['calculation']),
            'comparability':r['comparability'],'unresolved':r['unresolved'],
            'conflicts':r['conflicts'],'explanations':r['explanations']})
    return {'scope':'Full existing corpus regression and pipe-table-row-only ablation; no fresh blind test or human-reviewed accuracy.',
        'summary':summary,'replay':replay,'v2_replay':previous_replay,'paired_cases':pairs,
        'retained_uncertain_requests':quarantined,
        'pre_continuation_files_unchanged':preserved,
        'continuation_checkpoint_sha256':digest((folder/'continuations/terminal-failure-continuation.json').read_bytes()),
        'parser_control_metrics':parser_rows,'parser_control_cases':list(catalog.values()),
        'model_diagnostics':diagnostics,'terminal_errors':dict(errors),'accepted_explanation_reference_checks':reference_checks,
        'all_A_D_original_comparisons_unchanged':True,
        'analysis_script_sha256':digest(Path(__file__).read_bytes()),
        'bundle_hashes_sha256':digest((folder/'bundle_hashes.json').read_bytes()),
        'v2_bundle_hashes_sha256':digest((old/'bundle_hashes.json').read_bytes()),
        'approval':json.loads((folder/'approval.json').read_text()),
        'limits':['The 24 originally held-out pairs are now-exposed regression cases, not fresh unseen validation.',
            'B/C share a bounded candidate parser and source-reference interface; A/D retain earlier extraction rules. This is a system comparison, not an isolated agent-reasoning comparison.',
            'The deterministic shared-parser control separates candidate availability from model selection. Its outputs are not ground truth.',
            'Table ablation deletes pipe-bearing physical rows only. Non-pipe header continuations and every prose number remain. Surviving prose can legitimately support guidance; blanket abstention is not the expected answer.',
            'All labels and model explanation/conflict judgments remain pending Nick. Literal matches and Decimal arithmetic do not validate free-form prose.',
            'Single samples cannot establish stability or superiority. All unsuccessful outputs are retained.',
            'Token costs use conservative peak/cache-miss rates, not an invoice; the hard cap can stop an incomplete run.']}


def markdown(r):
    s=r['summary'];lines=['# V7 corpus regression and table-row ablation','',r['scope'],'',
        f"Saved **{s['completed_runs']} / {s['planned_runs']} run outcomes**, **{s['request_attempts']} request attempts**, **USD {s['charged_upper_usd']}** conservative cost including retained reservations. **{s['uncertain_requests']} request(s) remain billing-uncertain** and are preserved as terminal failures, never retried. Every saved request, failure and result replays exactly. All A/D original comparisons match v2.",'',
        '## Four-method coverage','','| Method | Original split | Input | n | Numeric outputs | No terminal errors | Calls |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for row in s['metrics']:
        lines.append(f"| {row['method']} | {row['split']} | {row['challenge']} | {row['cases']} | {row['numeric_outputs']} | {row['completed_without_errors']} | {row['calls']} |")
    lines+=['','These are output counts, not accuracy. A completed abstention may still miss evidence. The original split is retained for comparison, without calling these cases unseen.','',
        '## Shared-parser control','','| Original split | Input | n | Deterministic numerical outputs |','| --- | --- | ---: | ---: |']
    for row in r['parser_control_metrics']:
        lines.append(f"| {row['split']} | {row['challenge']} | {row['cases']} | {row['numeric_outputs']} |")
    lines+=['','This control directly compares the unique parser candidates without a model. It makes deterministic assistance visible rather than assigning all numerical gains to the agent. Ambiguous/missing candidate sets abstain.','',
        '## Original and ablated case pairs','','| Pair | Original split | A original / ablated | B original / ablated | C original / ablated | D original / ablated |',
        '| --- | --- | --- | --- | --- | --- |']
    for p in r['paired_cases']:
        cells=['yes / yes' if m['v7_numeric'] and m['table_rows_removed_numeric'] else
               ('yes' if m['v7_numeric'] else 'no')+' / '+('yes' if m['table_rows_removed_numeric'] else 'no') for m in p['methods'].values()]
        lines.append('| '+p['case_id']+' | '+p['split']+' | '+' | '.join(cells)+' |')
    lines+=['','## Failures and review','','Terminal errors: '+json.dumps(r['terminal_errors'],sort_keys=True)+'.','',
        'Every B/C error, rejected action, comparability warning, unresolved narrative, explanation and conflict is retained in `model_diagnostics` in the JSON report. These model judgments remain unreviewed. Full traces are in the sibling execution bundle.','',
        '## Limits','']+['- '+x for x in r['limits']]
    lines+=['','## Reproduce','','```sh','python scripts/analyze_earnings_expansion_v7.py --check','```','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    folder=ROOT/'reports/earnings-v7-2026-10-15';out=ROOT/'reports/earnings-v7-analysis-2026-10-15'
    r=build(folder);md=markdown(r)
    if a.check:
        if json.loads((out/'analysis.json').read_text())!=r or (out/'analysis.md').read_text()!=md:raise ValueError('saved_analysis_differs')
    else:
        if out.exists():raise ValueError('preserve_existing_analysis')
        write_json(out/'analysis.json',r);(out/'analysis.md').write_text(md)
    print(json.dumps({'all_results_reproduced':True,'runs':r['summary']['completed_runs'],'cost_usd':r['summary']['charged_upper_usd']}))


if __name__=='__main__':main()
