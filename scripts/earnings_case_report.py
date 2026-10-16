#!/usr/bin/env python3
"""Render saved evidence and recomputed arithmetic without promoting model prose."""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from eventlens.core import Metric,Source,compare,digest


def render(bundle,case_id,method,out):
    bundle=Path(bundle).resolve();out=Path(out).resolve()
    run_path=bundle/'runs'/(case_id+'_'+method+'.json')
    if not run_path.resolve().is_relative_to(bundle/'runs'):
        raise ValueError('invalid_case_path')
    seals=json.loads((bundle/'bundle_hashes.json').read_text())
    for path in (run_path,bundle/'sources.json'):
        if seals.get(str(path.relative_to(bundle)))!=digest(path.read_bytes()):
            raise ValueError('saved_record_hash_mismatch')
    run=json.loads(run_path.read_text());case=run['case']
    sources={s['source_id']:Source(**s) for s in json.loads((bundle/'sources.json').read_text())}
    for sid,h in run['source_hashes'].items():
        if sources[sid].content_hash!=h:raise ValueError('source_hash_mismatch')
    metrics={x['metric']['source_id']:Metric(**x['metric']) for x in run['extractions']}
    calc=run['comparison']['calculation']
    if calc and (run['errors'] or compare(metrics.get(case['old']),metrics.get(case['new']))['calculation']!=calc):
        raise ValueError('numerical_output_does_not_recompute')
    link=os.path.relpath(run_path,out.parent)
    lines=['# '+case_id,'',f"Method {method}; fiscal horizon {case['horizon']}. [Complete saved trace]({link}).",'',
           'These are automated extraction and arithmetic results. Human review of the numbers and explanations remains pending.']
    if case.get('synthetic'):
        lines+=['','**Synthetic control.** The modified disclosure contains test data. Injected statements must not be attributed to management.']
    if run['errors']:
        lines+=['','The attempt did not produce a validated completed result. Saved errors: '+', '.join(run['errors'])+'.']
    lines+=['','## Numerical comparison','']
    if calc:
        fmt=lambda v:format(Decimal(v),',f')
        unit=calc['delta_unit']
        lines+=['| Value | Old | New | Change |','| --- | ---: | ---: | ---: |']
        for title,k in [('Lower bound','lower'),('Upper bound','upper'),('Midpoint','midpoint')]:
            lines.append(f"| {title} ({unit}) | {fmt(calc['old_'+k])} | {fmt(calc['new_'+k])} | {fmt(calc[k+'_delta'])} |")
        lines+=['','Each change is calculated with Decimal from the cited metric records. Free-form model notes do not supply these numbers.']
    else:
        lines+=['No numerical change was produced. Saved reason: `'+run['comparison']['reason']+'`. Missing values remain missing.']
    lines+=['','## Guidance evidence','']
    for side in ('old','new'):
        sid=case[side];s=sources[sid];m=metrics.get(sid)
        lines+=['### '+side.title()+': '+sid,'',f'Source SHA-256: `{s.content_hash}`.']
        synthetic=s.snapshot_kind.startswith('SYNTHETIC')
        lines+=['',('Parent disclosure URL (the modified text is saved in the execution bundle): ' if synthetic else 'Disclosure: ')+f'[{sid}]({s.url}).','']
        if m:
            if m.horizon_evidence not in s.text or m.evidence not in m.horizon_evidence:
                raise ValueError('metric_quote_not_literal')
            lines+=['> '+line for line in m.horizon_evidence.splitlines()]
        else:lines+=['No accepted metric record.']
        lines+=['']
    if run['conflicts']:
        lines+=['## Proposed conflicts','',
            'The model selected these opposing passages. Source membership is checked; natural semantic support remains pending.','']
        for conflict in run['conflicts']:
            for q in conflict['citations']:
                s=sources[q['source_id']]
                if q['quote'] not in s.text:raise ValueError('conflict_quote_not_literal')
                if 'source_hash' in q and (q['source_hash']!=s.content_hash or s.text[q['start']:q['end']]!=q['quote']):
                    raise ValueError('conflict_binding_mismatch')
                lines+=['Source: `'+q['source_id']+'`'+(' (synthetic derivative).' if s.snapshot_kind.startswith('SYNTHETIC') else '.'),'']
                lines+=['> '+line for line in q['quote'].splitlines()]+['']
    lines+=['## Review status','',
        'Model explanations, comparability notes and unresolved prose are preserved in the complete trace for review. They are not displayed as verified arithmetic or established causal explanations.','',
        'Report generation is offline and makes no model calls.','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True,type=Path)
    p.add_argument('--case',required=True);p.add_argument('--method',choices=['A','B','C','D'],default='C')
    p.add_argument('--out',required=True,type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    md=render(a.bundle,a.case,a.method,a.out)
    if a.check:
        if a.out.read_text()!=md:raise ValueError('saved_report_differs')
    else:
        if a.out.exists():raise ValueError('preserve_saved_report')
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(md)
    print(json.dumps({'report':str(a.out),'offline':True,'human_reviewed':False}))


if __name__=='__main__':main()
