"""Versioned earnings investigation; frozen v1 runs keep their original pipeline.

All methods share the original eligibility, metric validation and Decimal comparison.
A/D stay frozen. B/C additionally propose cited conflicts and comparability warnings.
Literal validation is not a judgment that a management explanation is true.
"""
from copy import deepcopy
from dataclasses import asdict
import json
import re
import time
from uuid import uuid4

from .core import Metric, canonical, compare, digest, now, timestamp
from .extraction import validate_evidence
from .llm import SYSTEM, CONTROLLER, strict_json
from .pipeline import run_pair as legacy_run_pair
from .retrieval import ReadTools

VERSION = 'earnings-investigation-v2'
SYSTEM_V2 = SYSTEM + '''
Also investigate explanations for this SAME annual total-revenue revision. Distinguish
reported from constant-currency guidance, total from segment revenue, different years,
and changes in acquisition/consolidation scope. These differences are not contradictions.
An increase followed by a later decrease is not by itself a conflicting explanation.
Do not infer a management explanation from general positive commentary.
Finish JSON also has "conflicts": [] and "comparability": null.
For an actual apparent contradiction use:
"conflicts":[{"topic":"driver or proposition", "reason":"why the same proposition conflicts",
"statement_a":{"source_id":"...","quote":"exact statement"},
"statement_b":{"source_id":"...","quote":"exact opposing statement"}}].
Both statements must address the same period, scope and basis. A quote containing a
number is not enough to establish a causal explanation. Empty conflicts is allowed.
If definitions or consolidation scope prevent a like-for-like comparison, use
"comparability":{"status":"not_comparable","reason":"short explanation",
"evidence":[{"source_id":"...","quote":"exact scope/definition statement"}]}.
Otherwise use null. A warning requires literal evidence; it is a review candidate.
Do not copy a previous range into a disclosure whose guidance values are absent.
'''
CONTROLLER_V2 = CONTROLLER + '''
After checking annual values, actively search the current disclosure for guidance
explanations and opposing claims. Retrieve both sides of any apparent conflict before
finishing. Consider a search for "demand caused not guidance revision"; also investigate
currency or acquisition scope when the source warrants it. All tools read only the
allowed pair. At your last call finish with the evidence you have, or abstain.
'''


def citation(item, sources, shown=None):
    if not isinstance(item, dict) or set(item) != {'source_id', 'quote'}:
        raise ValueError('citation_requires_source_id_and_quote')
    sid, quote = item['source_id'], item['quote']
    if sid not in sources or not isinstance(quote, str) or not quote.strip():
        raise ValueError('invalid_citation')
    source = sources[sid]
    if quote not in source.text:
        raise ValueError('citation_not_literal')
    if shown is not None and not any(quote in window for window in shown.get(sid, [])):
        raise ValueError('citation_not_in_retrieved_context')
    start = source.text.index(quote)
    return {**item, 'start': start, 'end': start+len(quote), 'source_hash': source.content_hash,
            'url': source.url, 'origin': 'synthetic' if source.snapshot_kind.startswith('SYNTHETIC') else 'disclosure',
            'literal_valid': True, 'semantic_review': 'pending'}


def validate_conflicts(items, sources, shown):
    if not isinstance(items, list) or len(items) > 5:
        raise ValueError('invalid_conflicts')
    result = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'topic', 'reason', 'statement_a', 'statement_b'}:
            raise ValueError('conflict_requires_two_statements_topic_and_reason')
        if not all(isinstance(item[k], str) and item[k].strip() for k in ('topic', 'reason')):
            raise ValueError('conflict_requires_explanation')
        a, b = [citation(item[k], sources, shown) for k in ('statement_a', 'statement_b')]
        if a['quote'] == b['quote']:
            raise ValueError('conflict_requires_distinct_opposing_statements')
        result.append({'topic': item['topic'], 'reason': item['reason'], 'citations': [a, b],
                       'semantic_review': 'pending', 'kind': 'model_flagged_apparent_conflict'})
    return result


def explicit_conflicts(claims, sources):
    """Narrow rule control: opposite polarity of an otherwise identical proposition."""
    positive, negative = {}, {}
    for claim in claims:
        quote = claim['quote'].strip()
        m = re.fullmatch(r'(Demand|Currency|Pricing|Volume) (caused|drove|did not cause|did not drive) (.+)', quote, re.I)
        if not m:
            continue
        key = (m[1].lower(), m[3].lower())
        (negative if m[2].lower().startswith('did not') else positive)[key] = claim
    result = []
    for key in sorted(positive.keys() & negative.keys()):
        result.append({'topic': key[0], 'reason': 'opposite_polarity_same_literal_proposition',
                       'citations': [citation({k: c[k] for k in ('source_id','quote')}, sources)
                                     for c in (positive[key], negative[key])],
                       'semantic_review': 'pending', 'kind': 'explicit_lexical_conflict'})
    return result


