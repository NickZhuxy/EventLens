#!/usr/bin/env python3
"""Add the natural withdrawal result to the preserved v9 evidence checkpoint."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import earnings_evidence_index as previous
import analyze_earnings_withdrawal_v10 as withdrawal
from eventlens.core import digest
from eventlens.benchmark import write_json
ROOT=previous.ROOT


def build():
    r=previous.build();addition=withdrawal.build()
    r['previous_builder_sha256']=r['builder_sha256'];r['builder_sha256']=digest(Path(__file__).read_bytes())
    r['withdrawal_addendum']=addition
    r['performance'] += [{'version':10,**x} for x in previous.performance(ROOT/'reports/earnings-v10-2026-10-15')]
    path=ROOT/'reports/earnings-budget-2026-10-15/checkpoint-v10.json';b=json.loads(path.read_text())
    total=Decimal(0)
    for name,row in b['request_records'].items():
        p=ROOT/name
        if digest(p.read_bytes())!=row['sha256']:raise ValueError('budget_record_changed')
        total+=Decimal(json.loads(p.read_text())['charged_upper_usd'])
    if total!=Decimal(b['spent_or_reserved_usd']):raise ValueError('budget_total_changed')
    b.pop('request_records');r['budget']=b;r['source_analysis_hashes'][str(path.relative_to(ROOT))]=digest(path.read_bytes())
    r['source_analysis_hashes']['reports/earnings-v10-analysis-2026-10-15/analysis.json']=digest((ROOT/'reports/earnings-v10-analysis-2026-10-15/analysis.json').read_bytes())
    return r


def markdown(r):
    md=previous.markdown(r).replace('python scripts/earnings_evidence_index.py --check','python scripts/earnings_evidence_index_v10.py --check')
    a=r['withdrawal_addendum'];s=a['summary']
    add=(f"## Natural withdrawal addendum\n\nThe [v10 analysis](../earnings-v10-analysis-2026-10-15/analysis.md) adds {s['completed_runs']} live outcomes and {s['request_attempts']} provider requests at USD {s['charged_upper_usd']}. Both B/C now identify the explicit annual financial-guidance withdrawal in the original Synopsys notice. Bounds remain absent, and the prior unique revenue target supplies the identity fields. The rollover case still abstains.\n\n"
         "[Inspect the withdrawal and its source evidence](../earnings-examples-2026-10-15/synopsys-withdrawal.md). A separate offline check replays 290 non-withdrawal v8/v9 B/C recordings unchanged under the new code. This is recorded-response regression, not fresh inference or reviewed accuracy.\n\n")
    return md.replace('## Remaining acceptance requirements',add+'## Remaining acceptance requirements')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    r=build();md=markdown(r);out=ROOT/'reports/earnings-evidence-v10-2026-10-15'
    if a.check:
        if json.loads((out/'evidence.json').read_text())!=r or (out/'evidence.md').read_text()!=md:raise ValueError('saved_index_differs')
    else:
        if out.exists():raise ValueError('preserve_evidence_checkpoint')
        write_json(out/'evidence.json',r);(out/'evidence.md').write_text(md)
    print(json.dumps({'evidence_reproduced':True,'spent_or_reserved_usd':r['budget']['spent_or_reserved_usd']}))


if __name__=='__main__':main()
