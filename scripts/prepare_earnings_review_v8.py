#!/usr/bin/env python3
"""Prepare pending machine suggestions for the existing human review page."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import earnings_expansion_v8 as v8
import earnings_review as review
from eventlens.core import Metric,compare,digest
from eventlens.evidence_v8 import guidance_catalog
from eventlens.benchmark import write_json
ROOT=v8.ROOT


def build():
    folder=ROOT/'reports/earnings-v8-2026-10-15';sources,jobs,_=v8.check(folder)
    data=review.payload()
    export={k:deepcopy(data[k]) for k in ('schema','source_hashes','cases')}
    audit=[]
    for case in jobs:
        if case.get('synthetic'):continue
        rows=[guidance_catalog(sources[case[k]],case['horizon']) for k in ('old','new')]
        metrics=[deepcopy(found[0]['metric']) if len(found)==1 else None for found in rows]
        for metric in metrics:
            if metric:
                s=sources[metric['source_id']]
                if metric['horizon_evidence'] not in s.text or metric['evidence'] not in metric['horizon_evidence']:
                    raise ValueError('draft_quote_not_literal')
        comp=compare(*[Metric(**m) if m else None for m in metrics])
        direction={'unchanged':'maintained','guidance_withdrawn':'withdrawn'}.get(comp['reason'],comp['reason']) if all(metrics) else ''
        if direction not in {'raised','lowered','maintained','withdrawn','mixed_range'}:direction=''
        row=export['cases'][case['case_id']]
        row.update(metrics=metrics,direction=direction,review_status='pending',reviewed_by=None,reviewed_at=None,
                   human_attestation=False,explanations=[],explanation_status='',explanation_conflict='',notes='',
                   draft_origin='Unreviewed machine suggestion from the frozen v8 candidate parser. Check every number, period and explanation yourself.')
        audit.append({'case_id':case['case_id'],'candidate_counts':[len(r) for r in rows],
                      'metric_drafts_supplied':sum(m is not None for m in metrics),'direction_draft':direction,
                      'missing_or_ambiguous_sides':[k for k,m in zip(('old','new'),metrics) if m is None]})
    # A pending draft may be imported, but never qualifies as a reviewed label.
    review.validate_export(export,sources,[c for c in jobs if not c.get('synthetic')])
    report={'kind':'Machine suggestions, not ground truth','pairs':len(audit),'human_reviewed_pairs':0,
            'pairs_with_two_unique_metric_drafts':sum(r['metric_drafts_supplied']==2 for r in audit),
            'source_freeze_sha256':digest((folder/'freeze.json').read_bytes()),
            'builder_sha256':digest(Path(__file__).read_bytes()),'cases':audit,
            'instructions':'Export a backup of any existing review first. Open the existing disclosure-review.html, use Restore JSON to load labels.pending.json, then personally check each pair. Existing original draft data and browser storage are not changed by this builder.'}
    return export,report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    out=ROOT/'reports/earnings-v8-review-2026-10-15';labels,audit=build()
    if a.check:
        if json.loads((out/'labels.pending.json').read_text())!=labels or json.loads((out/'draft-audit.json').read_text())!=audit:
            raise ValueError('saved_draft_differs')
    else:
        if out.exists():raise ValueError('preserve_existing_review_draft')
        write_json(out/'labels.pending.json',labels);write_json(out/'draft-audit.json',audit)
    print(json.dumps({k:audit[k] for k in ('pairs','human_reviewed_pairs','pairs_with_two_unique_metric_drafts')}))


if __name__=='__main__':main()
