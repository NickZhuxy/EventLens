#!/usr/bin/env python3
"""Replay the complete v5 pilot and compare identical development inputs."""
from collections import Counter
from decimal import Decimal
import argparse
import json
from pathlib import Path

import earnings_protocol_v3 as v3
import earnings_protocol_v4 as v4
import earnings_protocol_v5 as v5
from analyze_earnings_protocol_v4 import diagnostics, outcome as old_outcome
from eventlens.benchmark import write_json
from eventlens.core import digest
from eventlens.evidence_v5 import guidance_catalog, explanation_catalog

ROOT = v5.ROOT


def outcome(run):
    result = old_outcome(run)
    expected = run['case'].get('transformation', {}).get('expected_conflict_quotes')
    if 'evidence_coverage' not in run:
        return result
    # B receives catalogs in its initial message; C sees only published tool data.
    if run['method'] == 'B':
        first = next(t for t in run['trace'] if t['stage'] == 'model_call')
        outputs = json.loads(first['messages']['messages'][1]['content'])['evidence_catalogs']
    else:
        outputs = [t['result'] for t in run['trace'] if t['stage'] == 'tool_call']
    citations = [c for output in outputs for c in output.get('citations', [])]
    result['expected_statements_retrieved'] = ([any(
        c['source_id'] == run['case']['new'] and q in c['quote'] for c in citations)
        for q in expected] if expected else None)
    result['evidence_coverage'] = run['evidence_coverage']
    result['selected_metric_ids'] = run.get('evidence_selection', {}).get('metric_ids', [])
    result['candidate_counts_seen'] = {o['source_id']: len(o['metric_candidates'])
                                      for o in outputs if 'metric_candidates' in o}
    return result


def matched(prior, run):
    path = prior/'runs'/(run['case']['case_id']+'_'+run['method']+'.json')
    if not path.exists():
        return None
    previous = json.loads(path.read_text())
    if previous['case'] != run['case'] or previous['source_hashes'] != run['source_hashes']:
        raise ValueError('paired_inputs_differ: '+path.name)
    return previous


def catalog_record(sources, case):
    row = {'case_id': case['case_id'], 'challenge': case.get('challenge', 'real'),
           'available_before_model': {}, 'expected_statements_available': None}
    for sid in (case['old'], case['new']):
        source = sources[sid]
        row['available_before_model'][sid] = {
            'source_hash': source.content_hash,
            'guidance': [{'metric_id': c['metric_id'], 'metric': c['metric'], 'proof_kind': c['proof']['kind']}
                         for c in guidance_catalog(source, case['horizon'])],
            'explanation_candidate_count': len(explanation_catalog(source, case['horizon']))}
    expected = case.get('transformation', {}).get('expected_conflict_quotes')
    if expected:
        quotes = {c['quote'] for c in explanation_catalog(sources[case['new']], case['horizon'])}
        row['expected_statements_available'] = [q in quotes for q in expected]
    return row


def rejected_references(runs):
    attempts = []
    for run in runs:
        for t in run['trace']:
            if t['stage'] != 'model_call' or not t.get('validation_error'):
                continue
            for c in t.get('raw_response', {}).get('choices', [{}])[0].get('message', {}).get('tool_calls', []):
                if c['function']['name'] != 'finish':
                    continue
                args = json.loads(c['function']['arguments'])
                attempts.append({'case_id': run['case']['case_id'], 'method': run['method'], 'call': t['call'],
                    'validation_error': t['validation_error'], 'arguments': args,
                    'conflict_reference_forms': [{k: 'evidence_id_shape' if conflict[k].startswith('e_') else 'text_not_evidence_id'
                        for k in ('statement_a', 'statement_b')} for conflict in args['conflicts']]})
    return attempts


