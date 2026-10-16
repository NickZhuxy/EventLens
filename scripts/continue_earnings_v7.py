#!/usr/bin/env python3
"""Continue unattempted v7 jobs while quarantining a saved terminal provider failure.

Never clear a charge or retry a failed/uncertain request. Existing runs are immutable.
A reservation without an already saved matching terminal run still blocks continuation.
"""
import fcntl
import json
from pathlib import Path
import earnings_expansion_v7 as run
from eventlens.core import digest,now
from eventlens.benchmark import BudgetJournal,write_json
ROOT=run.ROOT


def quarantined_failures(folder):
    retained=[]
    for p in sorted((folder/'requests').glob('*.json')):
        record=json.loads(p.read_text())
        if record['state']=='complete':continue
        if record['state']!='failed_or_uncertain':raise ValueError('unsettled_reservation_without_terminal_failure')
        prefix,_,counter=p.stem.rpartition('.')
        path=folder/'runs'/(prefix+'.json')
        if not path.exists():raise ValueError('uncertain_request_without_saved_terminal_run')
        saved=json.loads(path.read_text())
        if not any('provider_call_failed' in e for e in saved['errors']):raise ValueError('not_a_saved_provider_failure')
        calls=[t for t in saved['trace'] if t['stage']=='model_call']
        i=int(counter)-1
        if i>=len(calls) or calls[i].get('raw_response') is not None or calls[i].get('error')!='provider_call_failed; reservation retained; no automatic retry':
            raise ValueError('uncertain_request_not_matched_to_terminal_call')
        if record['request']['messages']!=calls[i]['messages'] or record['charged_upper_usd']!=record['reserved_usd']:
            raise ValueError('request_or_retained_reservation_changed')
        retained.append({'request':str(p.relative_to(folder)),'request_sha256':digest(p.read_bytes()),
                         'terminal_run':str(path.relative_to(folder)),'run_sha256':digest(path.read_bytes()),
                         'retained_usd':record['charged_upper_usd']})
    if not retained:raise ValueError('no_quarantined_failure_to_continue_past')
    return retained


def main():
    folder=ROOT/'reports/earnings-v7-2026-10-15'
    with (ROOT/'reports/earnings-budget-2026-10-15/execution.lock').open('a') as shared, (folder/'execution.lock').open('a') as lock:
        fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        sources,jobs,config=run.check(folder);run.replay(folder)
        failures=quarantined_failures(folder)
        checkpoint=folder/'continuations/terminal-failure-continuation.json'
        if not checkpoint.exists():
            write_json(checkpoint,{'recorded_at':now(),'helper_sha256':digest(Path(__file__).read_bytes()),
                'authorization':'reports/earnings-budget-2026-10-15/authorization.json',
                'action':'Continue only absent run files; do not resend any recorded failed request or release its reservation.',
                'quarantined_failures':failures,'summary_at_stop':json.loads((folder/'summary.json').read_text()),
                'bundle_hashes_at_stop':json.loads((folder/'bundle_hashes.json').read_text())})
        else:
            original=json.loads(checkpoint.read_text())
            if original['quarantined_failures']!=failures or original['helper_sha256']!=digest(Path(__file__).read_bytes()):
                raise ValueError('continuation_changed')
        cap=run.approved_cap(folder,ROOT/'work/earnings-v7-approval.json',config)
        if cap>run.budget_remaining(config):raise ValueError('budget_allocation_changed')
        import os
        for line in (ROOT/'.env').read_text().splitlines():
            key,sep,value=line.partition('=')
            if sep and key.strip() in {'EVENTLENS_API_KEY','DEEPSEEK_API_KEY'}:
                os.environ[key.strip()]=value.strip().strip('"').strip("'")
        journal=BudgetJournal(folder/'requests',run.NativeAdapter(config),cap,config['pricing'])
        for case in jobs:
            for method in config['methods']:
                prefix=case['case_id']+'_'+method;path=folder/'runs'/(prefix+'.json')
                if path.exists():continue
                # A partial unsealed request sequence is not a fresh unattempted job.
                if list((folder/'requests').glob(prefix+'.*.json')):
                    raise ValueError('new_job_already_has_requests; inspect_without_retry')
                result=run.run_native(sources,case,method,config,journal.bind(prefix))
                write_json(path,result);run.save_state(folder,jobs)
                print(json.dumps({'case':case['case_id'],'method':method,'calls':result['calls'],
                                  'errors':result['errors'],'charged_upper_usd':str(journal.spent())}),flush=True)
                if any('provider_' in e or 'paid_budget_' in e or 'reservation' in e for e in result['errors']):return
        run.save_state(folder,jobs);print(json.dumps(run.replay(folder)))


if __name__=='__main__':main()
