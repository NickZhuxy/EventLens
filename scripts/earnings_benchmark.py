#!/usr/bin/env python3
"""Prepare, run, resume or replay the v2 earnings benchmark. Live mode needs a budget record."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from eventlens.core import Source, digest, load_corpus, now
from eventlens.benchmark import (BudgetJournal, RecordedAdapter, population, report_text,
                                 run_investigation, stable, summary, write_json)
from eventlens.llm import LiveAdapter

ROOT=Path(__file__).resolve().parents[1]


def code_hashes():
    paths=list((ROOT/'src/eventlens').rglob('*.py'))+[Path(__file__)]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(paths)}


def prepare(folder):
    if folder.exists():raise ValueError('use a new bundle directory or --resume')
    _,sources=load_corpus(ROOT/'data/manifest.json')
    cases=json.loads((ROOT/'data/cases.json').read_text())
    sources,jobs=population(sources,cases)
    config=json.loads((ROOT/'configs/earnings_benchmark_v2.json').read_text())
    folder.mkdir(parents=True)
    write_json(folder/'sources.json',[asdict(s) for s in sources.values()])
    write_json(folder/'jobs.json',jobs);write_json(folder/'config.json',config)
    write_json(folder/'labels.json',{'status':'pending','cases':{}})
    write_json(folder/'freeze.json',{'frozen_at':now(),'code_hashes':code_hashes(),
        'input_hashes':{name:digest((folder/name).read_bytes()) for name in ('sources.json','jobs.json','config.json')},
        'protocol':'No tuning on v2 held-out model outputs. A/D and shared numerical validation unchanged from M1/M3. Synthetic controls are construction-known, natural label review pending.'})


def check(folder):
    frozen=json.loads((folder/'freeze.json').read_text())
    for name,h in frozen['code_hashes'].items():
        if digest((ROOT/name).read_bytes())!=h:raise ValueError('frozen_code_changed: '+name)
    for name,h in frozen['input_hashes'].items():
        if digest((folder/name).read_bytes())!=h:raise ValueError('frozen_input_changed: '+name)
    sources={}
    for value in json.loads((folder/'sources.json').read_text()):
        s=Source(**value)
        if s.source_id in sources:raise ValueError('duplicate_source')
        sources[s.source_id]=s
    return sources,json.loads((folder/'jobs.json').read_text()),json.loads((folder/'config.json').read_text())


def load_env(path):
    allowed={'EVENTLENS_API_KEY','DEEPSEEK_API_KEY','EVENTLENS_MODEL','EVENTLENS_BASE_URL','EVENTLENS_REASONING_EFFORT'}
    for line in path.read_text().splitlines():
        key,sep,value=line.partition('=');key=key.strip()
        if sep and key in allowed:os.environ[key]=value.strip().strip('"').strip("'")


def seal(folder):
    names=['sources.json','jobs.json','config.json','freeze.json','labels.json','summary.json','report.md','review_queue.json']
    paths=[folder/n for n in names]+sorted((folder/'runs').glob('*.json'))+sorted((folder/'requests').glob('*.json'))
    if (folder/'approval.json').exists():paths.append(folder/'approval.json')
    write_json(folder/'bundle_hashes.json',{str(p.relative_to(folder)):digest(p.read_bytes()) for p in paths})


def aggregate(folder,jobs):
    runs=[json.loads(p.read_text()) for p in sorted((folder/'runs').glob('*.json'))]
    labels=json.loads((folder/'labels.json').read_text())
    # Only validated reviewer exports can enter the scored-label path.
    if labels.get('cases'):
        from eventlens.review import validate_export
        sources={s['source_id']:Source(**s) for s in json.loads((folder/'sources.json').read_text())}
        labels=validate_export(labels,sources,[c for c in jobs if c['split'] in ('development','heldout')])
    requests=[json.loads(p.read_text()) for p in (folder/'requests').glob('*.json')]
    from decimal import Decimal
    report={'created_at':now(),'completed_runs':len(runs),'planned_runs':len(jobs)*4,
            'human_reviewed_cases':sum(c['review_status']=='reviewed' for c in labels['cases'].values()),
            'paid_request_attempts':len(requests),'charged_upper_usd':str(sum((Decimal(r['charged_upper_usd']) for r in requests),Decimal(0))),
            'metrics':summary(runs,labels),'labels':'Only explicit reviewer exports count as ground truth.'}
    queue=[]
    for run in runs:
        for kind,items in [('metric',run['extractions']),('explanation',run['explanations']),('conflict',run['conflicts'])]:
            for item in items:
                queue.append({'run_id':run['run_id'],'case_id':run['case']['case_id'],'method':run['method'],
                              'synthetic':bool(run['case'].get('synthetic')),'kind':kind,'candidate':item,
                              'source_hashes':run['source_hashes'],'decision':'pending','reviewer':None,'reviewed_at':None})
    write_json(folder/'review_queue.json',queue)
    write_json(folder/'summary.json',report);(folder/'report.md').write_text(report_text(report))
    seal(folder)
    return report


def replay(folder):
    sources,jobs,config=check(folder)
    hashes=json.loads((folder/'bundle_hashes.json').read_text())
    for name,h in hashes.items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder.resolve()) or digest(path.read_bytes())!=h:raise ValueError('bundle_hash_mismatch: '+name)
    runs=[];responses=0
    for path in sorted((folder/'runs').glob('*.json')):
        saved=json.loads(path.read_text());adapter=RecordedAdapter(saved)
        result=run_investigation(sources,saved['case'],saved['method'],config,adapter)
        if stable(result)!=stable(saved):
            fields=[k for k in stable(saved) if stable(saved)[k]!=stable(result).get(k)]
            raise ValueError('replay_mismatch: '+path.name+' '+str(fields))
        if adapter.used!=len(adapter.records):raise ValueError('unused_saved_response')
        responses+=adapter.used;runs.append(saved)
    saved=json.loads((folder/'summary.json').read_text())
    labels=json.loads((folder/'labels.json').read_text())
    if labels.get('cases'):
        from eventlens.review import validate_export
        labels=validate_export(labels,sources,[c for c in jobs if c['split'] in ('development','heldout')])
    if summary(runs,labels)!=saved['metrics']:raise ValueError('replayed_metrics_differ')
    if report_text(saved)!=(folder/'report.md').read_text():raise ValueError('replayed_report_differs')
    result={'replayed_runs':len(runs),'recorded_requests':responses,'paid_model_calls':0,'network_calls':0,
            'all_saved_requests_matched':True,'all_evidence_and_results_matched':True,'results_table_reproduced':True}
    write_json(folder/'replay.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path);p.add_argument('--resume',action='store_true')
    p.add_argument('--live',action='store_true');p.add_argument('--approval',type=Path)
    p.add_argument('--env-file',type=Path);p.add_argument('--replay',type=Path)
    p.add_argument('--labels',type=Path,help='Explicit human reviewer export; rescore with --resume')
    args=p.parse_args()
    if args.replay:
        if any((args.live,args.out,args.labels)):p.error('--replay is read-only')
        print(json.dumps(replay(args.replay.resolve()),indent=2));return
    if not args.out:p.error('--out required')
    folder=args.out.resolve()
    if not args.resume:prepare(folder)
    sources,jobs,config=check(folder)
    if args.labels:
        from eventlens.review import validate_export
        raw=json.loads(args.labels.read_text());validate_export(raw,sources,[c for c in jobs if c['split'] in ('development','heldout')])
        if json.loads((folder/'labels.json').read_text()).get('cases'):raise ValueError('use a new scoring bundle to preserve prior labels')
        write_json(folder/'labels.json',raw)
    journal=None
    if args.live:
        if args.env_file:load_env(args.env_file)
        if not args.approval:raise ValueError('explicit budget approval record required')
        approval=json.loads(args.approval.read_text())
        if approval.get('status')!='approved' or approval.get('model')!=config['model'] or approval.get('config_hash')!=digest((folder/'config.json').read_bytes()):
            raise ValueError('approval_does_not_match_frozen_plan')
        write_json(folder/'approval.json',approval)
        provider=config['provider']
        adapter=LiveAdapter(config['model'],base_url=provider['base_url'],reasoning_effort=provider['reasoning_effort'],timeout=60,max_retries=0)
        journal=BudgetJournal(folder/'requests',adapter,approval['cap_usd'],config['pricing'])
    methods=['A','B','C','D'] if args.live else ['A','D']
    for case in jobs:
        for method in methods:
            name=case['case_id']+'_'+method;path=folder/'runs'/(name+'.json')
            if path.exists():continue
            run=run_investigation(sources,case,method,config,journal.bind(name) if journal and method in ('B','C') else None)
            # Budget denial is not an algorithmic abstention; leave the job pending.
            if any('paid_budget_exhausted' in e for e in run['errors']):
                report=aggregate(folder,jobs)
                print(json.dumps({'stopped':'budget','completed_runs':report['completed_runs'],'charged_upper_usd':report['charged_upper_usd']}),flush=True);return
            write_json(path,run)
            print(json.dumps({'case':case['case_id'],'method':method,'status':run['conclusion'],'calls':run['calls'],'errors':run['errors']}),flush=True)
            if any('provider_call_failed' in e or 'usage_exceeded' in e for e in run['errors']):
                aggregate(folder,jobs);print('Stopped after provider failure; saved all completed work.',flush=True);return
    report=aggregate(folder,jobs)
    print(json.dumps({'completed_runs':report['completed_runs'],'charged_upper_usd':report['charged_upper_usd'],'replay':replay(folder)},indent=2))

if __name__=='__main__':main()