def build(bundle, previous3, previous4):
    sources, jobs, config = v5.check(bundle)
    replays = {'v5': v5.replay(bundle), 'v3': v3.replay(previous3), 'v4': v4.replay(previous4)}
    summary = v5.aggregate(bundle, jobs)
    if summary['completed_runs'] != summary['planned_runs'] or summary['uncertain_requests']:
        raise ValueError('pilot_incomplete_or_has_uncertain_requests')
    if config['methods'] != ['B', 'C']:
        raise ValueError('expected_B_C_pilot')
    runs = [json.loads(p.read_text()) for p in sorted((bundle/'runs').glob('*.json'))]
    prior3, prior4, pairs = [], [], []
    for run in runs:
        a, b = matched(previous3, run), matched(previous4, run)
        if a is None:
            raise ValueError('missing_v3_comparison')
        prior3.append(a)
        if b:
            prior4.append(b)
        pairs.append({'case_id': run['case']['case_id'], 'method': run['method'],
                      'challenge': run['case'].get('challenge', 'real'),
                      'v3': outcome(a), 'v4': outcome(b) if b else None, 'v5': outcome(run)})
    if len(prior3) != 32 or len(prior4) != 8:
        raise ValueError('matched_inventory_incomplete')
    eligible = [r for r in runs if r['case'].get('challenge') != 'stale_disclosure']
    natural = [r for r in runs if not r['case'].get('synthetic')]
    control_rows = [p for p in pairs if p['challenge'] == 'contradictory_commentary']
    costs = [json.loads((f/'summary.json').read_text())['charged_upper_usd']
             for f in (previous3, previous4, bundle)]
    # Retain every accepted natural explanation/conflict for subsequent human review.
    review = [{'case_id': r['case']['case_id'], 'method': r['method'],
               'source_hashes': r['source_hashes'], 'explanations': r['explanations'],
               'conflicts': r['conflicts'], 'comparability': r['comparability'],
               'reviewed_by': None, 'semantic_review': 'pending'} for r in natural]
    return {
        'scope': 'Four exposed development pairs and twelve synthetic derivatives, both B/C. Operational counts, not reviewed accuracy or unseen validation.',
        'bundle': str(bundle.relative_to(ROOT)),
        'analysis_script_sha256': digest(Path(__file__).read_bytes()),
        'bundle_hashes_sha256': {str(f.relative_to(ROOT)): digest((f/'bundle_hashes.json').read_bytes())
                                 for f in (previous3, previous4, bundle)},
        'approval': json.loads((bundle/'approval.json').read_text()), 'replays': replays,
        'summary': summary, 'v3_matched_metrics': v5.metrics(prior3),
        'v4_matched_metrics': v5.metrics(prior4), 'paired_cases': pairs,
        'catalog_availability': [catalog_record(sources, c) for c in jobs
                                 if c.get('challenge') != 'stale_disclosure'],
        'diagnostics': diagnostics(eligible),
        'rejected_finish_attempts': rejected_references(eligible),
        'expected_stale_rejections': sum(r['calls'] == 0 and r['errors'] == ['stale_or_reversed_disclosure_pair']
                                        for r in runs if r['case'].get('challenge') == 'stale_disclosure'),
        'required_reviews_complete': sum(r.get('evidence_coverage', {}).get('completed_reviews') == 4 for r in eligible),
        'eligible_runs': len(eligible),
        'conflict_counts': {method: {
            'cases': sum(p['method'] == method for p in control_rows),
            'both_expected_statements_visible': sum(p['method'] == method and all(p['v5']['expected_statements_retrieved']) for p in control_rows),
            'valid_two_citation_flags': sum(p['method'] == method and p['v5']['valid_two_citation_flag'] for p in control_rows)} for method in config['methods']},
        'natural_review_candidates': review,
        'natural_conflict_flags_unreviewed': dict(Counter(r['method'] for r in natural if r['conflicts'])),
        'combined_v3_v4_v5_conservative_cost_usd': str(sum(map(Decimal, costs), Decimal(0))),
        'limits': [
            'Selection was based on prior development failures. No new held-out or independent company events.',
            'V5 changes table parsing, evidence references, retrieval ranking and mandatory review together. One sample per case cannot isolate their effects or model variability.',
            'Both B and C use the same deterministic candidate catalogs. Numerical gains cannot be credited solely to agent reasoning; a general advantage over B or D is unestablished.',
            'The contradiction controls contain construction-known opposite-polarity sentences. They do not establish detection of natural management conflicts.',
            'The missing-evidence control masks all numerical tokens, including prose and years. It is not table-only deletion.',
            'Stale controls stop before inference. Their expected guard errors are distinct from eligible-case operational failures.',
            'All 36 natural labels and human semantic support judgments remain pending. Literal offsets and structural proofs do not establish semantic accuracy.',
            'V5 remains an opt-in versioned experiment; the original four-method held-out benchmark and default CLI are unchanged.',
            'Cost uses peak cache-miss token rates and ignores discounts; it is not a provider invoice.']}


