#!/usr/bin/env python3
"""Prepare a focused v4 batching pilot; paid execution needs new approval."""
from collections import defaultdict
from dataclasses import asdict, replace
from decimal import Decimal
import argparse
import fcntl
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from eventlens.core import Source, canonical, digest, load_corpus, now
from eventlens.benchmark import BudgetJournal, RecordedAdapter, stable, write_json
from eventlens.protocol_v4 import NativeAdapter, run_native


def population(sources, cases, config):
    selected = [next(c for c in cases if c['case_id'] == cid) for cid in config['case_ids']]
    if len({c['case_id'] for c in selected}) != len(selected) or any(c['split'] != 'development' for c in selected):
        raise ValueError('only_unique_development_cases_allowed')
    data = {sid: sources[sid] for c in selected for sid in (c['old'], c['new'])}
    jobs = list(selected)
    for c in selected:
        source = data[c['new']]
        removed = []
        def mask(m):
            removed.append({'start': m.start(), 'end': m.end(), 'text': m[0]})
            return '[VALUE REMOVED]'
        masked = re.sub(r'\d[\d,]*(?:\.\d+)?', mask, source.text)
        a = f"Demand caused the {c['horizon']} total revenue guidance revision on a reported basis."
        b = f"Demand did not cause the {c['horizon']} total revenue guidance revision on a reported basis."
        for kind, text, detail in [
            ('missing_numerical_evidence', masked, {'removed_spans': removed,
                'description': 'All numerical tokens masked, including prose, tables and year headings; not table-only.'}),
            ('contradictory_commentary', source.text+'\n'+a+'\n'+b+'\n',
                {'expected_conflict_quotes': [a, b], 'description': 'Construction-known synthetic opposite-polarity statements; not management statements.'})]:
            sid = source.source_id+'~v3-'+kind
            data[sid] = replace(source, source_id=sid, text=text, content_hash=digest(text),
                                snapshot_kind='SYNTHETIC derivative of '+source.source_id)
            jobs.append({**c, 'case_id': c['case_id']+'~v3-'+kind, 'new': sid,
                         'parent_case_id': c['case_id'], 'split': 'synthetic_development',
                         'synthetic': True, 'challenge': kind, 'transformation': detail,
                         'parent_source_hash': source.content_hash, 'derived_source_hash': digest(text)})
        jobs.append({**c, 'case_id': c['case_id']+'~v3-stale_disclosure', 'new': c['old'],
                     'parent_case_id': c['case_id'], 'split': 'synthetic_development',
                     'synthetic': True, 'challenge': 'stale_disclosure',
                     'transformation': {'description': 'Replace new disclosure with old; reject before model access.'}})
    jobs = [c for c in jobs if c.get('challenge', 'real') in config['selected_challenges']]
    used = {sid for c in jobs for sid in (c['old'], c['new'])}
    return {sid: source for sid, source in data.items() if sid in used}, jobs


def estimate(jobs, config):
    eligible = sum(c.get('challenge') != 'stale_disclosure' for c in jobs)
    requests = eligible * sum(1 if m == 'B' else config['max_calls'] for m in config['methods'])
    # The journal includes the complete wire body, model and provider settings.
    # 4096 is deliberately above its 2048-token padding plus envelope serialization.
    per_call = (Decimal(config['max_input_bytes']+4096)*Decimal(config['pricing']['input_per_million'])
                + Decimal(config['max_output_tokens_per_call'])*Decimal(config['pricing']['output_per_million']))/1000000
    # Transparent scenario, not a model-output prediction. Actual usage is journalled.
    inp, out = (Decimal(config['pricing'][k]) for k in ('input_per_million', 'output_per_million'))
    planning = eligible * sum(32000*inp+3000*out if m == 'B' else 7*(10000*inp+1000*out) for m in config['methods'])/1000000
    return {'paid_execution': 'not_started', 'planned_method_runs': len(jobs)*len(config['methods']),
            'real_development_pairs': sum(not c.get('synthetic') for c in jobs),
            'synthetic_variants': sum(bool(c.get('synthetic')) for c in jobs),
            'maximum_model_requests': requests, 'planning_scenario_usd': str(planning),
            'planning_assumptions': 'Per eligible C case: seven calls of 10000 input and 1000 output tokens each. B is not rerun. Not an empirical forecast.',
            'conservative_full_budget_bound_usd': str(per_call*requests),
            'bound_assumptions': 'Every request at input byte limit plus 4096 overhead tokens and maximum output tokens; peak/cache-miss prices. No automatic network retries.',
            'proposed_cap_usd': config['proposed_budget_usd'], 'pricing': config['pricing']}


