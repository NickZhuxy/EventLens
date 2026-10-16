#!/usr/bin/env python3
"""Reproduce the latest engineering evidence, costs and unfulfilled review gates."""
from collections import defaultdict
from decimal import Decimal
import argparse
import json
from pathlib import Path
from statistics import median
import sys
import earnings_budget
ROOT=earnings_budget.ROOT
sys.path.insert(0,str(ROOT/'src'))
from eventlens.core import digest
from eventlens.benchmark import write_json
VERSIONS={7:'earnings-v7-2026-10-15',8:'earnings-v8-2026-10-15',9:'earnings-v9-2026-10-15'}


def performance(folder):
    seals=json.loads((folder/'bundle_hashes.json').read_text())
    for name,h in seals.items():
        if digest((folder/name).read_bytes())!=h:raise ValueError('execution_record_changed')
    runs={p.stem:json.loads(p.read_text()) for p in (folder/'runs').glob('*.json')}
    groups=defaultdict(lambda:{'runs':[],'requests':[]})
    def key(r):return r['method'],r['case']['split'],r['case'].get('challenge','real')
    for r in runs.values():groups[key(r)]['runs'].append(r)
    for p in (folder/'requests').glob('*.json'):
        prefix=p.stem.rpartition('.')[0]
        groups[key(runs[prefix])]['requests'].append(json.loads(p.read_text()))
    result=[]
    for (method,split,challenge),g in sorted(groups.items()):
        rs=g['runs'];qs=g['requests']
        result.append({'method':method,'split':split,'challenge':challenge,'cases':len(rs),
            'numeric_outputs':sum(bool(r['comparison']['calculation']) for r in rs),
            'provider_requests':len(qs),'controller_call_attempts':sum(r['calls'] for r in rs),
            'charged_or_reserved_usd':str(sum((Decimal(q['charged_upper_usd']) for q in qs),Decimal(0))),
            'billing_uncertain_requests':sum(q['state']!='complete' for q in qs),
            'median_run_seconds':round(median(r['latency_ms']/1000 for r in rs),3),
            'input_tokens_reported':sum(q.get('response',{}).get('usage',{}).get('prompt_tokens',0) for q in qs),
            'output_tokens_reported':sum(q.get('response',{}).get('usage',{}).get('completion_tokens',0) for q in qs)})
    return result


def build():
    import analyze_earnings_protocol_v6 as a6
    import analyze_earnings_expansion_v7 as a7
    import analyze_earnings_expansion_v8 as a8
    import analyze_earnings_stress_v9 as a9
    # Their --check commands separately verify saved analyses; this index verifies its source seals.
    analysis={v:json.loads((ROOT/f'reports/earnings-v{v}-analysis-2026-10-15/analysis.json').read_text()) for v in (6,7,8,9)}
    hashes={}
    for v,a in analysis.items():
        path=ROOT/f'reports/earnings-v{v}-analysis-2026-10-15/analysis.json'
        hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes())
        script=Path({6:a6,7:a7,8:a8,9:a9}[v].__file__)
        if a['analysis_script_sha256']!=digest(script.read_bytes()):raise ValueError('analysis_script_changed')
    rows=[]
    for version,name in VERSIONS.items():
        folder=ROOT/'reports'/name
        if analysis[version]['bundle_hashes_sha256']!=digest((folder/'bundle_hashes.json').read_bytes()):
            raise ValueError('analysis_bundle_seal_changed')
        rows.extend({'version':version,**row} for row in performance(folder))
    review=json.loads((ROOT/'reports/earnings-v8-review-2026-10-15/labels.pending.json').read_text())
    if any(x['review_status']!='pending' or x['human_attestation'] for x in review['cases'].values()):
        raise ValueError('machine_draft_not_pending')
    checkpoint=ROOT/'reports/earnings-budget-2026-10-15/checkpoint-v9.json'
    budget=json.loads(checkpoint.read_text())
    total=Decimal(0)
    for name,row in budget['request_records'].items():
        p=ROOT/name
        if digest(p.read_bytes())!=row['sha256']:raise ValueError('budget_record_changed')
        total+=Decimal(json.loads(p.read_text())['charged_upper_usd'])
    if str(total)!=budget['spent_or_reserved_usd']:raise ValueError('budget_total_changed')
    hashes[str(checkpoint.relative_to(ROOT))]=digest(checkpoint.read_bytes())
    budget.pop('request_records')
    semantic=ROOT/'reports/earnings-v8-review-2026-10-15/semantic-review.pending.json'
    semantic_data=json.loads(semantic.read_text())
    if any(x['decision']!='pending' or x['human_attestation'] for x in semantic_data['reviews'].values()):
        raise ValueError('pending_semantic_template_changed')
    hashes[str(semantic.relative_to(ROOT))]=digest(semantic.read_bytes())
    return {'scope':'Engineering evidence for the earnings implementation; zero human-reviewed labels. Numerical accuracy and natural semantic support remain unestablished.',
        'latest_real_results':analysis[8]['summary'],'stress_controls':analysis[9]['control_metrics'],
        'natural_supplemental':analysis[9]['natural_supplemental'],'performance':rows,
        'budget':budget,'pairs':36,'issuers':12,'pending_review_pairs':len(review['cases']),
        'pending_semantic_candidates':len(semantic_data['reviews']),
        'saved_machine_drafts_are_not_gold':True,'source_analysis_hashes':hashes,
        'builder_sha256':digest(Path(__file__).read_bytes()),
        'remaining_acceptance_requirements':['Nick must review all 36 labels before precision, recall, direction or exact-match accuracy is reported.',
            'Natural explanation support and natural conflicts still require human semantic review.',
            'All original held-out inputs have now been exposed. Any new generalization claim needs a separately frozen unseen set.',
            'Remote CI and publication require an authorized push. No push was made.']}


