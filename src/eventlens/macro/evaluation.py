"""Small, explicitly provisional engineering evaluation; no inferred model quality."""
from ..core import canonical, digest, now
from .agent import run_brief
from .report import save_run
from .validation import narrative_words
import json


def score(run, labels):
    expected = set(labels['expected_events'][run['case']['case_id']])
    included = {item['event_id'] for item in (run['brief'] or {}).get('items', [])}
    return {'case_id':run['case']['case_id'], 'method':run['method'], 'status':run['status'],
            'included_events':len(included), 'expected_events':len(expected),
            'event_precision':len(included & expected)/len(included) if included else None,
            'event_recall':len(included & expected)/len(expected) if expected else None,
            'mechanical_validation_pass':bool(run['validation'] and run['validation']['valid']),
            'claims':(run['validation'] or {}).get('claims', 0),
            'narrative_words':narrative_words(run['brief']),
            'semantic_support_accuracy':None, 'analyst_editing_time':None,
            'calls':run['calls'], 'tool_calls':run['tool_calls'], 'tokens':run['tokens'],
            'latency_ms':run['latency_ms']}


def evaluate(root, out, sources, manifest, cases, config, labels, adapter=None, cutoff_mode='publication'):
    if out.exists():
        raise ValueError('use a new evaluation output directory')
    if labels['source_hashes'] != {sid:s.content_hash for sid,s in sources.items()}:
        raise ValueError('labels refer to a different macro corpus')
    if set(labels['expected_events']) != {c['case_id'] for c in cases}:
        raise ValueError('label case coverage does not match the experiment')
    out.mkdir(parents=True)
    runs = []
    for case in cases:
        for method in (['rules', 'single', 'agent'] if adapter else ['rules']):
            run = run_brief(sources, case, method, config, adapter, cutoff_mode)
            save_run(root, out/'runs'/(case['case_id']+'-'+method), run, sources)
            runs.append(run)
    summary = {'created_at':now(), 'label_status':labels['status'], 'sources':len(sources), 'cases':len(cases),
               'method_status':{'rules':'executed', 'single':'live_attempted' if adapter else 'not_run',
                                'agent':'live_attempted' if adapter else 'not_run'},
               'metrics':[score(run, labels) for run in runs],
               'limitations':['Two related FOMC cases do not establish broad generalization.',
                              'September is a temporal check, not a blinded holdout; its sources were inspected during development.',
                              'Draft calendar labels have not been reviewed by Nick.',
                              'Mechanical validation does not measure semantic support.',
                              'Sources were captured retrospectively; publication-time replay is not a point-in-time archive.']}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (out/'labels_used.json').write_text(json.dumps(labels, indent=2)+'\n')
    (out/'provenance.json').write_text(json.dumps({'manifest_hash':digest(canonical(manifest)),
         'cases_hash':digest(canonical(cases)), 'labels_hash':digest(canonical(labels)),
         'protocol_hash':digest((root/'configs/macro_protocol.json').read_bytes()), 'config':config}, indent=2)+'\n')
    lines = ['# Macro-event evaluation', '', 'Labels: '+labels['status']+'.', '',
             '| Case | Method | Included / expected | Mechanical checks | Model calls |',
             '| --- | --- | ---: | --- | ---: |']
    for row in summary['metrics']:
        lines.append(f"| {row['case_id']} | {row['method']} | {row['included_events']} / {row['expected_events']} | {row['mechanical_validation_pass']} | {row['calls']} |")
    lines += ['', 'Single-pass and agent results: '+('live attempts saved; inspect failures and reviews' if adapter else 'not run; no live model configured')+'.',
              'Semantic accuracy and analyst editing time: unmeasured.', '', '## Limits', '']
    lines += ['- '+s for s in summary['limitations']]
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    return summary
