#!/usr/bin/env python3
"""Reproduce operational results for the frozen v3 development pilot."""
from collections import Counter
from decimal import Decimal
import argparse
import json
from pathlib import Path
from statistics import median

from earnings_protocol_v3 import ROOT, aggregate, check, metrics, replay
from eventlens.benchmark import write_json
from eventlens.core import digest
from eventlens.llm import strict_json


def build(bundle, previous):
    sources, jobs, config = check(bundle)
    reproduced = replay(bundle)
    summary = aggregate(bundle, jobs)
    if summary['completed_runs'] != summary['planned_runs'] or summary['uncertain_requests']:
        raise ValueError('pilot_incomplete_or_has_uncertain_requests')
    runs = [json.loads(p.read_text()) for p in sorted((bundle/'runs').glob('*.json'))]
    requests = [json.loads(p.read_text()) for p in sorted((bundle/'requests').glob('*.json'))]
    paired, previous_hashes = [], {}
    old_hashes = json.loads((previous/'bundle_hashes.json').read_text())
    for run in runs:
        if run['case'].get('synthetic'):
            continue
        name = 'runs/'+run['case']['case_id']+'_'+run['method']+'.json'
        path = previous/name
        if digest(path.read_bytes()) != old_hashes[name]:
            raise ValueError('previous_run_hash_mismatch: '+name)
        previous_hashes[name] = old_hashes[name]
        old = json.loads(path.read_text())
        if old['source_hashes'] != run['source_hashes']:
            raise ValueError('paired_sources_differ')
        paired.append({'case_id': run['case']['case_id'], 'method': run['method'],
            'v2_numeric': bool(old['comparison']['calculation']), 'v3_numeric': bool(run['comparison']['calculation']),
            'v2_errors': old['errors'], 'v3_errors': run['errors'],
            'v2_calls': old['calls'], 'v3_calls': run['calls'],
            'v3_validation_failures': run['validation_failures'],
            'v2_latency_ms': old['latency_ms'], 'v3_latency_ms': run['latency_ms']})
    diagnostics, examples = {}, {}
    for method in config['methods']:
        items = [r for r in runs if r['method'] == method]
        active = [r for r in items if r['case'].get('challenge') != 'stale_disclosure']
        terminal = Counter(e for r in active for e in r['errors'])
        rejected = Counter(e['error'] for r in active for e in r['validation_failures'])
        model_records = [t for r in active for t in r['trace'] if t['stage'] == 'model_call']
        multi = 0
        unparseable = 0
        absent_candidates = []
        conflict_retrieval = []
        for r in active:
            if method == 'C' and r['case'].get('challenge') == 'contradictory_commentary':
                windows = []
                for t in r['trace']:
                    if t['stage'] == 'tool_call':
                        output = t.get('result', {})
                        windows.extend(p['quote'] for p in output.get('passages', [output]) if 'quote' in p)
                conflict_retrieval.append({'case_id': r['case']['case_id'],
                    'expected_statements_retrieved': [any(q in w for w in windows)
                        for q in r['case']['transformation']['expected_conflict_quotes']]})
            for t in r['trace']:
                if t['stage'] != 'model_call':
                    continue
                choice = t['raw_response']['choices'][0]
                calls = choice['message'].get('tool_calls') or []
                multi += len(calls) > 1
                for call in calls:
                    if call.get('function', {}).get('name') != 'finish':
                        continue
                    try:
                        value = strict_json(call['function']['arguments'])
                    except (ValueError, TypeError):
                        unparseable += 1
                        continue
                    if r['case'].get('challenge') == 'missing_numerical_evidence':
                        if any(m.get('source_id') == r['case']['new'] and m.get('status') == 'provided'
                               for m in value.get('metrics', []) if isinstance(m, dict)):
                            absent_candidates.append({'case_id': r['case']['case_id'], 'call': t['call']})
        reqs = [q for q in requests if any(
            q['request']['messages'] == t['messages'] for t in model_records)]
        diagnostics[method] = {'eligible_runs': len(active), 'terminal_errors': dict(terminal),
            'validation_failures': dict(rejected), 'multi_function_responses': multi,
            'native_envelope_errors': sum(t.get('validation_error', '').startswith(('expected_', 'invalid_native')) for t in model_records),
            'unparseable_finish_arguments': unparseable,
            'provided_metric_attempts_in_absent_new_source': absent_candidates,
            'synthetic_conflict_retrieval': conflict_retrieval,
            'recovered_to_numeric': sum(bool(r['validation_failures']) and not r['errors'] and bool(r['comparison']['calculation']) for r in active),
            'recovered_to_no_numeric': sum(bool(r['validation_failures']) and not r['errors'] and not r['comparison']['calculation'] for r in active),
            'median_eligible_latency_seconds': median(r['latency_ms'] for r in active)/1000,
            'prompt_tokens': sum(q['response']['usage']['prompt_tokens'] for q in reqs),
            'completion_tokens': sum(q['response']['usage']['completion_tokens'] for q in reqs),
            'charged_upper_usd': str(sum((Decimal(q['charged_upper_usd']) for q in reqs), Decimal(0)))}
    for r in runs:
        if r['method'] != 'C' or r['errors']:
            continue
        if not r['case'].get('synthetic') and r['validation_failures'] and r['comparison']['calculation']:
            examples.setdefault('repaired_real_comparison', r)
        if r['case'].get('challenge') == 'contradictory_commentary' and r['conflicts']:
            expected = set(r['case']['transformation']['expected_conflict_quotes'])
            if any({c['quote'] for c in f['citations']} == expected for f in r['conflicts']):
                examples.setdefault('two_cited_synthetic_statements', r)
    return {'scope': 'Failure-oriented development diagnostic. No human-reviewed accuracy or unseen-test result.',
        'bundle': str(bundle.relative_to(ROOT)), 'bundle_hashes_sha256': digest((bundle/'bundle_hashes.json').read_bytes()),
        'analysis_script_sha256': digest(Path(__file__).read_bytes()), 'approval': json.loads((bundle/'approval.json').read_text()),
        'replay': reproduced, 'summary': summary, 'paired_real_cases': paired,
        'previous_run_sha256': previous_hashes, 'diagnostics': diagnostics,
        'example_paths': {name: 'runs/'+r['case']['case_id']+'_C.json' for name, r in examples.items()},
        'limitations': ['Four selected development pairs, not an independent sample or unseen test.',
            'Tool format, prompts, reasoning mode, output allowance and validation feedback changed together.',
            'A completed abstention after repair is operational recovery, not proof that abstention was correct on real data.',
            'Missing-evidence controls mask every numeric token, not just a table. Contradictions use known synthetic wording.',
            'All labels and semantic explanation judgments remain pending. Literal citations are not semantic entailment.',
            'Cost uses reported tokens at peak cache-miss prices and is not an invoice.']}


