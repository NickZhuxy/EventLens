#!/usr/bin/env python3
"""Save reproducible v5 SCRIPTED traces. No live model or reviewed accuracy."""
from copy import deepcopy
import argparse
import json
from pathlib import Path

from earnings_protocol_v5 import ROOT, check
from eventlens.benchmark import RecordedAdapter, stable, write_json
from eventlens.core import canonical, digest
from eventlens.evidence_v5 import EvidenceTools
from eventlens.protocol_v5 import run_native


class ScriptedAdapter:
    model='scripted-v5-fixture-NOT-an-LLM'
    kind='scripted_fixture_not_model_inference'

    def __init__(self,responses):
        self.responses=iter(responses)

    def complete(self,payload,max_output):
        return deepcopy(next(self.responses))


def native(actions):
    return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
        {'id':'fixture-'+str(i),'type':'function','function':{'name':name,'arguments':canonical(args)}}
        for i,(name,args) in enumerate(actions)]}}],
        'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}


def fixture(sources,case,method):
    if case.get('challenge')=='stale_disclosure':
        return [],None
    tools=EvidenceTools(sources,[case['old'],case['new']],case['cutoff'],case['horizon'])
    actions=[(name,{'source_id':case[k]}) for k in ('old','new')
             for name in ('inspect_guidance','review_explanations')]
    for name,args in actions:
        tools.publish(tools.execute(name,args))
    chosen=[m['metric_id'] for items in tools.metrics.values() if len(items)==1 for m in items]
    finish={'metric_ids':chosen,'explanation_ids':[],'conflicts':[],'comparability':[],
            'unresolved':'SCRIPTED choices from parser and construction-known synthetic expectations. This is not model performance or human review.'}
    quotes=case.get('transformation',{}).get('expected_conflict_quotes',[])
    available=[any(c['quote']==q and c['source_id']==case['new'] for c in tools.citations.values()) for q in quotes]
    if quotes and all(available):
        ids=[next(eid for eid,c in tools.citations.items() if c['quote']==q and c['source_id']==case['new']) for q in quotes]
        finish['conflicts']=[{'topic':'construction-known fixture','reason':'Scripted opposite-polarity statements.',
                             'statement_a':ids[0],'statement_b':ids[1]}]
    responses=([native(actions)] if method=='C' else [])+[native([('finish',finish)])]
    audit={'case_id':case['case_id'],'method':method,
           'candidate_counts':{sid:len(items) for sid,items in tools.metrics.items()},
           'expected_conflict_statements_available':available if quotes else None}
    return responses,audit


def build(bundle):
    sources,jobs,config=check(bundle)
    traces={};audit=[]
    for case in jobs:
        for method in config['methods']:
            responses,entry=fixture(sources,case,method)
            raw=run_native(sources,case,method,config,ScriptedAdapter(responses))
            if entry:audit.append(entry)
            expected_stale=case.get('challenge')=='stale_disclosure'
            if raw['errors'] != (['stale_or_reversed_disclosure_pair'] if expected_stale else []):
                raise ValueError('scripted_fixture_failed: '+case['case_id']+' '+method+' '+str(raw['errors']))
            saved=json.loads(canonical(stable(raw)))
            adapter=RecordedAdapter(saved)
            actual=run_native(sources,case,method,config,adapter)
            if stable(actual)!=saved or adapter.used!=len(adapter.records):
                raise ValueError('scripted_replay_mismatch')
            traces[case['case_id']+'_'+method+'.json']={'kind':'SCRIPTED; NOT a live model result','run':saved}
    return {'kind':'Offline deterministic availability and scripted controller fixtures; no live model results.',
            'bundle':str(bundle.relative_to(ROOT)),'freeze_sha256':digest((bundle/'freeze.json').read_bytes()),
            'verifier_sha256':digest(Path(__file__).read_bytes()),'scripted_runs':len(traces),
            'scripted_model_calls':sum(x['run']['calls'] for x in traces.values()),
            'network_calls':0,'paid_calls':0,'human_reviewed_labels':0,'all_traces_replay_exactly':True,
            'availability':audit,
            'limits':['Candidate availability is parser coverage, not reviewed extraction accuracy.',
                      'Conflict selections are scripted using construction-known expectations, not LLM judgments.',
                      'Development cases are exposed; natural conflicts and unseen generalization remain unestablished.']},traces


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    result,traces=build(args.bundle.resolve())
    if args.check:
        if json.loads((args.out/'verification.json').read_text())!=result:
            raise ValueError('saved_verification_differs')
        if {p.name for p in (args.out/'traces').glob('*.json')}!=set(traces):
            raise ValueError('saved_trace_inventory_differs')
        for name,trace in traces.items():
            if json.loads((args.out/'traces'/name).read_text())!=trace:
                raise ValueError('saved_scripted_trace_differs: '+name)
    else:
        if args.out.exists():raise ValueError('preserve_existing_evidence_use_check')
        write_json(args.out/'verification.json',result)
        for name,trace in traces.items():write_json(args.out/'traces'/name,trace)
    print(json.dumps({k:result[k] for k in ('kind','scripted_runs','scripted_model_calls','network_calls','paid_calls','all_traces_replay_exactly')},indent=2))


if __name__=='__main__':main()
