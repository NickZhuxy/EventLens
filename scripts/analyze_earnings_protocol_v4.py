#!/usr/bin/env python3
"""Reproduce the v4 batch pilot and its matched v3 development comparison."""
from collections import Counter
from decimal import Decimal
import argparse
import json
from pathlib import Path
from statistics import median

import earnings_protocol_v3 as v3
import earnings_protocol_v4 as v4
from eventlens.benchmark import write_json
from eventlens.core import digest

ROOT = v4.ROOT


def outcome(run):
    expected = run['case'].get('transformation', {}).get('expected_conflict_quotes')
    windows = [part for t in run['trace'] if t['stage'] == 'tool_call'
               for part in t['result'].get('passages', [t['result']]) if 'quote' in part]
    retrieved = ([any(q in p['quote'] and p['source_id'] == run['case']['new'] for p in windows)
                  for q in expected] if expected else None)
    flagged = (not run['errors'] and any(
        {(c['source_id'], c['quote']) for c in conflict['citations']} ==
        {(run['case']['new'], q) for q in expected}
        for conflict in run['conflicts'])) if expected else None
    return {'completed_without_errors': not run['errors'],
            'numeric_output': bool(run['comparison']['calculation']),
            'comparison_reason': run['comparison']['reason'],
            'errors': run['errors'], 'calls': run['calls'],
            'accepted_retrievals': sum(t['stage'] == 'tool_call' for t in run['trace']),
            'validation_failures': run['validation_failures'],
            'expected_statements_retrieved': retrieved, 'valid_two_citation_flag': flagged,
            'explanation_candidates': len(run['explanations']), 'latency_ms': run['latency_ms']}


def diagnostics(runs):
    batches, errors = [], Counter()
    for run in runs:
        errors.update(run['errors'])
        for t in run['trace']:
            if t['stage'] != 'model_call' or 'raw_response' not in t:
                continue
            calls = t['raw_response']['choices'][0]['message'].get('tool_calls') or []
            if len(calls) > 1:
                accepted_ids = {s.get('native_call_id') for s in run['trace']
                                if s['stage'] == 'tool_call' and s.get('batch_model_call') == t['call']}
                batches.append({'case_id': run['case']['case_id'], 'model_call': t['call'],
                    'function_names': [c['function']['name'] for c in calls],
                    'accepted': 'validation_error' not in t and {c['id'] for c in calls} == accepted_ids,
                    'validation_error': t.get('validation_error')})
    return {'terminal_errors': dict(errors),
            'validation_errors': dict(Counter(f['error'] for r in runs for f in r['validation_failures'])),
            'multi_function_responses': len(batches),
            'accepted_batches': sum(b['accepted'] for b in batches), 'batches': batches,
            'median_latency_seconds': median(r['latency_ms'] for r in runs)/1000,
            'prompt_tokens': sum(r['tokens']['prompt_tokens'] for r in runs),
            'completion_tokens': sum(r['tokens']['completion_tokens'] for r in runs)}


def build(bundle, previous):
    _, jobs, config = v4.check(bundle)
    replay = v4.replay(bundle)
    previous_replay = v3.replay(previous)
    summary = v4.aggregate(bundle, jobs)
    if summary['completed_runs'] != summary['planned_runs'] or summary['uncertain_requests']:
        raise ValueError('pilot_incomplete_or_has_uncertain_requests')
    if config['methods'] != ['C']:
        raise ValueError('expected_focused_C_pilot')
    runs = [json.loads(p.read_text()) for p in sorted((bundle/'runs').glob('*.json'))]
    old_hashes = json.loads((previous/'bundle_hashes.json').read_text())
    prior, baseline, pairs, selected_hashes = [], [], [], {}
    for run in runs:
        matched = {}
        for method, target in [('C', prior), ('B', baseline)]:
            name = 'runs/'+run['case']['case_id']+'_'+method+'.json'
            path = previous/name
            if digest(path.read_bytes()) != old_hashes[name]:
                raise ValueError('previous_run_hash_mismatch: '+name)
            selected_hashes[name] = old_hashes[name]
            old = json.loads(path.read_text())
            if old['source_hashes'] != run['source_hashes'] or old['case'] != run['case']:
                raise ValueError('paired_inputs_differ')
            target.append(old)
            matched[method] = old
        pairs.append({'case_id': run['case']['case_id'],
                      'challenge': run['case'].get('challenge', 'real'),
                      'v3_C': outcome(matched['C']), 'v4_C': outcome(run),
                      'v3_B': outcome(matched['B'])})
    v3_cost = json.loads((previous/'summary.json').read_text())['charged_upper_usd']
    return {'scope': 'Eight exposed development cases. Operational results, not reviewed accuracy or unseen validation.',
        'bundle': str(bundle.relative_to(ROOT)), 'previous_bundle': str(previous.relative_to(ROOT)),
        'bundle_hashes_sha256': digest((bundle/'bundle_hashes.json').read_bytes()),
        'previous_bundle_hashes_sha256': digest((previous/'bundle_hashes.json').read_bytes()),
        'analysis_script_sha256': digest(Path(__file__).read_bytes()),
        'approval': json.loads((bundle/'approval.json').read_text()), 'replay': replay,
        'previous_replay': previous_replay, 'summary': summary,
        'v3_matched_C_metrics': v4.metrics(prior), 'v3_existing_B_metrics': v4.metrics(baseline),
        'paired_cases': pairs, 'previous_selected_run_sha256': selected_hashes,
        'diagnostics': diagnostics(runs),
        'combined_v3_v4_conservative_cost_usd': str(Decimal(v3_cost)+Decimal(summary['charged_upper_usd'])),
        'limits': [
            'Four selected real development pairs and four synthetic derivatives, not eight independent events.',
            'Only C is rerun; B numbers are the existing v3 results on exactly matching sources.',
            'Batch handling and the C batching instruction changed; model, tool budget, retrieval ranking and validators stayed fixed.',
            'One run per case and version cannot isolate model variability or establish generalization.',
            'Synthetic contradiction wording is construction-known and does not establish natural-conflict detection.',
            'Real-case labels and semantic support judgments remain pending; literal validation is not entailment.',
            'Missing-evidence and stale controls were not rerun in v4; earlier counts must not be attributed to v4.',
            'Reported token cost uses peak cache-miss rates, ignores discounts, and is not a provider invoice.']}


