#!/usr/bin/env python3
"""Save/reproduce scripted controller traces. These are not live model results."""
from copy import deepcopy
import argparse
import json
from pathlib import Path

from earnings_protocol_v3 import ROOT, population
from eventlens.benchmark import RecordedAdapter, stable, write_json
from eventlens.core import digest, load_corpus
from eventlens.protocol_v3 import run_native


def response(name, arguments, ident):
    return {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None,
        'tool_calls': [{'id': ident, 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(arguments)}}]}}]}


class Scripted:
    model = 'scripted-test-fixture-not-an-LLM'
    kind = 'scripted_test_fixture_not_an_LLM'

    def __init__(self, replies):
        self.replies = iter(replies)

    def complete(self, payload, max_output_tokens):
        return deepcopy(next(self.replies))


def generate():
    config = json.loads((ROOT/'configs/earnings_protocol_v3.json').read_text())
    config = {**config, 'model': Scripted.model}
    _, sources = load_corpus(ROOT/'data/manifest.json')
    sources, jobs = population(sources, json.loads((ROOT/'data/cases.json').read_text()), config)
    case = next(c for c in jobs if c.get('challenge') == 'contradictory_commentary')
    source = sources[case['new']]
    a, b = case['transformation']['expected_conflict_quotes']
    answer = {'metrics': [], 'explanations': [], 'comparability': [],
              'conflicts': [{'topic': 'demand', 'reason': 'Scripted opposing synthetic assertions',
                  'statement_a': {'source_id': source.source_id, 'quote': a},
                  'statement_b': {'source_id': source.source_id, 'quote': b}}],
              'unresolved': 'Synthetic fixture; semantic judgment and live model behavior are untested.'}
    finish = response('finish', answer, 'finish-1')
    read = response('get_source', {'source_id': source.source_id, 'start': source.text.index(a),
                                  'end': len(source.text)}, 'read-1')
    scenarios = [
        ('retrieval_repairs_unseen_citations', case, [finish, read, response('finish', answer, 'finish-2')]),
        ('repeated_invalid_citations_stop', case, [finish, finish, finish]),
        ('stale_pair_never_calls_model', next(c for c in jobs if c.get('challenge') == 'stale_disclosure'), [])]
    files = {}
    for name, job, replies in scenarios:
        run = run_native(sources, job, 'C', config, Scripted(replies))
        replay = RecordedAdapter(run)
        actual = run_native(sources, job, 'C', config, replay)
        if stable(actual) != stable(run) or replay.used != len(replies):
            raise AssertionError('scripted_replay_mismatch')
        files[name+'.json'] = stable(run)
    repaired = files['retrieval_repairs_unseen_citations.json']
    assert not repaired['errors'] and len(repaired['validation_failures']) == 1
    assert len(repaired['conflicts'][0]['citations']) == 2
    assert files['repeated_invalid_citations_stop.json']['calls'] == 3
    assert files['repeated_invalid_citations_stop.json']['errors']
    assert files['stale_pair_never_calls_model.json']['calls'] == 0
    paths = [Path(__file__), ROOT/'scripts/earnings_protocol_v3.py', ROOT/'configs/earnings_protocol_v3.json',
             ROOT/'src/eventlens/protocol_v3.py']
    files['summary.json'] = {'scope': 'Three scripted controller fixtures, not live inference or accuracy evidence.',
        'fixture_traces': 3, 'network_calls': 0, 'paid_calls': 0,
        'all_saved_responses_and_results_replayed': True,
        'code_hashes': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths},
        'trace_hashes': {name: digest(json.dumps(value, sort_keys=True)) for name, value in files.items()}}
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    files = generate()
    for name, value in files.items():
        path = args.out/name
        if args.check:
            if json.loads(path.read_text()) != value:
                raise ValueError('scripted_fixture_changed: '+name)
        else:
            if path.exists():
                raise ValueError('preserve_existing_fixture: '+name)
            write_json(path, value)
    print(json.dumps(files['summary.json'], indent=2))


if __name__ == '__main__':
    main()