def markdown(result):
    s, d = result['summary'], result['diagnostics']
    lines = ['# V5 table and conflict pilot', '', result['scope'], '',
        f"Completed **{s['completed_runs']} B/C runs** and **{s['request_attempts']} requests**, with **USD {s['charged_upper_usd']}** conservative token cost under the approved USD {result['approval']['max_usd']} cap. Zero uncertain requests. Combined v3/v4/v5 cost: **USD {result['combined_v3_v4_v5_conservative_cost_usd']}**, within the prior USD 6 allocation. All v3/v4/v5 requests and outputs replay exactly offline.", '',
        '## Matched operational results', '',
        '| Version | Method | Case type | n | No terminal errors | Numerical outputs | Valid control outcomes | Calls |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for version, rows in [('v3', result['v3_matched_metrics']), ('v4', result['v4_matched_metrics']), ('v5', s['metrics'])]:
        for r in rows:
            valid = 'unreviewed' if r['valid_control_outcomes'] is None else r['valid_control_outcomes']
            lines.append(f"| {version} | {r['method']} | {r['challenge']} | {r['cases']} | {r['completed_without_errors']} | {r['numeric_outputs']} | {valid} | {r['calls']} |")
    lines += ['', 'A numerical output is not an accuracy judgment. Valid controls exclude terminal failures; stale guards intentionally return errors before inference. V4 reran only C real/contradiction cases.', '',
        '## Parser availability and model selection', '',
        'B receives full sources plus the same catalogs available to C. The following candidates exist deterministically before inference. Their proof details and every selected ID are saved in `analysis.json` and the raw runs.', '',
        '| Real pair | Old / new candidates | Proof kinds | B numerical output | C numerical output |',
        '| --- | --- | --- | --- | --- |']
    for c in result['catalog_availability']:
        if c['challenge'] != 'real':
            continue
        sources = list(c['available_before_model'].values())
        counts = ' / '.join(str(len(v['guidance'])) for v in sources)
        kinds = ', '.join(sorted({g['proof_kind'] for v in sources for g in v['guidance']}))
        values = {p['method']: p['v5']['numeric_output'] for p in result['paired_cases'] if p['case_id'] == c['case_id']}
        lines.append(f"| {c['case_id']} | {counts} | {kinds} | {values['B']} | {values['C']} |")
    lines += ['', f"Required reviews completed: **{result['required_reviews_complete']}/{result['eligible_runs']} eligible B/C runs**. B catalogs are supplied automatically; C completes actual read-only actions. Expected stale rejections: **{result['expected_stale_rejections']}/8**, all before model access.", '',
        '## Synthetic conflict retrieval', '',
        '| Method | Controls | Both statements visible | Valid flags with both source-specific citations |',
        '| --- | ---: | ---: | ---: |']
    for method, c in result['conflict_counts'].items():
        lines.append(f"| {method} | {c['cases']} | {c['both_expected_statements_visible']} | {c['valid_two_citation_flags']} |")
    lines += ['', 'These flags concern injected synthetic text. Natural explanation/conflict selections are retained in `natural_review_candidates`, with no manufactured human judgments.', '',
        'All eight B/C contradiction runs failed `citation_id_not_in_retrieved_context` despite both injected statements being visible. The schema names `statement_a` and `statement_b` are plain strings, while the resolver expects evidence IDs. Rejected conflict entries contain quotation text in those fields. The saved rejected arguments are retained for diagnosis; they are not counted as successful flags. V5 remains frozen. A separate interface revision must use explicit ID fields and constrain choices to visible references.', '',
        '## Operational diagnostics', '',
        f"Accepted multiple-function responses: **{d['accepted_batches']}/{d['multi_function_responses']}**. Tokens: **{d['prompt_tokens']} input / {d['completion_tokens']} output**. Median eligible-run latency: **{d['median_latency_seconds']:.3f} seconds**.", '',
        'Eligible-case terminal errors: '+(json.dumps(d['terminal_errors'], sort_keys=True) if d['terminal_errors'] else 'none.') , '',
        'Validation failures (including recovered attempts): '+(json.dumps(d['validation_errors'], sort_keys=True) if d['validation_errors'] else 'none.'), '',
        '## Every paired outcome', '',
        '| Case | Method | v3 / v4 / v5 numerical output | v5 terminal errors | v5 calls |',
        '| --- | --- | --- | --- | ---: |']
    for p in result['paired_cases']:
        vals = ' / '.join(str(p[k]['numeric_output']) if p[k] else 'not run' for k in ('v3','v4','v5'))
        file = p['case_id']+'_'+p['method']+'.json'
        lines.append(f"| [{p['case_id']}](../{Path(result['bundle']).name}/runs/{file}) | {p['method']} | {vals} | {', '.join(p['v5']['errors']) or 'none'} | {p['v5']['calls']} |")
    lines += ['', '## Limits', '']+['- '+s for s in result['limits']]
    lines += ['', '## Reproduce', '', '```sh',
        f"python scripts/analyze_earnings_protocol_v5.py {result['bundle']} --out reports/earnings-v5-analysis-2026-10-15 --check", '```', '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle', type=Path)
    p.add_argument('--previous-v3', type=Path, default=ROOT/'reports/earnings-v3-preflight-2026-10-14')
    p.add_argument('--previous-v4', type=Path, default=ROOT/'reports/earnings-v4-preflight-2026-10-15')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    result = build(args.bundle.resolve(), args.previous_v3.resolve(), args.previous_v4.resolve())
    rendered = markdown(result)
    if args.check:
        if json.loads((args.out/'analysis.json').read_text()) != result or (args.out/'analysis.md').read_text() != rendered:
            raise ValueError('saved_analysis_differs')
    else:
        if args.out.exists():
            raise ValueError('preserve_existing_analysis_use_check')
        write_json(args.out/'analysis.json', result)
        (args.out/'analysis.md').write_text(rendered)
    print(json.dumps({'runs': result['summary']['completed_runs'], 'cost_usd': result['summary']['charged_upper_usd'],
                      'all_results_reproduced': True, 'human_reviewed_accuracy': None}, indent=2))


if __name__ == '__main__':
    main()
