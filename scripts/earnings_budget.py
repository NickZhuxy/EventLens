#!/usr/bin/env python3
"""Account for the continuing improvement allocation, retaining uncertain charges."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
POLICY='reports/earnings-budget-2026-10-15/authorization.json'


def snapshot():
    policy=json.loads((ROOT/POLICY).read_text())
    folders=set(policy['prior_bundles'])
    for p in (ROOT/'reports').glob('*/approval.json'):
        a=json.loads(p.read_text())
        if a.get('budget_authorization')==POLICY:
            folders.add(str(p.parent.relative_to(ROOT)))
    rows=[];records={};spent=Decimal(0)
    for name in sorted(folders):
        total=Decimal(0);uncertain=0;count=0
        for p in sorted((ROOT/name/'requests').glob('*.json')):
            b=p.read_bytes();r=json.loads(b);amount=Decimal(r['charged_upper_usd'])
            if not amount.is_finite() or amount<0:raise ValueError('invalid_charge')
            total+=amount;count+=1;uncertain+=r['state']!='complete'
            records[str(p.relative_to(ROOT))]={'sha256':hashlib.sha256(b).hexdigest(),'charged_upper_usd':str(amount),'state':r['state']}
        rows.append({'bundle':name,'requests':count,'charged_or_reserved_usd':str(total),'uncertain_requests':uncertain})
        spent+=total
    allocation=Decimal(policy['allocation_usd']);reserve=Decimal(policy['reserve_usd'])
    return {'policy':POLICY,'policy_sha256':hashlib.sha256((ROOT/POLICY).read_bytes()).hexdigest(),
            'allocation_usd':str(allocation),'preserved_reserve_usd':str(reserve),
            'spent_or_reserved_usd':str(spent),'remaining_in_allocation_usd':str(allocation-spent),
            'remaining_authorized_spend_usd':str(allocation-reserve-spent),'bundles':rows,'request_records':records,
            'meaning':'Conservative peak/cache-miss token estimates and retained uncertain reservations. Not a provider account balance or invoice. Earlier v2 benchmark is a separate allocation.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--check',type=Path);a=p.parse_args()
    if a.check:
        s=json.loads(a.check.read_text())
        if hashlib.sha256((ROOT/s['policy']).read_bytes()).hexdigest()!=s['policy_sha256']:raise ValueError('policy_changed')
        total=Decimal(0)
        for name,r in s['request_records'].items():
            data=(ROOT/name).read_bytes()
            if hashlib.sha256(data).hexdigest()!=r['sha256']:raise ValueError('ledger_changed')
            total+=Decimal(json.loads(data)['charged_upper_usd'])
        if total!=Decimal(s['spent_or_reserved_usd']):raise ValueError('total_mismatch')
        print(json.dumps({'saved_checkpoint_verified':True,'spent_or_reserved_usd':str(total)}));return
    s=snapshot()
    if a.out:
        if a.out.exists():raise ValueError('preserve_existing_checkpoint')
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(s,indent=2)+'\n')
    print(json.dumps({k:v for k,v in s.items() if k!='request_records'},indent=2))


if __name__=='__main__':main()
