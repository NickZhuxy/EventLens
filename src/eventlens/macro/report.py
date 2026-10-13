"""Readable briefs and append-only research artifacts."""
from pathlib import Path
import json
import re

from ..core import Store, canonical, digest


def safe(text):
    return re.sub(r'([\\`*_{}\[\]<>#|])', r'\\\1', str(text)).replace('\n', ' ')


def render_brief(run, sources):
    if run.get('broad_scope'):
        return render_global_brief(run, sources)
    case = run['case']
    lines = ['# Macro-event brief', '',
             f"Window: {case['start_date']} to {case['end_date']} · Markets: {', '.join(case['markets'])}",
             f"Information cutoff: {case['as_of']} · Mode: {run['cutoff_mode']}",
             f"Method: {run['method']} · Execution: {run['execution_kind']} · Status: {run['status']}", '',
             'Coverage: dated events found in the saved corpus. Watchlist selection is disabled.', '']
    if run['execution_kind'] == 'mock':
        lines += ['**Scripted controller demonstration. No LLM made these decisions.**', '']
    if run['cutoff_mode'] == 'publication':
        lines += ['Historical replay uses publication dates. These snapshots were retrieved later; their historical contents are not independently archived.', '']
    brief = run['brief']
    if brief is None:
        lines += ['No validated brief was produced.', '', 'Errors: '+safe('; '.join(run['errors'])), '']
        return '\n'.join(lines)
    refs = {}

    def cite(evidence):
        labels = []
        for entry in evidence:
            key = (entry['source_id'], entry['start'], entry['end'])
            if key not in refs:
                refs[key] = (len(refs)+1, entry)
            labels.append(f"[{refs[key][0]}]")
        return ' '.join(labels)

    events = {e['event_id']:e for e in run['calendar']}
    for item in brief['items']:
        event = events[item['event_id']]
        lines += [f"## {event['name']} · {event['start_date']}–{event['end_date']}", '',
                  'Date source: '+cite(event['date_evidence'])+'. Dates use '+event['timezone']+'.', '']
        for kind, title in [('fact','Known context'), ('expectation','Market expectations'), ('risk','Possible risk effects')]:
            claims = [c for c in item['claims'] if c['kind'] == kind]
            lines += ['**'+title+'**', '']
            if not claims:
                lines += [{'fact':'No context claim was supported by this run.',
                           'expectation':'Not established by the evidence returned in this run.',
                           'risk':'No risk interpretation was produced by this method.'}[kind], '']
            for claim in claims:
                label = 'Interpretation; analyst review pending' if kind == 'risk' else claim['context'].capitalize()
                if kind == 'risk':
                    label += '; '+claim['channel']
                lines.append(f"- {safe(claim['statement'])} {cite(claim['evidence'])} ({label}.)")
            if claims:
                lines.append('')
        if item['gaps']:
            lines += ['**Research gaps**', ''] + ['- '+safe(g) for g in item['gaps']] + ['']
    if not brief['items']:
        lines += ['No event was included. An empty result does not establish that no market events exist.', '']
    if brief['omissions']:
        lines += ['## Omitted events', '']
        lines += ['- '+safe(x['event_id'])+': '+safe(x['reason']) for x in brief['omissions']]
        lines.append('')
    if refs:
        lines += ['## Evidence', '']
        for number, entry in refs.values():
            source = sources[entry['source_id']]
            lines += [f"[{number}] [{safe(source.title)}]({source.url}) — context {source.document_date}; published {source.published_at}.",
                      f"> {safe(entry['quote'])}", '',
                      f"Source `{source.source_id}`, characters {entry['start']}–{entry['end']}; SHA-256 `{source.content_hash}`.", '']
    lines += ['Mechanical checks verify source identity, cutoff, literal citations, and record structure. They do not establish semantic support or predict market outcomes.',
              'Analyst review is pending.', '']
    return '\n'.join(lines)


def review_queue(run, sources):
    result = []
    for item in (run['brief'] or {}).get('items', []):
        for claim in item['claims']:
            result.append({'observation_id':digest(canonical({'run_id':run['run_id'], 'event_id':item['event_id'], 'claim':claim})),
                           'run_id':run['run_id'], 'event_id':item['event_id'], 'claim':claim,
                           'source_hashes':{c['source_id']:sources[c['source_id']].content_hash for c in claim['evidence']},
                           'decision':'pending', 'reviewer':None,
                           'checks':['Does the quotation support the statement, including its attribution?',
                                     'Is the context date appropriate for this briefing?',
                                     'Are expectations separate from official policy and historical facts?',
                                     'Is the risk note conditional, relevant, and free of unsupported price predictions?']})
    return result