def markdown(r):
    b=r['budget'];lines=['# Earnings evidence checkpoint','',r['scope'],'',
        f"The corpus contains {r['pairs']} disclosure pairs from {r['issuers']} issuers. All {r['pending_review_pairs']} labels remain pending human review.",'',
        '## Current corpus regression','','The originally held-out 24 pairs are now exposed regression cases. Numerical outputs are coverage, not accuracy. B/C use the same candidate parser; the A/D extraction rules remain unchanged.','',
        '| Method | n | Numerical outputs | No terminal errors |','| --- | ---: | ---: | ---: |']
    for x in r['latest_real_results']['metrics']:
        if x['split']=='heldout' and x['challenge']=='real':lines.append(f"| {x['method']} | {x['cases']} | {x['numeric_outputs']} | {x['completed_without_errors']} |")
    lines+=['','## Stress controls','','| Control | Method | n | Valid outcomes | Failed attempts |','| --- | --- | ---: | ---: | ---: |']
    for x in r['stress_controls']:
        lines.append(f"| {x['challenge']} | {x['method']} | {x['cases']} | {x['v9_valid_outcomes']} | {x['v9_failed_attempts']} |")
    lines+=['','The original `missing_table` control removes all numbers. [V8](../earnings-v8-analysis-2026-10-15/analysis.md) separately deletes only pipe-bearing table rows while preserving prose. Surviving prose may support a numerical output. Synthetic opposite-polarity statements do not establish natural management-conflict accuracy.','',
        '## Cost and latency','','| Version | Method | Split | Input | n | Provider requests | Cost incl. reservations, USD | Median seconds |',
        '| --- | --- | --- | --- | ---: | ---: | ---: | ---: |']
    for x in r['performance']:
        lines.append(f"| {x['version']} | {x['method']} | {x['split']} | {x['challenge']} | {x['cases']} | {x['provider_requests']} | {x['charged_or_reserved_usd']} | {x['median_run_seconds']} |")
    lines+=[ '',f"Improvement allocation: USD {b['allocation_usd']}. Used or conservatively reserved: USD {b['spent_or_reserved_usd']}. Remaining in that allocation: USD {b['remaining_in_allocation_usd']}; further authorized spend after preserving USD {b['preserved_reserve_usd']}: USD {b['remaining_authorized_spend_usd']}.",'',
        'These are peak/cache-miss token estimates and retained uncertain charges, not a provider account balance or invoice. The earlier v2 benchmark uses a separate allocation. Controller attempts can include a blocked request that never reached the provider. Failed attempts remain in all denominators.','',
        '## Inspect and reproduce','',
        '- [Explicit conflict references: v6](../earnings-v6-analysis-2026-10-15/analysis.md)',
        '- [Full corpus and table ablation: v7](../earnings-v7-analysis-2026-10-15/analysis.md)',
        '- [Point-target screening: v8](../earnings-v8-analysis-2026-10-15/analysis.md)',
        '- [Full stress regression: v9](../earnings-v9-analysis-2026-10-15/analysis.md)',
        '- [Recomputed BOX arithmetic](../earnings-examples-2026-10-15/box-arithmetic.md)',
        '- [Synthetic conflict with annual table evidence](../earnings-examples-2026-10-15/synopsys-synthetic-conflict.md)',
        '- [Pending review suggestions](../earnings-v8-review-2026-10-15/labels.pending.json)','',
        f"A separate [semantic review sample](../earnings-v8-review-2026-10-15/semantic-review.pending.json) contains {r['pending_semantic_candidates']} pending natural explanation/conflict candidates. The sole natural B conflict candidate has a [field/reason inconsistency](../earnings-v8-review-2026-10-15/natural-conflict-note.json); C emitted no natural conflict in the original 24 held-out real pairs.",'',
        '```sh','python scripts/earnings_evidence_index.py --check','```','',
        '## Remaining acceptance requirements','']+['- '+x for x in r['remaining_acceptance_requirements']]+['']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    r=build();md=markdown(r);out=ROOT/'reports/earnings-evidence-2026-10-15'
    if a.check:
        if json.loads((out/'evidence.json').read_text())!=r or (out/'evidence.md').read_text()!=md:raise ValueError('saved_index_differs')
    else:
        if out.exists():raise ValueError('preserve_evidence_checkpoint')
        write_json(out/'evidence.json',r);(out/'evidence.md').write_text(md)
    print(json.dumps({'evidence_reproduced':True,'budget':r['budget']['spent_or_reserved_usd']}))


if __name__=='__main__':main()
