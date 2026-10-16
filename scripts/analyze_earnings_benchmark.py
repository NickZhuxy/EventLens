#!/usr/bin/env python3
"""Summarize frozen run outputs without tuning methods or promoting draft labels."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics


def analyze(bundle):
    runs=[json.loads(p.read_text()) for p in sorted((bundle/'runs').glob('*.json'))]
    requests=[json.loads(p.read_text()) for p in sorted((bundle/'requests').glob('*.json'))]
    groups=defaultdict(list)
    for run in runs:groups[(run['method'],run['case']['split'])].append(run)
    costs=defaultdict(Decimal)
    for path in (bundle/'requests').glob('*.json'):
        request=json.loads(path.read_text());method=path.name.rsplit('_',1)[1].split('.')[0]
        costs[method]+=Decimal(request['charged_upper_usd'])
    methods=[]
    for (method,split),rows in sorted(groups.items()):
        latencies=[r['latency_ms']/1000 for r in rows]
        errors=Counter(e for r in rows for e in r['errors'])
        rejected=Counter(e for r in rows for x in r['extractions'] for e in x['validation']['errors'])
        reason=Counter(r['comparison']['reason'] for r in rows)
        model_calls=[c for r in rows for c in r['trace'] if c['stage']=='model_call']
        incomplete=sum(c.get('raw_response',{}).get('choices',[{}])[0].get('finish_reason')=='length' for c in model_calls)
        methods.append({'method':method,'split':split,'n':len(rows),
            'numerical_outputs':sum(r['comparison']['calculation'] is not None for r in rows),
            'withdrawal_flags':sum(r['comparison']['reason']=='guidance_withdrawn' for r in rows),
            'apparent_conflicts':sum(bool(r.get('conflicts')) for r in rows),
            'abstentions':sum(r['conclusion']=='insufficient_evidence' for r in rows),
            'calls':sum(r['calls'] for r in rows),'tool_calls':sum(t['stage']=='tool_call' for r in rows for t in r['trace']),
            'prompt_tokens':sum((r['tokens'] or {}).get('prompt_tokens',0) for r in rows),
            'completion_tokens':sum((r['tokens'] or {}).get('completion_tokens',0) for r in rows),
            'reasoning_tokens_reported':sum(c.get('raw_response',{}).get('usage',{}).get('completion_tokens_details',{}).get('reasoning_tokens',0) for c in model_calls),
            'missing_token_usage_runs':sum(r['calls']>0 and r['tokens'] is None for r in rows),
            'median_latency_seconds':round(statistics.median(latencies),3),
            'p95_latency_seconds':round(sorted(latencies)[max(0,int(.95*len(latencies)+.999)-1)],3),
            'output_truncated_calls':incomplete,'errors':dict(errors),'validation_errors':dict(rejected),'comparison_reasons':dict(reason)})
    controls=defaultdict(list)
    for run in runs:
        if run['case']['split']=='synthetic_heldout':
            controls[(run['method'],run['case']['challenge'])].append(run)
    stress=[]
    for (method,challenge),rows in sorted(controls.items()):
        valid=matched=both=fabricated=retrieved=0
        for run in rows:
            # Stale eligibility rejection is the intended successful guard action.
            allowed={'stale_or_reversed_disclosure_pair'} if challenge=='stale_disclosure' else set()
            executed=not (set(run['errors'])-allowed)
            matches=run['conclusion']==run['case']['expected_status']
            matched+=matches
            valid+=executed and matches
            if challenge=='contradictory_commentary':
                expected=set(run['case']['transformation']['expected_conflict_quotes'])
                both+=executed and matches and any(expected=={c['quote'] for c in flag['citations']} for flag in run['conflicts'])
                if method=='C':
                    windows=[]
                    for tool in (t for t in run['trace'] if t['stage']=='tool_call'):
                        output=tool['result']
                        windows.extend(part['quote'] for part in output.get('passages',[output]) if 'quote' in part)
                    retrieved+=all(any(quote in window for window in windows) for quote in expected)
            else:
                fabricated+=any(x['metric']['source_id']==run['case']['new'] and x['metric']['status']=='provided' for x in run['extractions'])
        stress.append({'method':method,'challenge':challenge,'n':len(rows),
            'status_matches':matched,'valid_expected_decisions':valid,'valid_expected_decision_rate':valid/len(rows),
            'both_expected_citations':both if challenge=='contradictory_commentary' else None,
            'both_expected_statements_retrieved':retrieved if method=='C' and challenge=='contradictory_commentary' else None,
            'absent_source_metric_candidates':fabricated if challenge!='contradictory_commentary' else None})
    decisions=[]
    for r in runs:
        if r['method']!='C':continue
        tools=[t for t in r['trace'] if t['stage']=='tool_call']
        if not tools:continue
        if r.get('conflicts'):
            decisions.append({'case_id':r['case']['case_id'],'kind':'synthetic_conflict' if r['case'].get('synthetic') else 'natural_apparent_conflict',
                              'citations':r['conflicts'],'calls':r['calls'],'tool_calls':len(tools)})
        elif r['comparison']['calculation'] is not None and r['case']['split']=='development':
            decisions.append({'case_id':r['case']['case_id'],'kind':'numerical_example','comparison':r['comparison'],'calls':r['calls'],'tool_calls':len(tools)})
    priced=[r for r in requests if r['state']=='complete']
    usage={k:sum(r.get('provider_usage',{}).get(k,0) for r in priced) for k in ('prompt_tokens','completion_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens')}
    return {'bundle':str(bundle),'complete_runs':len(runs),'request_attempts':len(requests),'completed_requests':len(priced),
            'request_states':dict(Counter(r['state'] for r in requests)),
            'cost_upper_usd':str(sum(costs.values(),Decimal(0))),'cost_upper_by_method_usd':{m:str(v) for m,v in sorted(costs.items())},
            'cost_basis':'Peak price with every input token treated as a cache miss; uncertain requests retain the full reservation. Not an invoice.',
            'provider_usage':usage,'methods':methods,'stress':stress,'investigation_examples':decisions,
            'stress_definition':'Valid expected decisions require the expected status and no controller errors, except the intended stale-pair eligibility rejection. Rejected metric candidates remain separately visible. All attempted runs remain in the denominator; these are construction-known synthetic controls, not reviewed natural labels.',
            'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_bundle_hashes_sha256':hashlib.sha256((bundle/'bundle_hashes.json').read_bytes()).hexdigest(),
            'interpretation':'Counts are coverage and engineering evidence. No natural-case accuracy or superiority claim until human label and explanation review.'}


def text(report):
    lines=['# Earnings benchmark execution analysis','',f"Completed method/case runs: {report['complete_runs']}; request attempts: {report['request_attempts']}; conservative cost: USD {report['cost_upper_usd']}.",
        '',report['cost_basis'],'',report['interpretation'],'',
        '| Method | Split | n | Numerical outputs | Conflict flags | Abstentions | Calls | Median seconds | Truncated calls |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for m in report['methods']:
        lines.append(f"| {m['method']} | {m['split']} | {m['n']} | {m['numerical_outputs']} | {m['apparent_conflicts']} | {m['abstentions']} | {m['calls']} | {m['median_latency_seconds']} | {m['output_truncated_calls']} |")
    lines += ['', '## Stress controls with execution failures excluded from success', '', report['stress_definition'], '',
        '| Method | Control | n | Raw status matches | Valid expected decisions | Both expected citations | Absent-source metric candidates |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for s in report['stress']:
        both='n/a' if s['both_expected_citations'] is None else str(s['both_expected_citations'])
        fabricated='n/a' if s['absent_source_metric_candidates'] is None else str(s['absent_source_metric_candidates'])
        lines.append(f"| {s['method']} | {s['challenge']} | {s['n']} | {s['status_matches']} | {s['valid_expected_decisions']} | {both} | {fabricated} |")
    lines += ['', '## Failure categories', '']
    for m in report['methods']:
        if m['errors'] or m['validation_errors']:
            lines += [f"- {m['method']} / {m['split']}: controller errors {json.dumps(m['errors'],sort_keys=True)}; metric-screen errors {json.dumps(m['validation_errors'],sort_keys=True)}."]
    lines += ['', 'An output-limit failure is reported as a failed attempt, not a successful abstention or proof that a model cannot extract the answer. The same frozen per-call limit applies to B and C, but B must complete the entire task in one response; this budget can disadvantage B. The comparison is not compute matched.',
              'The missing-table control removes all numerical content, including headings and actuals. It measures behavior under broad missing numerical evidence, not isolated table removal. Contradictory-control assertions are synthetic. Natural explanation support remains unreviewed.',
              'Absent-source metric counts cover extracted candidates, including candidates rejected by the metric screen. A malformed response or an earlier controller rejection can prevent candidate extraction. Zero counted candidates therefore does not establish zero fabrication across all raw model text; failed attempts remain failures.',
              'The contradiction controls use a known opposite-polarity template. Its vocabulary appears in the C search hint and the A/D lexical checker. Their scores test retrieval, protocol handling and citation validation for this known construction; they do not establish generalization to unseen natural contradictions.',
              'For each saved C example, inspect its tool requests, returned passages, final quotations and Python validation in the source bundle. The analysis retains failed cases rather than selecting only successful examples.', '']
    return '\n'.join(lines)


def example(bundle):
    """Use the original pilot example, explicitly outside held-out accuracy claims."""
    name='ADBE-FY2025-Q2-Q3_C'
    path=bundle/'runs'/(name+'.json')
    if not path.exists():return 'The original Adobe pilot example has no saved C run yet.\n'
    run=json.loads(path.read_text())
    sources={s['source_id']:s for s in json.loads((bundle/'sources.json').read_text())}
    lines=['# Saved retrieval example: Adobe FY2025 Q2 to Q3','',
        'This is a development example from the original pilot. It illustrates the execution trace and does not estimate benchmark accuracy.', '',
        f"Source run: `{bundle / 'runs' / (name+'.json')}`.", '',
        f"Model calls: {run['calls']}. Conclusion: `{run['conclusion']}`. Controller errors: `{json.dumps(run['errors'])}`.", '',
        '## Retrieved evidence', '']
    for extraction in run['extractions']:
        metric=extraction['metric'];source=sources[metric['source_id']]
        lines += [f"[{source['source_id']}]({source['url']}):",'',
            '> '+metric['horizon_evidence'].replace('\n','\n> '),'',
            f"Saved source hash: `{source['content_hash']}`. Metric validation: `{extraction['validation']['semantic_screen']}`.",'']
    calc=run['comparison']['calculation']
    if calc:
        lines += ['## Python calculation','',f"Old midpoint: USD {calc['old_midpoint']}. New midpoint: USD {calc['new_midpoint']}. Change: USD {calc['midpoint_delta']}.", '',
            'These values come from the validated ranges. The model does not supply the arithmetic result.', '']
    lines += ['## Retrieval actions', '', '| Step | Tool | Arguments |', '| ---: | --- | --- |']
    for i,tool in enumerate((t for t in run['trace'] if t['stage']=='tool_call'),1):
        lines.append(f"| {i} | `{tool['name']}` | `{json.dumps(tool['arguments'],sort_keys=True)}` |")
    lines += ['', 'Each returned passage and every model request and response are in the source run. Explanation support still requires human review.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args()
    report=analyze(a.bundle);values={'analysis.json':json.dumps(report,indent=2,ensure_ascii=False)+'\n','analysis.md':text(report),'adobe_example.md':example(a.bundle)}
    if a.check:
        for name,content in values.items():
            if (a.out/name).read_text()!=content:raise ValueError('analysis no longer matches saved runs: '+name)
        print('Analysis reproduced from saved run files.');return
    if a.out.exists():raise ValueError('use a new analysis directory; preserve earlier results')
    a.out.mkdir(parents=True)
    for name,content in values.items():(a.out/name).write_text(content)
    print(json.dumps({'runs':report['complete_runs'],'requests':report['request_attempts'],'cost_upper_usd':report['cost_upper_usd']}))

if __name__=='__main__':main()
