"""Local CLI. Experiment paths are explicit and every run is append-only."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import sys
from uuid import uuid4
from . import __version__
from .core import load_corpus, Store, now, digest, timestamp, Metric, canonical
from .pipeline import run_pair
from .challenges import make_challenges
from .evaluation import score, report_text
from .llm import LiveAdapter, MockAdapter, SYSTEM, CONTROLLER, PROMPT_VERSION


def write_json(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def load_cases(root,sources):
    cases=json.loads((root/'data/cases.json').read_text())
    ids=set()
    protocol=json.loads((root/'configs/protocol.json').read_text())
    for case in cases:
        if case['case_id'] in ids:raise ValueError('duplicate case_id')
        ids.add(case['case_id'])
        timestamp(case['cutoff'])
        for side in ['old','new']:
            s=sources[case[side]]
            if s.issuer!=case['issuer'] or case['horizon'] not in s.forecast_horizons:
                raise ValueError('case identity/horizon metadata mismatch')
        split=case['split']
        if split not in ['development','heldout'] or case['issuer'] not in protocol[split+'_issuers']:
            raise ValueError('case violates issuer split')
    return cases


def persist_run(root,run,out=None):
    destination=Path(out) if out else root/'reports/runs'/f"{run['run_id']}.json"
    if destination.exists():raise ValueError('refusing to overwrite an existing run')
    write_json(destination,run)
    db=Store(root/'work/eventlens.sqlite')
    try:db.save_run(run)
    finally:db.close()
    return destination


def run_review_queue(runs,sources):
    queue=[]
    for r in runs:
        for x in r['extractions']:
            m=x['metric']
            queue.append({'run_id':r['run_id'],'case_id':r['case']['case_id'],
                'kind':'metric','observation_id':x['validation']['observation_id'],
                'source_hash':r['source_hashes'][m['source_id']], 'metric':m,
                'decision':'pending','reviewer':None,
                'checks':['Correct issuer, annual horizon, and column?', 'Revenue versus segment revenue or actual result?',
                          'Correct bounds, currency, scale, and accounting basis?', 'Literal passage actually supports the interpretation?']})
        for x in r['explanations']:
            queue.append({'run_id':r['run_id'],'case_id':r['case']['case_id'],'kind':'explanation',
                'observation_id':digest(canonical(x)), 'source_hash':r['source_hashes'][x['source_id']],
                'candidate':x,'decision':'pending','reviewer':None,
                'checks':['Is the statement about this guidance horizon?', 'Does it explicitly explain the revision?',
                          'Is it only general promotion or a hypothesis?', 'Is another passage contradictory?']})
    return queue


def provenance(root,manifest,cases,labels,config):
    code={p.name:digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    files=['data/manifest.json','data/cases.json','configs/protocol.json','configs/freeze.json']
    return {'created_at':now(),'python':platform.python_version(),'platform':platform.platform(),
            'eventlens_version':__version__,'command':sys.argv,'code_hashes':code,
            'input_file_hashes':{f:digest((root/f).read_bytes()) for f in files},
            'dataset_hash':digest(canonical(manifest)), 'case_hash':digest(canonical(cases)),
            'label_hash':digest(canonical(labels)), 'configuration':config,
            'prompts':{'version':PROMPT_VERSION,'extraction':SYSTEM,'controller':CONTROLLER}}


def print_demo(run):
    c=run['comparison'];print(f"{run['case']['case_id']} | {run['method']} | {run['conclusion']} | {c['reason']}")
    for x in run['extractions']:
        m=x['metric'];print(f"  {m['source_id']} {m['horizon']}: {m['lower']}..{m['upper']} {m['currency']} {m['unit']}")
        print('  Evidence:',m['evidence'])
    if c['calculation']:
        n=c['calculation'];print(f"  Python: ({n['new_lower']} + {n['new_upper']})/2 - ({n['old_lower']} + {n['old_upper']})/2 = {n['midpoint_delta']} {n['delta_unit']}")
    print('  Explanation:',run['explanation_conclusion']['status'],';',run['explanation_conclusion']['reason'])
    print('  Human semantic review: pending')


def main(argv=None):
    parser=argparse.ArgumentParser(description='EventLens — macro-event research and evidence-linked briefs')
    parser.add_argument('--root',type=Path,default=Path.cwd(),help='Project data/config root')
    sub=parser.add_subparsers(dest='command',required=True)
    from .macro.cli import add_parser as add_macro_parser, execute as execute_macro
    add_macro_parser(sub)
    sub.add_parser('validate');sub.add_parser('ingest');sub.add_parser('demo')
    p=sub.add_parser('compare');p.add_argument('--case',required=True);p.add_argument('--method',choices=['A','B','C'],default='A')
    p.add_argument('--cutoff-mode',choices=['disclosure','snapshot'],default='disclosure')
    p.add_argument('--model');p.add_argument('--out',type=Path)
    p=sub.add_parser('evaluate');p.add_argument('--live',action='store_true');p.add_argument('--model')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--labels',type=Path)
    p.add_argument('--cutoff-mode',choices=['disclosure','snapshot'],default='disclosure')
    sub.add_parser('mock-demo')
    p=sub.add_parser('review');p.add_argument('--queue',type=Path,required=True);p.add_argument('--observation',required=True)
    p.add_argument('--reviewer',required=True);p.add_argument('--decision',choices=['supports','reject','uncertain'],required=True)
    p.add_argument('--note',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='macro':
            return execute_macro(args)
        root=args.root.resolve();manifest,sources=load_corpus(root/'data/manifest.json');cases=load_cases(root,sources)
        config=json.loads((root/'configs/model.json').read_text())
        if args.command=='validate':
            eligible=[c for c in cases if all(sources[c[k]].eligible(c['cutoff']) for k in ['old','new'])]
            print(json.dumps({'documents':len(sources),'issuers':len({s.issuer for s in sources.values()}),
                'eligible_comparisons':len(eligible),'development_pairs':sum(c['split']=='development' for c in cases),
                'heldout_pairs':sum(c['split']=='heldout' for c in cases),'source_hashes':'verified'}));return 0
        if args.command=='ingest':
            db=Store(root/'work/eventlens.sqlite')
            try:
                added=sum(db.ingest(s) for s in sources.values());total=db.db.execute('select count(*) from sources').fetchone()[0]
            finally:db.close()
            print(json.dumps({'added':added,'total_sources':total}));return 0
        if args.command=='review':
            queue=json.loads(args.queue.read_text());matches=[x for x in queue if x['observation_id']==args.observation]
            if not matches:raise ValueError('observation not found in queue')
            item=matches[0]
            if item['source_hash'] not in {s.content_hash for s in sources.values()}:
                raise ValueError('review source hash does not match real corpus')
            if not args.reviewer.strip() or not args.note.strip():raise ValueError('reviewer and note required')
            review={**item,'decision':args.decision,'reviewer':args.reviewer,'note':args.note,'reviewed_at':now()}
            db=Store(root/'work/eventlens.sqlite')
            try:db.save_review(review)
            finally:db.close()
            with (root/'data/reviews.jsonl').open('a') as f:f.write(canonical(review)+'\n')
            print('Review appended. Raw output and draft labels unchanged.');return 0
        adapter=None
        if getattr(args,'live',False) or getattr(args,'method','A') in ['B','C']:
            model=getattr(args,'model',None) or os.getenv('EVENTLENS_MODEL') or config['model']
            adapter=LiveAdapter(model);config={**config,'model':model}
        if args.command=='compare':
            matching=[c for c in cases if c['case_id']==args.case]
            if not matching:raise ValueError('unknown case id')
            r=run_pair(sources,matching[0],args.method,adapter,config,args.cutoff_mode)
            path=persist_run(root,r,args.out);print_demo(r);print('Saved:',path);return 0
        if args.command=='demo':
            base=next(c for c in cases if c['split']=='development')
            print('A = deterministic rules. B/C live results: not part of this offline demo. Labels: AI-draft.')
            demo=[(sources,base)]+[x for x in make_challenges(sources,base) if x[1]['case_id'].endswith(('missing_table','contradictory_explanations'))]
            demo += [(sources,c) for c in cases if c['issuer']=='CRM']
            for data,c in demo:
                r=run_pair(data,c);path=persist_run(root,r);print_demo(r);print('  Trace:',path)
            return 0
        if args.command=='mock-demo':
            base=next(c for c in cases if c['split']=='development')
            from .extraction import extract
            metrics=[asdict(extract(sources[base[k]],base['horizon'])[0]) for k in ['old','new']]
            replies=[]
            for k,m in zip(['old','new'],metrics):
                s=sources[base[k]];start=s.text.index(m['horizon_evidence']);end=start+len(m['horizon_evidence'])
                replies.append({'action':'tool','name':'get_source','arguments':{'source_id':s.source_id,'start':start,'end':end},
                                'reason':'Scripted fixture retrieves a known annual heading and row. This is not a model decision.'})
            replies.append({'action':'finish','metrics':metrics,'explanations':[]})
            r=run_pair(sources,base,'C',MockAdapter(replies),config)
            path=persist_run(root,r);print('MOCK ENGINEERING DEMO — NOT AN LLM RESULT');print_demo(r);print('Saved:',path);return 0
        if args.command=='evaluate':
            out=args.out.resolve()
            if out.exists():raise ValueError('use a new output directory to preserve prior results')
            labels=json.loads((args.labels or root/'data/labels.draft.json').read_text())
            if labels['source_hashes']!={sid:s.content_hash for sid,s in sources.items()}:
                raise ValueError('labels refer to a different corpus')
            runs=[];methods=['A','B','C'] if args.live else ['A']
            for c in cases:
                for method in methods:runs.append(run_pair(sources,c,method,adapter,config,args.cutoff_mode))
            base=next(c for c in cases if c['split']=='development')
            for data,c in make_challenges(sources,base):
                for method in methods:runs.append(run_pair(data,c,method,adapter,config,args.cutoff_mode))
            out.mkdir(parents=True)
            for data,c in make_challenges(sources,base):
                if c['new'] not in sources:
                    write_json(out/'synthetic_sources'/f"{c['new']}.json",asdict(data[c['new']]))
            for r in runs:persist_run(root,r,out/'runs'/f"{r['case']['case_id']}_{r['method']}.json")
            statuses={'A':'executed deterministic rules','B':'not_run_no_live_model','C':'not_run_no_live_model'}
            if args.live:
                for method in ['B','C']:
                    mr=[r for r in runs if r['method']==method]
                    statuses[method]=f"live attempts: {len(mr)}; calls: {sum(r['calls'] for r in mr)}; runs with errors: {sum(bool(r['errors']) for r in mr)}"
            summary={'created_at':now(),'corpus':{'documents':len(sources),'issuers':len({s.issuer for s in sources.values()}),
                         'eligible_comparisons':sum(all(sources[c[k]].eligible(c['cutoff'],args.cutoff_mode) for k in ['old','new']) for c in cases)},
                     'synthetic_controls':sum(r['case']['synthetic'] for r in runs if r['method']=='A'),
                     'methods':statuses,'metrics':score(runs,labels),'failures':[{'case_id':r['case']['case_id'],'method':r['method'],
                     'status':r['conclusion'],'reason':r['explanation_conclusion']['reason'] if r['explanation_conclusion']['status']=='conflicting' else r['comparison']['reason']}
                     for r in runs if r['conclusion']!='supported']}
            write_json(out/'summary.json',summary);write_json(out/'review_queue.json',run_review_queue(runs,sources))
            write_json(out/'provenance.json',provenance(root,manifest,cases,labels,config))
            write_json(out/'labels_used.json',labels)
            (out/'report.md').write_text(report_text(summary))
            print(json.dumps(summary,indent=2));print('Saved:',out);return 0
        return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(f'EventLens error: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
