#!/usr/bin/env python3
"""Sample emitted v8 natural explanations for human review without changing the bundle."""
from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import review_earnings_explanations as previous
import earnings_expansion_v8 as runner
from eventlens.core import digest
ROOT=runner.ROOT


def template():
    folder=ROOT/'reports/earnings-v8-2026-10-15';sources,jobs,_=runner.check(folder)
    seals=json.loads((folder/'bundle_hashes.json').read_text());groups=defaultdict(dict)
    for c in jobs:
        if c['split']!='heldout' or c.get('synthetic'):continue
        for method in 'ABCD':
            name='runs/'+c['case_id']+'_'+method+'.json';path=folder/name
            if digest(path.read_bytes())!=seals[name]:raise ValueError('saved_run_changed')
            run=json.loads(path.read_text())
            for kind,key in [('explanation','explanations'),('conflict','conflicts')]:
                for candidate in run[key]:
                    quotes=[candidate] if kind=='explanation' else candidate['citations']
                    for q in quotes:
                        s=sources[q['source_id']]
                        if q['quote'] not in s.text:raise ValueError('candidate_not_literal')
                        if 'source_hash' in q and (q['source_hash']!=s.content_hash or s.text[q['start']:q['end']]!=q['quote']):
                            raise ValueError('candidate_binding_changed')
                    e={'case_id':c['case_id'],'method':method,'kind':kind,'candidate':candidate,
                       'source_hashes':run['source_hashes'],'horizon':c['horizon']}
                    groups[method,kind][previous.digest(e)]=e
    populations=[];reviews={}
    for method in 'ABCD':
        for kind in ('explanation','conflict'):
            group=groups[method,kind];chosen=sorted(group)[:8]
            populations.append({'method':method,'kind':kind,'eligible_candidates':len(group),'sampled_candidates':len(chosen)})
            for key in chosen:reviews[key]={'evidence':group[key],'decision':'pending','reviewed_by':None,'reviewed_at':None,'human_attestation':False,'notes':''}
    return {'schema':'eventlens-semantic-review-v1','bundle_hashes_sha256':digest((folder/'bundle_hashes.json').read_bytes()),
        'review_script_sha256':digest(Path(__file__).read_bytes()),
        'scorer_script_sha256':digest(Path(previous.__file__).read_bytes()),
        'sample_size_per_method_and_kind':8,
        'sampling_policy':'First SHA-256 identities per method and kind among emitted natural originally-heldout candidates. This is a post-execution review sample on exposed data, not a preregistered test or all-case accuracy metric.',
        'questions':{'explanation':'Does this exact quotation explicitly explain the annual total-revenue guidance revision for the same horizon and basis? General optimism alone is insufficient.',
                     'conflict':'Do both cited statements make opposing claims about the same explanation, period, scope and basis? Differences in currency basis or fiscal year alone are not contradictions.'},
        'allowed_decisions':['pending','supported','unsupported','uncertain'],'population':populations,'reviews':reviews}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--review',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    expected=template();result=previous.score(json.loads(a.review.read_text()),expected) if a.review else expected
    out=a.out or ROOT/'reports/earnings-v8-review-2026-10-15/semantic-review.pending.json'
    content=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if a.check:
        if out.read_text()!=content:raise ValueError('saved_review_artifact_differs')
    else:
        if out.exists():raise ValueError('preserve_prior_review_artifact')
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(content)
    print(json.dumps({'sampled':len(expected['reviews']),'reviewed':sum(x['reviewed_candidates'] for x in result.get('metrics',[]))}))


if __name__=='__main__':main()
