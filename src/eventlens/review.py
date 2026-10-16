"""Validate explicit human label exports without promoting machine drafts to gold."""
from copy import deepcopy
from dataclasses import asdict

from .core import Metric, compare, number, timestamp
from .investigation import citation

DIRECTIONS={'raised','lowered','maintained','withdrawn','not_comparable','mixed_range'}


def validate_export(payload,sources,cases):
    if payload.get('schema')!='eventlens-review-v2' or not isinstance(payload.get('cases'),dict):
        raise ValueError('invalid_review_export')
    cases={c['case_id']:c for c in cases}
    if set(payload['cases'])!=set(cases):raise ValueError('review_case_inventory_mismatch')
    expected={c[k] for c in cases.values() for k in ('old','new')}
    if payload.get('source_hashes')!={sid:sources[sid].content_hash for sid in sorted(expected)}:
        raise ValueError('review_source_hash_mismatch')
    result=deepcopy(payload)
    for cid,row in result['cases'].items():
        if row.get('review_status')=='pending':continue
        if row.get('review_status')!='reviewed' or row.get('human_attestation') is not True:
            raise ValueError('explicit_human_review_required: '+cid)
        if not isinstance(row.get('reviewed_by'),str) or not row['reviewed_by'].strip():raise ValueError('reviewer_required')
        timestamp(row.get('reviewed_at'))
        if row.get('direction') not in DIRECTIONS:raise ValueError('invalid_reviewed_direction')
        if row.get('explanation_conflict') not in ('yes','no','uncertain'):raise ValueError('conflict_review_required')
        if row.get('explanation_status') not in ('quoted','none_found','uncertain'):raise ValueError('explanation_review_required')
        if not isinstance(row.get('notes'),str) or not row['notes'].strip():raise ValueError('review_notes_required')
        values=row.get('metrics')
        if not isinstance(values,list) or len(values)!=2:raise ValueError('two_label_records_required')
        metrics=[];case=cases[cid]
        for side,value in zip(('old','new'),values):
            if value is None:
                metrics.append(None);continue
            metric=Metric(**value);source=sources[case[side]]
            if (metric.source_id!=source.source_id or metric.issuer!=case['issuer'] or
                metric.horizon!=case['horizon'] or metric.metric!='revenue'):
                raise ValueError('label_identity_or_horizon_mismatch')
            citation({'source_id':metric.source_id,'quote':metric.evidence},sources)
            citation({'source_id':metric.source_id,'quote':metric.horizon_evidence},sources)
            if metric.evidence not in metric.horizon_evidence:raise ValueError('label_quote_disconnected_from_heading')
            metrics.append(metric)
        explanations=row.get('explanations',[])
        if not isinstance(explanations,list):raise ValueError('invalid_label_explanations')
        for claim in explanations:
            if claim.get('source_id') not in {case['old'],case['new']}:raise ValueError('explanation_outside_pair')
            citation(claim,sources)
        if row['explanation_status']=='quoted' and not explanations:raise ValueError('quoted_explanation_required')
        if row['explanation_status']=='none_found' and explanations:raise ValueError('none_found_cannot_have_quotes')
        if row['explanation_conflict']=='yes' and len({x['quote'] for x in explanations})<2:raise ValueError('conflict_needs_two_distinct_quotes')
        comparison=compare(*metrics)
        direction={'unchanged':'maintained','guidance_withdrawn':'withdrawn'}.get(comparison['reason'],comparison['reason'])
        if row['direction']!='not_comparable' and row['direction']!=direction:
            raise ValueError('reviewed_direction_disagrees_with_bounds: '+cid)
        if row['direction']=='not_comparable':
            row['expected_midpoint_delta_usd']=None;row['normalized_bounds']={}
        else:
            calc=comparison['calculation'];row['expected_midpoint_delta_usd']=calc['midpoint_delta'] if calc else None
            row['normalized_bounds']={k:calc[k] for k in ('old_lower','old_upper','new_lower','new_upper')} if calc else {}
    result['status']='human_reviewed' if all(c['review_status']=='reviewed' for c in result['cases'].values()) else 'partially_reviewed'
    return result
