"""Frozen benchmark population, durable paid-call journal, and offline replay."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
import json
from pathlib import Path
import re

from .core import Source, canonical, digest, now, number
from .investigation import run_investigation


def write_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    temporary.replace(path)


def population(sources, cases):
    """Three controls for every held-out pair, independently of extractor success."""
    data=dict(sources);jobs=list(cases)
    for case in cases:
        if case['split']!='heldout':continue
        current=sources[case['new']]
        # Remove numeric content in every row, including duplicate prose guidance.
        # This is deliberately broader than deleting one table: actuals are masked too.
        removed=[]
        def mask(match):
            removed.append({'start':match.start(),'end':match.end(),'text':match[0]})
            return '[VALUE REMOVED]'
        masked=re.sub(r'\d[\d,]*(?:\.\d+)?',mask,current.text)
        a=f"Demand caused the {case['horizon']} total revenue guidance revision on a reported basis."
        b=f"Demand did not cause the {case['horizon']} total revenue guidance revision on a reported basis."
        for kind,text,expected,detail in [
            ('missing_table',masked,'insufficient_evidence',{'description':'Mask every numerical token in the new disclosure, including table cells, duplicate guidance prose, actuals and year headings. A broad missing-numerical-disclosure control, not an isolated table-parser ablation.','removed_spans':removed}),
            ('contradictory_commentary',current.text+'\n'+a+'\n'+b+'\n','conflicting',{'description':'Append a synthetic opposing pair about the same annual guidance, driver and basis. Never attribute these sentences to management.','expected_conflict_quotes':[a,b]})]:
            sid=current.source_id+'~v2-'+kind
            derived=replace(current,source_id=sid,text=text,content_hash=digest(text),snapshot_kind='SYNTHETIC derivative of '+current.source_id)
            data[sid]=derived
            jobs.append({**case,'case_id':case['case_id']+'~v2-'+kind,'new':sid,'synthetic':True,
                         'split':'synthetic_heldout','parent_case_id':case['case_id'],'challenge':kind,
                         'expected_status':expected,'transformation':detail,
                         'parent_source_hash':current.content_hash,'derived_source_hash':derived.content_hash})
        jobs.append({**case,'case_id':case['case_id']+'~v2-stale_disclosure','new':case['old'],
                     'synthetic':True,'split':'synthetic_heldout','parent_case_id':case['case_id'],
                     'challenge':'stale_disclosure','expected_status':'insufficient_evidence',
                     'transformation':{'description':'Substitute the old disclosure for the new one; fail eligibility before any model request.'}})
    for cid,old,new,horizon in [
        ('SNPS-FY2025-Q2-WITHDRAWAL','SNPS-2025-Q2','SNPS-2025-WITHDRAWAL','FY2025'),
        ('ADBE-FY2025-Q3-Q4-ROLLOVER','ADBE-2025-Q3','ADBE-2025-Q4','FY2025')]:
        jobs.append({'case_id':cid,'old':old,'new':new,'issuer':sources[old].issuer,'horizon':horizon,
                     'metric':'revenue','cutoff':sources[new].available_at,'split':'supplemental_natural',
                     'synthetic':False,'label_status':'pending_Nick_review','counted_in_quarterly_pairs':False})
    return data,jobs


class BudgetJournal:
    """Reserve before sending. Retain reservations when transport outcome is unknown.

    Pricing deliberately ignores all cache/off-peak discounts. Automatic retries are
    disabled by the caller. Resuming reuses an exact journalled request, never repays it.
    """
    def __init__(self, directory, adapter, cap, pricing):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.adapter=adapter;self.cap=number(cap);self.pricing=pricing
        if self.cap<=0:raise ValueError('budget_must_be_positive')
        self.model=adapter.model;self.kind=adapter.kind
        self.prefix=None;self.index=0

    def bind(self, prefix):
        if not re.fullmatch(r'[A-Za-z0-9_.~-]+',prefix):raise ValueError('invalid_journal_prefix')
        self.prefix=prefix;self.index=0
        return self

    def amount(self, inputs, outputs):
        return (Decimal(inputs)*number(self.pricing['input_per_million'])+
                Decimal(outputs)*number(self.pricing['output_per_million']))/Decimal(1000000)

    def spent(self):
        return sum((number(json.loads(p.read_text())['charged_upper_usd']) for p in self.directory.glob('*.json')),Decimal(0))

    def complete(self,messages,max_output_tokens):
        if self.prefix is None:raise ValueError('journal_not_bound_to_case')
        self.index+=1;path=self.directory/f'{self.prefix}.{self.index:02d}.json'
        request={'model':self.model,'messages':deepcopy(messages),'max_output_tokens':max_output_tokens,
                 'provider_settings':self.adapter.settings.to_dict()}
        if path.exists():
            saved=json.loads(path.read_text())
            if saved['request']!=request:raise ValueError('journal_request_changed')
            if saved['state']!='complete':raise RuntimeError('journalled_uncertain_or_failed_request; no automatic retry')
            return deepcopy(saved['response'])
        # UTF-8 bytes upper-bound text tokens, with 2048 tokens for role/schema overhead.
        bound=len(canonical(request).encode('utf-8'))+2048
        reserve=self.amount(bound,max_output_tokens)
        if self.spent()+reserve>self.cap:raise RuntimeError('paid_budget_exhausted_before_request')
        record={'created_at':now(),'request':request,'state':'reserved','input_token_bound':bound,
                'reserved_usd':str(reserve),'charged_upper_usd':str(reserve),'pricing':self.pricing}
        write_json(path,record)
        try:raw=self.adapter.complete(messages,max_output_tokens)
        except Exception:
            record['state']='failed_or_uncertain';record['error']='provider_call_failed; reservation retained'
            write_json(path,record)
            raise RuntimeError('provider_call_failed; reservation retained; no automatic retry') from None
        record['response']=raw;record['state']='complete'
        usage=raw.get('usage',{})
        values=[usage.get('prompt_tokens'),usage.get('completion_tokens')]
        if all(type(v) is int and v>=0 for v in values):
            actual=self.amount(*values)
            record['charged_upper_usd']=str(actual)
            record['provider_usage']=usage
            if actual>reserve:
                record['state']='usage_exceeded_reservation';write_json(path,record)
                raise RuntimeError('usage_exceeded_reservation; stop benchmark')
        write_json(path,record)
        return raw


class RecordedAdapter:
    kind='recorded_replay'
    def __init__(self,run):
        self.model=run.get('model');self.records=[r for r in run['trace'] if r['stage']=='model_call'];self.used=0
    def complete(self,messages,max_output_tokens):
        if self.used>=len(self.records):raise AssertionError('unrecorded_model_request')
        record=self.records[self.used];self.used+=1
        if messages!=record['messages'] or max_output_tokens!=record['max_output_tokens']:
            raise AssertionError('replay_request_mismatch')
        if 'raw_response' not in record:raise RuntimeError(record['error'])
        return deepcopy(record['raw_response'])


def stable(run):
    result=deepcopy(run)
    for key in ('run_id','created_at','latency_ms','execution_kind'):result.pop(key,None)
    for record in result['trace']:record.pop('latency_ms',None)
    return result


def summary(runs, labels=None):
    groups=defaultdict(list)
    for run in runs:groups[(run['method'],run['case']['split'],run['case'].get('challenge','real'))].append(run)
    result=[]
    for (method,split,challenge),rows in sorted(groups.items()):
        synthetic=split=='synthetic_heldout'
        supported=sum(bool(r['comparison']['calculation']) for r in rows)
        rejected=sum(bool(x['validation']['errors']) for r in rows for x in r['extractions'])
        fabricated=0;strict_flags=0
        for r in rows:
            if challenge in {'missing_table','stale_disclosure'}:
                # Count any candidate attributed to the missing/current source, even if rejected.
                fabricated+=any(x['metric']['source_id']==r['case']['new'] and x['metric']['status']=='provided' for x in r['extractions'])
            elif challenge=='contradictory_commentary':
                expected=set(r['case']['transformation']['expected_conflict_quotes'])
                strict_flags+=any(expected=={x['quote'] for x in c['citations']} for c in r['conflicts'])
        accepted=[labels['cases'][r['case']['case_id']] for r in rows if labels and r['case']['case_id'] in labels['cases'] and labels['cases'][r['case']['case_id']]['review_status']=='reviewed']
        entry={'method':method,'split':split,'challenge':challenge,'cases':len(rows),
               'numeric_comparisons':supported,'abstentions':sum(r['conclusion']=='insufficient_evidence' for r in rows),
               'conflict_flags':sum(r['conclusion']=='conflicting' for r in rows),
               'calls':sum(r['calls'] for r in rows),'runs_with_errors':sum(bool(r['errors']) for r in rows),
               'rejected_metric_candidates':rejected,'latency_ms_sum':round(sum(r['latency_ms'] for r in rows),3),
               'tokens':sum(r['tokens']['total_tokens'] for r in rows if r['tokens']) if all(r['tokens'] is not None or r['calls']==0 for r in rows) else None,
               'human_reviewed_cases':len(accepted),'revision_precision':None,'revision_recall':None,
               'numeric_exact_match_rate':None,'direction_accuracy':None,'human_explanation_support_rate':None,
               'correct_status_rate':sum(r['conclusion']==r['case']['expected_status'] for r in rows)/len(rows) if synthetic else None,
               'two_expected_citations_rate':strict_flags/len(rows) if challenge=='contradictory_commentary' else None,
               'fabrication_rate':fabricated/len(rows) if challenge in {'missing_table','stale_disclosure'} else None,
               'direction_definition':'Any numerical abstention maps to not_comparable; errors and missed eligible revisions remain incorrect when gold provides a direction.',
               'fabrication_definition':'Provided metric attributed to an absent/current source in an absence control; includes rejected candidates. Other semantic fabrication is unmeasured.'}
        if accepted:
            gold={r['case']['case_id']:labels['cases'][r['case']['case_id']] for r in rows if r['case']['case_id'] in labels['cases'] and labels['cases'][r['case']['case_id']]['review_status']=='reviewed'}
            tp=fp=fn=correct=exact=0
            for r in rows:
                if r['case']['case_id'] not in gold:continue
                truth=gold[r['case']['case_id']];direction=truth['direction']
                reason=r['comparison']['reason']
                predicted=('not_comparable' if r['comparison']['status']=='insufficient_evidence' else
                           {'unchanged':'maintained','guidance_withdrawn':'withdrawn'}.get(reason,reason))
                positive=direction in {'raised','lowered','mixed_range','withdrawn'}
                detected=predicted in {'raised','lowered','mixed_range','withdrawn'}
                tp+=positive and detected;fp+=(not positive) and detected;fn+=positive and not detected
                correct+=predicted==direction
                calc=r['comparison']['calculation']
                if calc and truth['expected_midpoint_delta_usd'] is not None:
                    # Exact means all four normalized endpoints and the delta, not merely equal net changes.
                    bounds=truth['normalized_bounds']
                    exact+=all(number(calc[k])==number(v) for k,v in bounds.items()) and number(calc['midpoint_delta'])==number(truth['expected_midpoint_delta_usd'])
            entry.update(revision_precision=tp/(tp+fp) if tp+fp else None,revision_recall=tp/(tp+fn) if tp+fn else None,
                         direction_accuracy=correct/len(gold),numeric_exact_match_rate=exact/sum(gold[c]['expected_midpoint_delta_usd'] is not None for c in gold) if any(gold[c]['expected_midpoint_delta_usd'] is not None for c in gold) else None)
        result.append(entry)
    return result


def report_text(report):
    lines=['# Earnings investigation benchmark v2','',
           f"Saved runs: {report['completed_runs']} / {report['planned_runs']}. Real quarterly pairs: 36 (12 development, 24 held out); 12 issuers. Synthetic held-out controls: 72; natural supplements: 2.",
           '','Human-reviewed labels: '+str(report['human_reviewed_cases'])+'. Unreviewed cases do not contribute to accuracy. Model-selected explanation support remains pending human review.',
           '', 'Costs use peak, cache-miss prices and include retained reservations for uncertain requests. These are conservative token estimates, not a provider invoice.',
           '', '| Method | Split | Control | n | Numeric outputs | Abstain | Conflict | Expected status | Both expected citations | Calls |',
           '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    def fmt(v):return 'unmeasured' if v is None else f'{v:.1%}'
    for row in report['metrics']:
        lines.append(f"| {row['method']} | {row['split']} | {row['challenge']} | {row['cases']} | {row['numeric_comparisons']} | {row['abstentions']} | {row['conflict_flags']} | {fmt(row['correct_status_rate'])} | {fmt(row['two_expected_citations_rate'])} | {row['calls']} |")
    lines += ['', '## Interpretation', '',
              'The synthetic contradictory sentences are invented controls. Literal citations are validated against the saved source and, for C, the text actually retrieved. A model conflict flag on natural text is still a semantic-review candidate.',
              'The missing-table variant masks all numeric tokens throughout the new disclosure, including duplicate prose, actuals and headings. It tests missing numerical evidence; it does not isolate table parsing. Stale pairs fail before model access.',
              'A and D retain their frozen extraction rules. All four methods use the same original literal/semantic screen and Decimal arithmetic. The screen can reject valid complex layouts. B/C use one model and common extraction instructions; C has more calls and retrieves context. This is not compute matched.',
              'The two natural supplements are development-issuer diagnostics, outside the 36 quarterly pairs. Unit/scope changes in the real corpus require human labels before their correctness can be scored.',
              'A historical disclosure cutoff does not remove training-data exposure. This benchmark measures extraction and evidence discipline, not leakage-free investment performance.',
              '', 'See summary.json, runs/, requests/, sources.json, jobs.json and freeze.json for the complete record. Replay uses recorded responses and makes no network calls.', '']
    return '\n'.join(lines)
