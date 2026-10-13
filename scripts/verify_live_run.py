#!/usr/bin/env python3
"""Replay a recorded model trace against frozen public sources, without an API key."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

import eventlens
from eventlens.core import digest
from eventlens.macro.agent import run_brief
from eventlens.macro.records import MacroSource


class RecordedAdapter:
    kind = 'recorded_replay'

    def __init__(self, run):
        self.model = run['model']
        self.calls = [t for t in run['trace'] if t['stage'] == 'model_call']
        self.used = 0

    def complete(self, messages, max_output_tokens):
        if self.used >= len(self.calls):
            raise AssertionError('replay requested an unrecorded model call')
        record = self.calls[self.used]
        if messages != record['messages'] or max_output_tokens != record['max_output_tokens']:
            raise AssertionError(f'request differs at model call {self.used + 1}')
        self.used += 1
        return deepcopy(record['raw_response'])


def verify(bundle):
    original = json.loads((bundle/'run.json').read_text())
    job = json.loads((bundle/'job.json').read_text())
    records = json.loads((bundle/'sources.json').read_text())
    sources = {}
    captures = 0
    for record in records:
        source = MacroSource(**record['source'])  # Validates text hash and timestamp ordering.
        if source.source_id in sources:
            raise AssertionError('duplicate saved source')
        sources[source.source_id] = source
        for capture in record['provenance']['captures']:
            if digest(capture['content']) != capture['sha256']:
                raise AssertionError('raw capture hash mismatch')
            captures += 1
    if {s.source_id: s.content_hash for s in sources.values()} != original['source_hashes']:
        raise AssertionError('source inventory differs from the live run')
    package = Path(eventlens.__file__).parent.resolve()
    for filename, expected in original['code_hashes'].items():
        path = (package/filename).resolve()
        if not path.is_relative_to(package) or digest(path.read_bytes()) != expected:
            raise AssertionError('package differs from the recorded run: '+filename)
    request = job['request']
    adapter = RecordedAdapter(original)
    replay = run_brief(sources, request['case'], request['method'], request['config'], adapter,
                       request['cutoff_mode'], request.get('include_watchlist'))
    fields = ['case', 'source_hashes', 'eligible_source_ids', 'excluded_source_ids', 'calendar',
              'brief', 'status', 'validation', 'calls', 'tool_calls', 'tokens', 'errors', 'input_hash', 'coverage']
    for field in fields:
        if replay.get(field) != original.get(field):
            raise AssertionError('replayed result differs: '+field)
    if adapter.used != len(adapter.calls):
        raise AssertionError('replay did not consume all recorded responses')
    return {'success': True, 'execution_kind': adapter.kind, 'paid_model_calls': 0,
            'original_model': original['model'], 'original_execution_kind': original['execution_kind'],
            'source_count': len(sources), 'capture_count': captures,
            'recorded_model_responses': adapter.used, 'tool_calls': replay['tool_calls'],
            'validation_outcomes': [t['valid'] for t in replay['trace'] if t['stage'] == 'draft_validation'],
            'compared_fields': fields,
            'scope': 'Reproduces controller behavior from recorded responses; does not repeat model inference or assess claim meaning.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.bundle)
    content = json.dumps(report, indent=2)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(content)
    print(content, end='')


if __name__ == '__main__':
    main()