def prepare(folder):
    if folder.exists():
        raise ValueError('prepare requires a new directory')
    config = json.loads((ROOT/'configs/earnings_protocol_v4.json').read_text())
    _, sources = load_corpus(ROOT/'data/manifest.json')
    sources, jobs = population(sources, json.loads((ROOT/'data/cases.json').read_text()), config)
    initial_bytes = initial_request_sizes(sources, jobs, config)
    folder.mkdir(parents=True)
    write_json(folder/'sources.json', [asdict(s) for s in sources.values()])
    write_json(folder/'jobs.json', jobs)
    write_json(folder/'config.json', config)
    write_json(folder/'estimate.json', estimate(jobs, config))
    write_json(folder/'initial_request_sizes.json', initial_bytes)
    paths = sorted((ROOT/'src/eventlens').rglob('*.py')) + [Path(__file__)]
    write_json(folder/'freeze.json', {'frozen_at': now(),
        'code_hashes': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths},
        'input_hashes': {n: digest((folder/n).read_bytes()) for n in ('sources.json', 'jobs.json', 'config.json', 'estimate.json', 'initial_request_sizes.json')},
        'scope': 'Development diagnostic only. No new unseen test, reviewed accuracy, or agent superiority claim.'})
    return estimate(jobs, config)


def initial_request_sizes(sources, jobs, config):
    """Construct initial wire bodies locally; no provider client or credentials."""
    class Probe:
        model = config['model']
        kind = 'local_request_size_probe_not_model_inference'
        size = 0
        def complete(self, payload, max_output):
            self.size = len(canonical(payload).encode())
            raise RuntimeError('local_size_probe_complete')
    sizes = {}
    for case in jobs:
        for method in config['methods']:
            adapter = Probe()
            result = run_native(sources, case, method, config, adapter)
            if result['errors'] != (['stale_or_reversed_disclosure_pair'] if case.get('challenge') == 'stale_disclosure'
                                    else ['local_size_probe_complete']):
                raise ValueError('preflight_request_failed: '+case['case_id']+' '+method+' '+str(result['errors']))
            sizes[case['case_id']+'_'+method] = adapter.size
    return {'initial_wire_bytes': sizes, 'all_initial_requests_fit': True,
            'network_calls': 0, 'later_context_growth': 'Enforced at each request; not predicted here.'}


def check(folder):
    freeze = json.loads((folder/'freeze.json').read_text())
    for name, h in freeze['code_hashes'].items():
        if digest((ROOT/name).read_bytes()) != h:
            raise ValueError('frozen_code_changed: '+name)
    for name, h in freeze['input_hashes'].items():
        if digest((folder/name).read_bytes()) != h:
            raise ValueError('frozen_input_changed: '+name)
    sources = [Source(**s) for s in json.loads((folder/'sources.json').read_text())]
    if len({s.source_id for s in sources}) != len(sources):
        raise ValueError('duplicate_source')
    return ({s.source_id: s for s in sources}, json.loads((folder/'jobs.json').read_text()),
            json.loads((folder/'config.json').read_text()))