def markdown(result):
    s = result['summary']
    lines = ['# V3 development reliability pilot', '', result['scope'], '',
             f"Completed **{s['completed_runs']} method runs** and **{s['request_attempts']} model requests**. Conservative token cost: **USD {s['charged_upper_usd']}**, under the approved USD 6 cap. Exact replay made zero network or paid calls.", '',
             '## Operational results', '',
             '| Method | Case type | n | Completed without errors | Numeric outputs | Valid control outcomes | Terminal errors | Recovered runs | Calls |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in s['metrics']:
        valid = 'unreviewed' if r['valid_control_outcomes'] is None else str(r['valid_control_outcomes'])
        lines.append(f"| {r['method']} | {r['challenge']} | {r['cases']} | {r['completed_without_errors']} | {r['numeric_outputs']} | {valid} | {r['terminal_errors']} | {r['recovered_runs']} | {r['calls']} |")
    lines += ['', 'Stale-source rejections are expected pre-model eligibility failures. Other failures are never credited as valid control outcomes. Recovered runs can finish without numerical output; real-case correctness is unreviewed.', '',
              '## Same real development pairs in v2 and v3', '',
              '| Case | Method | v2 numeric | v3 numeric | v2 terminal failure | v3 terminal failure | v2 calls | v3 calls |',
              '| --- | --- | --- | --- | --- | --- | ---: | ---: |']
    for r in result['paired_real_cases']:
        lines.append(f"| {r['case_id']} | {r['method']} | {r['v2_numeric']} | {r['v3_numeric']} | {bool(r['v2_errors'])} | {bool(r['v3_errors'])} | {r['v2_calls']} | {r['v3_calls']} |")
    lines += ['', 'This comparison diagnoses the same exposed development inputs. It does not isolate a causal effect of native tools or establish generalization.', '', '## Remaining failures', '']
    for method, d in result['diagnostics'].items():
        lines += [f"### {method}", '',
            f"Multiple-function responses: {d['multi_function_responses']}. Native envelope errors: {d['native_envelope_errors']}. Unparseable finish arguments: {d['unparseable_finish_arguments']}.", '',
            f"Recovered to numerical output: {d['recovered_to_numeric']}; recovered without numerical output: {d['recovered_to_no_numeric']}.", '',
            f"Provided-metric attempts attributed to the absent new source: {len(d['provided_metric_attempts_in_absent_new_source'])}. This audit includes parseable rejected finish actions; it is not a general fabrication score.", '']
        for error, count in d['terminal_errors'].items():
            lines.append(f'- {count}: `{error}`')
        if d['synthetic_conflict_retrieval']:
            both = sum(all(c['expected_statements_retrieved']) for c in d['synthetic_conflict_retrieval'])
            lines += ['', f"Cases with both expected synthetic statements in retrieved context: {both}/{len(d['synthetic_conflict_retrieval'])}."]
        lines.append('')
    lines += ['## Saved investigation examples', '']
    for name, path in result['example_paths'].items():
        lines.append(f"- [{name.replace('_', ' ')}](../{Path(result['bundle']).name}/{path})")
    lines += ['', 'Read validation feedback and subsequent retrieval actions in the trace. No successful two-citation C conflict example was produced in this pilot.', '', '## Limits', '']
    lines += ['- '+x for x in result['limitations']]
    lines += ['', '## Reproduce', '', 'From the repository root:', '', '```sh',
              f"python scripts/analyze_earnings_protocol_v3.py {result['bundle']} --out reports/earnings-v3-analysis-2026-10-15 --check", '```', '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle', type=Path)
    p.add_argument('--previous', type=Path, default=ROOT/'reports/earnings-v2-2026-10-13')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    result = build(args.bundle.resolve(), args.previous.resolve())
    text = markdown(result)
    if args.check:
        if json.loads((args.out/'analysis.json').read_text()) != result or (args.out/'analysis.md').read_text() != text:
            raise ValueError('saved_analysis_differs')
    else:
        if args.out.exists():
            raise ValueError('preserve_existing_analysis_use_check')
        write_json(args.out/'analysis.json', result)
        (args.out/'analysis.md').write_text(text)
    print(json.dumps({'runs': result['summary']['completed_runs'], 'cost_usd': result['summary']['charged_upper_usd'],
                      'all_results_reproduced': True, 'human_reviewed_accuracy': None}, indent=2))


if __name__ == '__main__':
    main()
