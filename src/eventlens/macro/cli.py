"""Macro workflow commands, with explicit deterministic, mock, and live modes."""
from pathlib import Path
import json
import os
from uuid import uuid4

from ..core import Store, canonical, now
from ..llm import LiveAdapter
from .agent import run_brief
from .demo import scripted_adapter
from .evaluation import evaluate
from .records import calendar, load_sources, validate_case
from .report import save_run


def add_parser(sub):
    macro = sub.add_parser('macro', help='Research macro events and produce an evidence-linked brief')
    commands = macro.add_subparsers(dest='macro_command', required=True)
    commands.add_parser('validate', help='Check the saved corpus, hashes, cases, and calendar')
    commands.add_parser('ingest', help='Import immutable macro source records into SQLite')
    p = commands.add_parser('brief', help='Build a brief with rules, a single model call, or the agent')
    p.add_argument('--case', help='Saved case ID; defaults to july-2025-fomc')
    p.add_argument('--as-of', help='Custom information cutoff with a timezone')
    p.add_argument('--start', help='Custom window start, YYYY-MM-DD')
    p.add_argument('--end', help='Custom window end, YYYY-MM-DD')
    p.add_argument('--method', choices=['rules', 'single', 'agent'], default='rules')
    p.add_argument('--model')
    p.add_argument('--out', type=Path)
    p.add_argument('--cutoff-mode', choices=['publication', 'snapshot'], default='publication')
    p = commands.add_parser('mock-demo', help='Run a scripted controller demonstration; no LLM call')
    p.add_argument('--case', default='july-2025-fomc')
    p.add_argument('--repair', action='store_true', help='Demonstrate rejection and revision of an invalid citation')
    p.add_argument('--out', type=Path)
    p.add_argument('--cutoff-mode', choices=['publication', 'snapshot'], default='publication')
    p = commands.add_parser('evaluate', help='Evaluate the real calendar cases; model methods require --live')
    p.add_argument('--live', action='store_true')
    p.add_argument('--model')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cutoff-mode', choices=['publication', 'snapshot'], default='publication')
    p = commands.add_parser('review', help='Append an analyst decision without changing raw output')
    p.add_argument('--queue', type=Path, required=True)
    p.add_argument('--observation', required=True)
    p.add_argument('--reviewer', required=True)
    p.add_argument('--decision', choices=['supports', 'reject', 'uncertain'], required=True)
    p.add_argument('--note', required=True)


def execute(args):
    root = args.root.resolve()
    manifest, sources = load_sources(root/'data/macro/manifest.json')
    cases = json.loads((root/'data/macro/cases.json').read_text())
    for case in cases:
        validate_case(case)
    if len({c['case_id'] for c in cases}) != len(cases):
        raise ValueError('duplicate macro case ID')
    config = json.loads((root/'configs/macro.json').read_text())
    if args.macro_command == 'validate':
        result = {'sources':len(sources), 'cases':len(cases), 'hashes':'verified',
                  'calendars':{c['case_id']:[e['event_id'] for e in calendar(sources, c)] for c in cases}}
        print(json.dumps(result, indent=2))
        return 0
    if args.macro_command == 'ingest':
        db = Store(root/'work/eventlens.sqlite')
        try:
            added = sum(db.ingest(source) for source in sources.values())
        finally:
            db.close()
        print(json.dumps({'added':added, 'macro_sources':len(sources)}))
        return 0
    if args.macro_command == 'review':
        queue = json.loads(args.queue.read_text())
        item = next((q for q in queue if q['observation_id'] == args.observation), None)
        if item is None:
            raise ValueError('observation not in review queue')
        for sid, content_hash in item['source_hashes'].items():
            if sid not in sources or sources[sid].content_hash != content_hash:
                raise ValueError('review refers to a different source corpus')
        if not args.reviewer.strip() or not args.note.strip():
            raise ValueError('reviewer and note must be nonempty')
        review = {**item, 'decision':args.decision, 'reviewer':args.reviewer,
                  'note':args.note, 'reviewed_at':now()}
        db = Store(root/'work/eventlens.sqlite')
        try:
            db.save_review(review)
        finally:
            db.close()
        (root/'work').mkdir(exist_ok=True)
        with (root/'work/macro-reviews.jsonl').open('a') as stream:
            stream.write(canonical(review)+'\n')
        print('Review appended. Raw brief, trace, and draft labels are unchanged.')
        return 0
    adapter = None
    if getattr(args, 'out', None) is not None and args.out.exists():
        raise ValueError('use a new output directory; existing runs are never overwritten')
    if getattr(args, 'live', False) or getattr(args, 'method', 'rules') in {'single', 'agent'}:
        model = args.model or os.getenv('EVENTLENS_MODEL') or config['model']
        adapter = LiveAdapter(model)
        config = {**config, 'model':model}
    if args.macro_command == 'evaluate':
        labels = json.loads((root/'data/macro/labels.draft.json').read_text())
        summary = evaluate(root, args.out.resolve(), sources, manifest, cases, config, labels, adapter, args.cutoff_mode)
        print(json.dumps(summary, indent=2))
        return 1 if any(row['status'] == 'failed' for row in summary['metrics']) else 0
    custom = [getattr(args, k, None) for k in ('as_of', 'start', 'end')]
    if any(custom):
        if not all(custom) or args.case:
            raise ValueError('supply --as-of, --start, --end together, without --case')
        case = {'case_id':'custom-window', 'as_of':args.as_of, 'start_date':args.start,
                'end_date':args.end, 'markets':['US'], 'split':'custom',
                'question':'Prepare an evidence-linked macro-event risk brief for this window.'}
        validate_case(case)
    else:
        case = next((c for c in cases if c['case_id'] == (args.case or 'july-2025-fomc')), None)
        if case is None:
            raise ValueError('unknown macro case')
    method = getattr(args, 'method', 'agent')
    if args.macro_command == 'mock-demo':
        adapter = scripted_adapter(sources, case, args.repair, args.cutoff_mode)
    run = run_brief(sources, case, method, config, adapter, args.cutoff_mode)
    destination = args.out or root/'work/macro-runs'/str(uuid4())
    save_run(root, destination, run, sources)
    print(json.dumps({'status':run['status'], 'method':method, 'execution':run['execution_kind'],
                      'events':len(run['calendar']), 'model_calls':run['calls'], 'tool_calls':run['tool_calls'],
                      'brief':str(destination/'brief.md'), 'trace':str(destination/'run.json')}, indent=2))
    return 1 if run['status'] == 'failed' else 0