def metrics(runs):
    groups = defaultdict(list)
    for r in runs:
        groups[r['method'], r['case'].get('challenge', 'real')].append(r)
    rows = []
    for (method, challenge), items in sorted(groups.items()):
        good = lambda r: not r['errors']
        expected = None
        if challenge == 'stale_disclosure':
            expected = sum(r['calls'] == 0 and r['comparison']['reason'] == 'stale_or_reversed_disclosure_pair' for r in items)
        elif challenge == 'missing_numerical_evidence':
            expected = sum(good(r) and r['conclusion'] == 'insufficient_evidence' and
                           not any(x['metric']['source_id'] == r['case']['new'] and x['metric']['status'] == 'provided'
                                   for x in r['extractions']) for r in items)
        elif challenge == 'contradictory_commentary':
            expected = sum(good(r) and any(set(r['case']['transformation']['expected_conflict_quotes']) ==
                              {c['quote'] for c in conflict['citations']} for conflict in r['conflicts']) for r in items)
        rows.append({'method': method, 'challenge': challenge, 'cases': len(items),
            'completed_without_errors': sum(good(r) for r in items),
            'numeric_outputs': sum(bool(r['comparison']['calculation']) for r in items),
            'valid_control_outcomes': expected, 'terminal_errors': sum(not good(r) for r in items),
            'validation_failures': sum(len(r['validation_failures']) for r in items),
            'recovered_runs': sum(bool(r['validation_failures']) and good(r) for r in items),
            'calls': sum(r['calls'] for r in items), 'human_reviewed_accuracy': None})
    return rows


def aggregate(folder, jobs):
    runs = [json.loads(p.read_text()) for p in sorted((folder/'runs').glob('*.json'))]
    requests = [json.loads(p.read_text()) for p in sorted((folder/'requests').glob('*.json'))]
    return {'completed_runs': len(runs), 'planned_runs': len(jobs)*len(json.loads((folder/'config.json').read_text())['methods']), 'metrics': metrics(runs),
            'request_attempts': len(requests),
            'charged_upper_usd': str(sum((Decimal(r['charged_upper_usd']) for r in requests), Decimal(0))),
            'uncertain_requests': sum(r['state'] != 'complete' for r in requests),
            'scope': 'V4 batching diagnostic on eight C cases; operational counts, not accuracy. Zero human-reviewed labels.'}


def save_state(folder, jobs):
    result = aggregate(folder, jobs)
    write_json(folder/'summary.json', result)
    files = [folder/n for n in ('sources.json', 'jobs.json', 'config.json', 'estimate.json', 'initial_request_sizes.json', 'freeze.json', 'summary.json')]
    files += sorted((folder/'runs').glob('*.json')) + sorted((folder/'requests').glob('*.json'))
    if (folder/'approval.json').exists():
        files.append(folder/'approval.json')
    write_json(folder/'bundle_hashes.json', {str(p.relative_to(folder)): digest(p.read_bytes()) for p in files})
    return result


def replay(folder, allow_pending=False):
    sources, jobs, config = check(folder)
    hashes = json.loads((folder/'bundle_hashes.json').read_text())
    for name, h in hashes.items():
        path = (folder/name).resolve()
        if not path.is_relative_to(folder.resolve()) or digest(path.read_bytes()) != h:
            raise ValueError('bundle_hash_mismatch: '+name)
    for sub in ('runs', 'requests'):
        actual_names = {str(p.relative_to(folder)) for p in (folder/sub).glob('*.json')}
        sealed_names = {n for n in hashes if n.startswith(sub+'/')}
        if not sealed_names <= actual_names or (not allow_pending and actual_names != sealed_names):
            raise ValueError('bundle_inventory_changed')
    requests = 0
    seen_requests = set()
    allowed = {(c['case_id'], m): c for c in jobs for m in config['methods']}
    for path in sorted((folder/'runs').glob('*.json')):
        saved = json.loads(path.read_text())
        key = saved['case']['case_id'], saved['method']
        if allowed.get(key) != saved['case'] or path.name != '_'.join(key)+'.json':
            raise ValueError('run_not_in_frozen_jobs')
        adapter = RecordedAdapter(saved)
        actual = run_native(sources, saved['case'], saved['method'], config, adapter)
        if stable(actual) != stable(saved) or adapter.used != len(adapter.records):
            raise ValueError('run_replay_mismatch: '+path.name)
        for i, record in enumerate(adapter.records, 1):
            p = folder/'requests'/('_'.join(key)+f'.{i:02d}.json')
            if not p.exists():
                # A pre-request budget denial has no reservation; nothing was sent.
                if record.get('error') != 'paid_budget_exhausted_before_request':
                    raise ValueError('missing_request_record')
                continue
            request = json.loads(p.read_text())
            if request['request']['messages'] != record['messages'] or request['request']['max_output_tokens'] != record['max_output_tokens']:
                raise ValueError('journal_wire_mismatch')
            if request.get('response') != record.get('raw_response'):
                raise ValueError('journal_response_mismatch')
            requests += 1
            seen_requests.add(p.name)
    pending = {p.name for p in (folder/'requests').glob('*.json')} - seen_requests
    pending_prefixes = {'_'.join(k) for k in allowed if not (folder/'runs'/('_'.join(k)+'.json')).exists()}
    for name in pending:
        prefix, separator, counter = name.removesuffix('.json').rpartition('.')
        if (not allow_pending or prefix not in pending_prefixes or not counter.isdigit()
                or not 1 <= int(counter) <= config['max_calls']):
            raise ValueError('unmatched_journal_request')
    if not allow_pending and aggregate(folder, jobs) != json.loads((folder/'summary.json').read_text()):
        raise ValueError('summary_replay_mismatch')
    result = {'replayed_runs': len(list((folder/'runs').glob('*.json'))), 'journalled_requests': requests,
              'network_calls': 0, 'paid_calls': 0, 'all_requests_and_results_matched': True}
    if not allow_pending:
        write_json(folder/'replay.json', result)
    return result