def model_extract_v2(selected, case, method, adapter, config, run):
    max_calls = 1 if method == 'B' else config['max_calls']
    max_tools = 0 if method == 'B' else config['max_tool_calls']
    max_output = config['max_output_tokens_per_call']
    max_context = config['max_input_characters']
    if not (1 <= max_calls <= 12 and 0 <= max_tools <= 10 and 1 <= max_output <= 8000
            and 1000 <= max_context <= 200000):
        raise ValueError('invalid_model_budgets')
    sources = {s.source_id: s for s in selected}
    shown = {sid: [] for sid in sources}
    header = {'question': f"Compare {case['issuer']} {case['horizon']} total revenue guidance and investigate conflicting explanations",
              'cutoff': case['cutoff'], 'allowed_sources_in_order': list(sources),
              'source_metadata': [{'source_id': s.source_id, 'issuer': s.issuer,
                                  'published_at': s.published_at, 'length': len(s.text)} for s in selected]}
    if method == 'B':
        header['disclosures'] = [{'source_id': s.source_id, 'text': s.text} for s in selected]
        shown = {s.source_id: [s.text] for s in selected}
    messages = [{'role':'system','content':SYSTEM_V2 + (CONTROLLER_V2 if method=='C' else '')},
                {'role':'user','content':json.dumps(header,ensure_ascii=False)}]
    tools = ReadTools(sources, list(sources), case['cutoff'])
    run.update(model=adapter.model, execution_kind=adapter.kind, prompt_version=VERSION,
               context_policy='full_pair_snapshots' if method=='B' else 'pair_scoped_tool_windows',
               model_budget={'max_calls': max_calls, 'max_tool_calls': max_tools,
                             'max_output_tokens_per_call': max_output, 'max_input_characters_per_call': max_context})
    usages, tool_count = [], 0
    run['context_characters'] = sum(len(q) for spans in shown.values() for q in spans)
    for call in range(max_calls):
        if sum(len(m['content']) for m in messages) > max_context:
            run['errors'].append('input_context_budget_exhausted'); break
        record = {'stage':'model_call','call':call+1,'messages':deepcopy(messages),'max_output_tokens':max_output}
        run['trace'].append(record)
        started = time.perf_counter()
        try:
            run['calls'] += 1
            raw = adapter.complete(messages,max_output)
            record['raw_response'] = raw
            record['latency_ms'] = round((time.perf_counter()-started)*1000,3)
            if isinstance(raw.get('usage'),dict): usages.append(raw['usage'])
            run['tokens'] = ({k:sum(u.get(k,0) for u in usages) for k in ('prompt_tokens','completion_tokens','total_tokens')}
                             if len(usages)==run['calls'] else None)
            choice = raw['choices'][0]
            if choice.get('finish_reason') != 'stop': raise ValueError('incomplete_model_output')
            content = choice['message']['content']; response = strict_json(content)
            if not isinstance(response,dict): raise ValueError('model_output_must_be_object')
            messages.append({'role':'assistant','content':content})
            if response.get('action') == 'finish':
                values = response.get('metrics')
                if not isinstance(values,list) or len(values)!=2: raise ValueError('expected_two_ordered_metrics')
                metrics = [Metric(**v) if v is not None else None for v in values]
                for source,metric in zip(selected,metrics):
                    if metric and (metric.source_id!=source.source_id or not any(metric.horizon_evidence in q for q in shown[source.source_id])):
                        raise ValueError('citation_not_in_supplied_context')
                explanations = response.get('explanations',[])
                if not isinstance(explanations,list) or len(explanations)>10: raise ValueError('invalid_explanations')
                validated = [citation(c,sources,shown) for c in explanations]
                conflicts = validate_conflicts(response.get('conflicts',[]),sources,shown)
                warning = response.get('comparability')
                if warning is not None:
                    if not isinstance(warning,dict) or set(warning)!={'status','reason','evidence'} or warning['status']!='not_comparable':
                        raise ValueError('invalid_comparability_warning')
                    if not isinstance(warning['reason'],str) or not warning['reason'].strip(): raise ValueError('missing_comparability_reason')
                    if not isinstance(warning['evidence'],list) or not 1<=len(warning['evidence'])<=4: raise ValueError('comparability_requires_citations')
                    warning={**warning,'evidence':[citation(c,sources,shown) for c in warning['evidence']], 'semantic_review':'pending'}
                # Commit only after every citation in the finish action validates.
                run['explanations'] = validated; run['conflicts'] = conflicts; run['comparability'] = warning
                return metrics
            if method!='C' or response.get('action')!='tool': raise ValueError('invalid_action')
            if tool_count>=max_tools or call==max_calls-1: raise ValueError('tool_or_call_budget_exhausted')
            tool_count+=1
            event={'stage':'tool_call','name':response.get('name'),'arguments':response.get('arguments'),'reason':response.get('reason','')}
            run['trace'].append(event)
            try: output=tools.execute(event['name'],event['arguments'])
            except (ValueError,KeyError,TypeError) as exc: output={'error':str(exc)}
            event['result']=output
            for part in output.get('passages',[output]):
                if 'quote' in part:
                    shown[part['source_id']].append(part['quote']);run['context_characters']+=len(part['quote'])
            messages.append({'role':'user','content':json.dumps({'tool_result_DATA':output,'remaining_model_calls':max_calls-call-1},ensure_ascii=False)})
        except (ValueError,KeyError,TypeError,IndexError,RuntimeError,StopIteration) as exc:
            record['error']=str(exc) or type(exc).__name__;run['errors'].append(record['error']);break
    if not run['errors']: run['errors'].append('model_call_budget_exhausted')
    return [None,None]


