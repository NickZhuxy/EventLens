#!/usr/bin/env python3
"""Prepare a reproducible semantic-review sample and score explicit human judgments."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def template(bundle, sample_size=8):
    if type(sample_size) is not int or not 1 <= sample_size <= 1000:
        raise ValueError('sample_size must be an integer from 1 to 1000')
    inventory=json.loads((bundle/'bundle_hashes.json').read_text())
    for name in ('review_queue.json','sources.json','jobs.json'):
        if hashlib.sha256((bundle/name).read_bytes()).hexdigest()!=inventory[name]:
            raise ValueError('bundle changed: '+name)
    jobs={c['case_id']:c for c in json.loads((bundle/'jobs.json').read_text())}
    groups=defaultdict(list)
    for method in 'ABCD':
        for kind in ('explanation','conflict'):groups[(method,kind)]=[]
    for item in json.loads((bundle/'review_queue.json').read_text()):
        if item['kind'] not in ('explanation','conflict') or jobs[item['case_id']]['split']!='heldout' or item['synthetic']:
            continue
        evidence={k:item[k] for k in ('case_id','method','kind','candidate','source_hashes')}
        evidence['horizon']=jobs[item['case_id']]['horizon']
        # Hash order defines a deterministic sample; no judgment is used in selection.
        identity=digest(evidence)
        groups[(item['method'],item['kind'])].append((identity,evidence))
    candidates={};populations=[]
    for (method,kind),items in sorted(groups.items()):
        unique=dict(items)
        chosen=sorted(unique)[:sample_size]
        populations.append({'method':method,'kind':kind,'eligible_candidates':len(unique),'sampled_candidates':len(chosen)})
        for key in chosen:
            candidates[key]={'evidence':unique[key],'decision':'pending','reviewed_by':None,'reviewed_at':None,
                             'human_attestation':False,'notes':''}
    return {'schema':'eventlens-semantic-review-v1','bundle_hashes_sha256':hashlib.sha256((bundle/'bundle_hashes.json').read_bytes()).hexdigest(),
        'review_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'sample_size_per_method_and_kind':sample_size,
        'sampling_policy':'First SHA-256 identities per method and kind among emitted natural held-out explanation/conflict candidates. Repeated identical candidates are deduplicated. Operational sample defined after execution; not a preregistered test or all-case accuracy metric.',
        'questions':{'explanation':'Does this exact quotation explicitly explain or state the reason for the annual total-revenue guidance revision for this horizon and basis? General company optimism alone is insufficient.',
                     'conflict':'Do both cited statements make opposing claims about the same explanation, period, scope and basis? Different currency bases, fiscal years or consolidation scopes alone are not contradictions.'},
        'allowed_decisions':['pending','supported','unsupported','uncertain'],
        'population':populations,'reviews':candidates}


def score(review, expected):
    for field in expected:
        if field!='reviews' and review.get(field)!=expected[field]:
            raise ValueError('review metadata differs: '+field)
    if not isinstance(review.get('reviews'),dict) or set(review['reviews'])!=set(expected['reviews']):
        raise ValueError('review inventory differs')
    groups=defaultdict(list)
    for identity,item in review['reviews'].items():
        if not isinstance(item,dict) or item.get('evidence')!=expected['reviews'][identity]['evidence']:
            raise ValueError('candidate evidence differs: '+identity)
        if item.get('decision') not in expected['allowed_decisions']:
            raise ValueError('invalid decision: '+identity)
        if item['decision']!='pending':
            if item.get('human_attestation') is not True or not isinstance(item.get('reviewed_by'),str) or not item['reviewed_by'].strip():
                raise ValueError('explicit human attestation and reviewer required: '+identity)
            if not isinstance(item.get('notes'),str) or not item['notes'].strip():
                raise ValueError('review notes required: '+identity)
            try:
                stamp=datetime.fromisoformat(item['reviewed_at'].replace('Z','+00:00'))
                if stamp.tzinfo is None:raise ValueError('timezone required')
            except (KeyError,AttributeError,TypeError,ValueError):
                raise ValueError('valid review timestamp with timezone required: '+identity) from None
        groups[(item['evidence']['method'],item['evidence']['kind'])].append(item)
    metrics=[]
    for group in expected['population']:
        rows=groups[(group['method'],group['kind'])];counts=Counter(r['decision'] for r in rows)
        reviewed=len(rows)-counts['pending']
        metrics.append({**group,'reviewed_candidates':reviewed,'pending':counts['pending'],
            'supported':counts['supported'],'unsupported':counts['unsupported'],'uncertain':counts['uncertain'],
            'supported_rate_among_reviewed':counts['supported']/reviewed if reviewed else None})
    return {'schema':'eventlens-semantic-scores-v1','bundle_hashes_sha256':expected['bundle_hashes_sha256'],
        'review_sha256':digest(review),'metrics':metrics,
        'denominator':'Reviewed sampled candidates, including uncertain judgments. Pending entries never count as reviewed. Rates concern emitted candidates only; they do not measure missed explanations or overall case accuracy.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--sample-size',type=int,default=8);p.add_argument('--review',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    expected=template(a.bundle,a.sample_size)
    result=score(json.loads(a.review.read_text()),expected) if a.review else expected
    content=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if a.check:
        if a.out.read_text()!=content:raise ValueError('saved artifact differs from reproduction')
        print('Semantic-review artifact reproduced.');return
    if a.out.exists():raise ValueError('preserve earlier artifacts; choose a new output file')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(content)
    print(json.dumps({'saved':str(a.out),'human_reviews_scored':sum(m['reviewed_candidates'] for m in result.get('metrics',[]))}))


if __name__=='__main__':main()