def approved_cap(folder, path, config):
    approval = json.loads(path.read_text())
    if (approval.get('approved') is not True or approval.get('approved_by') != 'Nick'
            or approval.get('freeze_sha256') != digest((folder/'freeze.json').read_bytes())):
        raise ValueError('new_approval_must_bind_this_frozen_experiment')
    cap = Decimal(approval['max_usd'])
    if not cap.is_finite() or not 0 < cap <= Decimal(config['proposed_budget_usd']):
        raise ValueError('approval_cap_out_of_range')
    saved = folder/'approval.json'
    if saved.exists() and json.loads(saved.read_text()) != approval:
        raise ValueError('approval_cannot_change_on_resume')
    write_json(saved, approval)
    return cap


def execute(folder, approval, env_file=None):
    # One runner holds the budget ledger at a time, including across process crashes.
    with (folder/'execution.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sources, jobs, config = check(folder)
        if (folder/'bundle_hashes.json').exists():
            replay(folder, allow_pending=True)
        cap = approved_cap(folder, approval, config)
        if env_file:
            import os
            for line in env_file.read_text().splitlines():
                key, sep, value = line.partition('=')
                if sep and key.strip() in {'EVENTLENS_API_KEY', 'DEEPSEEK_API_KEY'}:
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")
        adapter = NativeAdapter(config)
        journal = BudgetJournal(folder/'requests', adapter, cap, config['pricing'])
        if any(json.loads(p.read_text())['state'] != 'complete' for p in (folder/'requests').glob('*.json')):
            raise ValueError('uncertain_request_requires_manual_resolution; no automatic retry')
        for case in jobs:
            for method in config['methods']:
                prefix = case['case_id']+'_'+method
                path = folder/'runs'/(prefix+'.json')
                if path.exists():
                    continue
                run = run_native(sources, case, method, config, journal.bind(prefix))
                write_json(path, run)
                save_state(folder, jobs)
                print(json.dumps({'case': case['case_id'], 'method': method, 'calls': run['calls'],
                                  'errors': run['errors'], 'charged_upper_usd': str(journal.spent())}), flush=True)
                if any('provider_' in e or 'paid_budget_' in e or 'reservation' in e for e in run['errors']):
                    return save_state(folder, jobs)
        result = save_state(folder, jobs)
        replay(folder)
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', type=Path)
    p.add_argument('--replay', type=Path)
    p.add_argument('--run', type=Path)
    p.add_argument('--approval', type=Path)
    p.add_argument('--env-file', type=Path)
    args = p.parse_args()
    if sum(x is not None for x in (args.prepare, args.replay, args.run)) != 1:
        p.error('choose exactly one of --prepare, --replay, --run')
    if args.run and not args.approval:
        p.error('--run requires a new explicit approval file')
    if not args.run and (args.approval or args.env_file):
        p.error('credentials and approval apply only to --run')
    result = (prepare(args.prepare.resolve()) if args.prepare else replay(args.replay.resolve()) if args.replay
              else execute(args.run.resolve(), args.approval, args.env_file))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