def run_investigation(sources, case, method, config, adapter=None):
    selected=[sources[case[k]] for k in ('old','new')]
    scoped={s.source_id:s for s in selected}
    if method in {'A','D'}:
        run=legacy_run_pair(sources,case,method,config=config)
        run['conflicts']=explicit_conflicts(run['explanations'],scoped)
        run['comparability']=None
    elif method in {'B','C'}:
        start=time.perf_counter()
        run={'run_id':str(uuid4()),'created_at':now(),'case':case,'method':method,'config':config,
             'cutoff_mode':'disclosure','trace':[],'extractions':[],'explanations':[],'conflicts':[],
             'comparability':None,'errors':[],'calls':0,'tokens':None,'label_status':'not_used_by_system',
             'human_semantic_review':'pending','source_hashes':{s.source_id:s.content_hash for s in selected}}
        run['input_hash']=digest(canonical({'case':case,'sources':run['source_hashes']}))
        if selected[0].issuer!=selected[1].issuer or selected[0].issuer!=case['issuer']:run['errors'].append('issuer_mismatch')
        if timestamp(selected[0].available_at)>=timestamp(selected[1].available_at):run['errors'].append('stale_or_reversed_disclosure_pair')
        if any(not s.eligible(case['cutoff']) for s in selected):run['errors'].append('source_after_cutoff')
        if run['errors']:
            result={'status':'insufficient_evidence','reason':run['errors'][0],'calculation':None}
        else:
            metrics=model_extract_v2(selected,case,method,adapter,config,run)
            valid=[]
            for source,metric in zip(selected,metrics):
                if metric:
                    validation=validate_evidence(metric,source)
                    if metric.horizon!=case['horizon']:validation['errors'].append('question_horizon_mismatch')
                    if metric.metric!=case.get('metric','revenue'):validation['errors'].append('question_metric_mismatch')
                    if validation['errors']:validation['semantic_screen']='fail'
                    run['extractions'].append({'metric':asdict(metric),'validation':validation})
                    valid.append(metric if not validation['errors'] else None)
                else:valid.append(None)
            result=compare(*valid)
            if run['comparability']:
                result={'status':'insufficient_evidence','reason':'model_flagged_scope_or_definition_change','calculation':None}
        run['comparison']=result
        run['trace'].append({'stage':'deterministic_comparison','result':result})
        run['latency_ms']=round((time.perf_counter()-start)*1000,3)
    else:raise ValueError('unknown_method')
    run['investigation_version']=VERSION
    run['explanation_conclusion']=({'status':'conflicting','reason':'two_cited_opposing_statements',
                                    'conflicts':run['conflicts'],'semantic_review':'pending'} if run['conflicts'] else
                                   {'status':'insufficient_evidence','reason':'semantic_review_required' if run['explanations'] else 'no_explicit_explanation_found'})
    run['conclusion']='conflicting' if run['conflicts'] else run['comparison']['status']
    return run