def save_run(root, destination, run, sources):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('use a new output directory; existing runs are never overwritten')
    destination.mkdir(parents=True)
    package = Path(__file__).parent
    run['code_hashes'] = {str(p.relative_to(package.parent)):digest(p.read_bytes())
                         for p in sorted(package.glob('*.py')) + [package.parent/'core.py', package.parent/'llm.py']}
    files = {'run.json':run, 'review_queue.json':review_queue(run, sources)}
    for name, value in files.items():
        (destination/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    (destination/'brief.md').write_text(render_brief(run, sources))
    (destination/'calendar.csv').write_text(render_calendar_csv(run, sources), encoding='utf-8-sig')
    db = Store(Path(root)/'work/eventlens.sqlite')
    try:
        for source in sources.values():
            db.ingest(source)
        db.save_run(run)
    finally:
        db.close()
    return destination


def render_calendar_csv(run, sources):
    """Excel-compatible coverage export. Neutralize formula-leading imported text."""
    import csv
    import io
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['Date from', 'Date to', 'Date status', 'Event', 'Explanation', 'Frequency',
                     'Markets', 'Assets', 'Research priority', 'Historical impact', 'Analyst views',
                     'Risk assessment', 'Selected', 'Evidence URLs', 'Coverage note'])
    items = {i['event_id']:i for i in (run['brief'] or {}).get('items', [])}
    for event in run['calendar']:
        item = items.get(event['event_id'], {'claims':[]})
        def statements(kind):
            return ' | '.join(c['statement'] for c in item['claims'] if c['kind'] == kind)
        ids = {c['source_id'] for c in event['date_evidence']}
        ids.update(c['source_id'] for claim in item['claims'] for c in claim['evidence'])
        row = [event['start_date'] or '', event['end_date'] or '', event.get('date_status', 'confirmed'),
               event['name'], event.get('explanation', ''), event.get('cadence', ''),
               ', '.join(event['markets']), ', '.join(event.get('assets', [])), event.get('priority', ''),
               statements('historical_impact'), statements('analyst_view'), statements('risk'),
               'yes' if event['event_id'] in items else 'no', ' | '.join(sorted({sources[sid].url for sid in ids})),
               event.get('coverage_note', '')]
        writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for v in row])
    return stream.getvalue()


def render_global_brief(run, sources):
    case, brief = run['case'], run['brief']
    lines = ['# Macro-event brief', '',
             f"{case['start_date']} to {case['end_date']} · Markets: {', '.join(case['markets'])}",
             f"Cutoff: {case['as_of']} ({run['cutoff_mode']}) · Method: {run['method']} · Status: {run['status']}", '']
    if run['execution_kind'] == 'mock':
        lines += ['**Scripted test; no live model made these decisions.**', '']
    if run['method'] == 'rules':
        lines += ['**Calendar extraction only. Risk analysis requires an agent run and supporting sources.**', '']
    if run.get('collection_report', {}).get('errors'):
        failures = ', '.join(sorted({e['provider'] for e in run['collection_report']['errors']}))
        lines += ['Source refresh incomplete: '+safe(failures)+'. Other collected sources remain available.', '']
    if brief is None:
        return '\n'.join(lines+['No validated brief was produced. Errors: '+safe('; '.join(run['errors'])), ''])
    refs = {}
    def cite(evidence):
        labels = []
        for entry in evidence:
            key = (entry['source_id'], entry['start'], entry['end'])
            if key not in refs:
                refs[key] = (len(refs)+1, entry)
            labels.append(f'[{refs[key][0]}]')
        return ' '.join(labels)
    events = {e['event_id']:e for e in run['calendar']}
    lines += ['## Important events', '', '| Date / status | Event | Markets / assets | Research priority |',
              '| --- | --- | --- | --- |']
    for item in brief['items']:
        event = events[item['event_id']]
        when = ((event['start_date']+' to '+event['end_date']) if event['start_date'] != event['end_date']
                else event['start_date']) if event['start_date'] else 'Date unverified'
        when += ' / '+event['date_status']
        lines.append('| '+safe(when)+' '+cite(event['date_evidence'])+' | '+safe(event['name'])+' | '+
                     safe(', '.join(event['markets'])+' / '+', '.join(event.get('assets', [])))+' | '+safe(event['priority'])+' |')
    lines += ['', 'Priority is a research setting. It is not a measured historical volatility rating.', '']
    labels = {'fact':'Context', 'expectation':'Market expectation', 'historical_impact':'Historical impact',
              'analyst_view':'Analyst view', 'risk':'Risk assessment'}
    for item in brief['items']:
        event = events[item['event_id']]
        lines += ['**'+safe(event['name'])+'** — '+safe(event.get('explanation', '')), '']
        for claim in item['claims']:
            label = labels[claim['kind']]
            if claim['kind'] == 'risk':
                label += ' / '+claim['channel']
            lines += [f"- {label}: {safe(claim['statement'])} {cite(claim['evidence'])} ({claim['context']})"]
        if item['gaps']:
            lines += ['- Evidence needed: '+safe(' '.join(item['gaps']))]
        lines.append('')
    undated = sum(e.get('date_status') == 'watchlist' for e in run['calendar'])
    lines += [f"Coverage: {len(brief['items'])} selected from {len(events)} candidates; {undated} have no verified date in this window. The full calendar and watchlist are in `calendar.csv`.", '']
    if refs:
        lines += ['## Sources', '']
        for number, entry in refs.values():
            source = sources[entry['source_id']]
            lines.append(f"[{number}] [{safe(source.publisher+': '+source.title)}]({source.url}) · context {source.document_date} · `{source.source_id}:{entry['start']}:{entry['end']}`")
        lines.append('')
    lines += ['Source passages, model actions, and omitted candidates remain in the run record. Claim interpretation requires analyst review.', '']
    return '\n'.join(lines)