def markdown(result):
    summary, d = result['summary'], result['diagnostics']
    lines = ['# V4 retrieval-batching pilot', '', result['scope'], '',
        f"Completed **{summary['completed_runs']} C runs** and **{summary['request_attempts']} model requests** at **USD {summary['charged_upper_usd']}** conservative token cost, under the approved USD 3 cap. Combined v3/v4 cost: **USD {result['combined_v3_v4_conservative_cost_usd']}**, within the prior USD 6 allocation. All v4 requests and results replay exactly with zero network calls.", '',
        '## Matched development results', '',
        '| Version / method | Case type | n | Completed without errors | Numerical outputs | Valid two-citation flags | Terminal errors | Calls |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, rows in [('v3 B (existing)', result['v3_existing_B_metrics']),
                       ('v3 C', result['v3_matched_C_metrics']), ('v4 C', summary['metrics'])]:
        for r in rows:
            valid = 'unreviewed' if r['valid_control_outcomes'] is None else r['valid_control_outcomes']
            lines.append(f"| {name} | {r['challenge']} | {r['cases']} | {r['completed_without_errors']} | {r['numeric_outputs']} | {valid} | {r['terminal_errors']} | {r['calls']} |")
    lines += ['', 'Numerical output coverage is not accuracy. A completed real-case abstention can still be wrong. Terminal failures are never counted as valid conflict flags.', '',
        '## Paired outcomes', '',
        '| Case | v3 C numeric | v4 C numeric | v3 C errors | v4 C errors | v3 C calls | v4 C calls |',
        '| --- | --- | --- | --- | --- | ---: | ---: |']
    for p in result['paired_cases']:
        a, b = p['v3_C'], p['v4_C']
        lines.append(f"| {p['case_id']} | {a['numeric_output']} | {b['numeric_output']} | {bool(a['errors'])} | {bool(b['errors'])} | {a['calls']} | {b['calls']} |")
    lines += ['', '## Retrieval and conflict diagnosis', '',
        f"The controller accepted **{d['accepted_batches']}/{d['multi_function_responses']}** multiple-function responses. Exact batch actions and any rejection reasons are retained in `analysis.json`.", '',
        '| Synthetic control | v3 retrieved both | v4 retrieved both | v3 valid flag | v4 valid flag |',
        '| --- | --- | --- | --- | --- |']
    for p in result['paired_cases']:
        if p['challenge'] != 'contradictory_commentary':
            continue
        a, b = p['v3_C'], p['v4_C']
        lines.append(f"| {p['case_id']} | {all(a['expected_statements_retrieved'])} | {all(b['expected_statements_retrieved'])} | {a['valid_two_citation_flag']} | {b['valid_two_citation_flag']} |")
    lines += ['', '## Remaining terminal failures', '']
    lines += [f'- {n}: `{e}`' for e, n in d['terminal_errors'].items()] or ['None.']
    lines += ['', '## Saved traces', '']
    for p in result['paired_cases']:
        filename = p['case_id']+'_C.json'
        lines.append(f"- [{p['case_id']}](../{Path(result['bundle']).name}/runs/{filename})")
    lines += ['', '## Limits', ''] + ['- '+item for item in result['limits']]
    lines += ['', '## Reproduce', '', 'From the repository root:', '', '```sh',
        f"python scripts/analyze_earnings_protocol_v4.py {result['bundle']} --out reports/earnings-v4-analysis-2026-10-15 --check", '```', '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle', type=Path)
    p.add_argument('--previous', type=Path, default=ROOT/'reports/earnings-v3-preflight-2026-10-14')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    result = build(args.bundle.resolve(), args.previous.resolve())
    rendered = markdown(result)
    if args.check:
        if json.loads((args.out/'analysis.json').read_text()) != result or (args.out/'analysis.md').read_text() != rendered:
            raise ValueError('saved_analysis_differs')
    else:
        if args.out.exists():
            raise ValueError('preserve_existing_analysis_use_check')
        write_json(args.out/'analysis.json', result)
        (args.out/'analysis.md').write_text(rendered)
    print(json.dumps({'runs': result['summary']['completed_runs'],
        'cost_usd': result['summary']['charged_upper_usd'], 'all_results_reproduced': True,
        'human_reviewed_accuracy': None}, indent=2))


if __name__ == '__main__':
    main()
