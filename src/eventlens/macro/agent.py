"""A single bounded controller: choose a tool, observe, draft, validate, revise."""
from __future__ import annotations
import json
import time
from uuid import uuid4

from ..core import canonical, digest, now
from ..llm import strict_json
from .baseline import build_baseline
from .prompts import PROMPT_VERSION, SYSTEM, TOOLS
from .tools import ResearchTools
from .validation import validate_brief


def validate_config(config):
    bounds = {'max_calls':(1, 20), 'max_tool_calls':(0, 18),
              'max_output_tokens_per_call':(100, 8000), 'max_input_characters':(1000, 250000),
              'max_brief_words':(50, 1000), 'freshness_days':(1, 90)}
    for key, (low, high) in bounds.items():
        if type(config.get(key)) is not int or not low <= config[key] <= high:
            raise ValueError('invalid budget: '+key)


def run_brief(sources, case, method, config, adapter=None, cutoff_mode='publication', include_watchlist=None):
    validate_config(config)
    if method not in {'rules', 'single', 'agent'}:
        raise ValueError('unknown macro method')
    if method != 'rules' and adapter is None:
        raise ValueError('a model adapter is required')
    tools = ResearchTools(sources, case, cutoff_mode, include_watchlist)
    started = time.perf_counter()
    run = {'run_id':str(uuid4()), 'created_at':now(), 'workflow':'macro', 'case':case,
           'method':method, 'cutoff_mode':cutoff_mode,
           'execution_kind':'deterministic' if method == 'rules' else adapter.kind,
           'model':None if method == 'rules' else adapter.model,
           'config':dict(config), 'prompt_version':PROMPT_VERSION,
           'source_hashes':{sid:s.content_hash for sid,s in sources.items()},
           'eligible_source_ids':sorted(tools.sources),
           'excluded_source_ids':sorted(set(sources)-set(tools.sources)),
           'calendar':tools.events, 'broad_scope':tools.broad_scope, 'brief':None, 'status':'insufficient_evidence',
           'validation':None, 'calls':0, 'tool_calls':0, 'tokens':None,
           'trace':[], 'errors':[]}
    if not tools.events:
        run['brief'] = {'items': [], 'omissions': []}
        run['validation'] = validate_brief(run['brief'], tools, config)
        run['trace'].append({'stage': 'scope_check', 'result': 'no eligible calendar events; no model call needed'})
    elif method == 'rules':
        run['brief'] = build_baseline(tools)
        run['validation'] = validate_brief(run['brief'], tools, config)
        run['trace'].append({'stage':'baseline', 'algorithm':'latest eligible statement policy sentence; no interpretation'})
    else:
        _investigate(run, tools, config, adapter)
    if run['brief'] is not None and run['validation']['valid']:
        if not run['brief']['items'] or not any(item['claims'] for item in run['brief']['items']):
            run['status'] = 'insufficient_evidence'
        else:
            run['status'] = 'partial' if run['brief']['omissions'] else 'ready_for_review'
    elif run['errors'] or run['validation']:
        run['status'] = 'failed'
    if tools.broad_scope and run['brief']:
        selected = {i['event_id'] for i in run['brief']['items']}
        run['coverage'] = [{'event_id':e['event_id'], 'selected':e['event_id'] in selected,
                            'date_status':e['date_status']} for e in tools.events]
        if run['status'] == 'ready_for_review' and (any(i['gaps'] for i in run['brief']['items']) or
                any(e['date_status'] == 'watchlist' for e in tools.events)):
            run['status'] = 'partial'
    run['latency_ms'] = round((time.perf_counter()-started)*1000, 3)
    run['input_hash'] = digest(canonical({'case':case, 'sources':run['source_hashes'], 'config':config,
                                         'method':method, 'cutoff_mode':cutoff_mode,
                                         **({'include_watchlist':include_watchlist, 'calendar':tools.events} if tools.broad_scope else {})}))
    return run


def _investigate(run, tools, config, adapter):
    single = run['method'] == 'single'
    max_calls = 1 if single else config['max_calls']
    header = {'task':tools.case, 'budgets':config, 'broad_scope':tools.broad_scope,
              'sources':[s.metadata(tools.case['as_of']) for s in tools.sources.values()],
              'coverage':'Select important verified events and research watchlist risks across the requested markets. Reference URLs in the catalog are discovery links, not claim evidence.'}
    if single:
        header['calendar'] = tools.execute('list_events', {})
        header['documents'] = [{'source_id':s.source_id, 'text':s.text} for s in tools.sources.values()]
        tools.shown = {sid:[(0, len(s.text))] for sid,s in tools.sources.items()}
    messages = [{'role':'system', 'content':SYSTEM+('' if single else TOOLS)},
                {'role':'user', 'content':json.dumps(header, ensure_ascii=False)}]
    usages = []
    for call in range(max_calls):
        if sum(len(m['content']) for m in messages) > config['max_input_characters']:
            run['errors'].append('input_context_budget_exhausted')
            break
        record = {'stage':'model_call', 'call':call+1, 'messages':list(messages),
                  'max_output_tokens':config['max_output_tokens_per_call']}
        run['trace'].append(record)
        run['calls'] += 1
        t0 = time.perf_counter()
        try:
            raw = adapter.complete(messages, config['max_output_tokens_per_call'])
            record['raw_response'] = raw
            record['latency_ms'] = round((time.perf_counter()-t0)*1000, 3)
            if isinstance(raw.get('usage'), dict):
                usages.append(raw['usage'])
            run['tokens'] = ({k:sum(u.get(k, 0) for u in usages)
                              for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
                             if len(usages) == run['calls'] else None)
            choice = raw['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('incomplete_model_output')
            content = choice['message']['content']
            action = strict_json(content)
            if not isinstance(action, dict):
                raise ValueError('action must be an object')
            messages.append({'role':'assistant', 'content':content})
            if action.get('action') == 'finish':
                if set(action) != {'action', 'brief'}:
                    raise ValueError('finish requires action and brief only')
                validation = validate_brief(action['brief'], tools, config)
                run['trace'].append({'stage':'draft_validation', 'draft':action['brief'], **validation})
                run['validation'] = validation
                if validation['valid']:
                    run['brief'] = action['brief']
                    return
                feedback = {'validation_errors':validation['errors'], 'instruction':'Revise or retrieve evidence; unsupported claims must be omitted.'}
            elif action.get('action') == 'tool' and not single:
                if (set(action) != {'action', 'name', 'arguments', 'reason'}
                        or not isinstance(action['reason'], str) or not 1 <= len(action['reason']) <= 400):
                    raise ValueError('invalid tool action fields/reason')
                if run['tool_calls'] >= config['max_tool_calls']:
                    raise ValueError('tool_budget_exhausted')
                if call == max_calls-1:
                    raise ValueError('no remaining model call to use tool result')
                run['tool_calls'] += 1
                event = {'stage':'tool_call', 'name':action['name'], 'arguments':action['arguments'], 'reason':action['reason']}
                run['trace'].append(event)
                try:
                    output = tools.execute(action['name'], action['arguments'])
                except (ValueError, KeyError, TypeError) as exc:
                    output = {'error':str(exc)}
                event['result'] = output
                feedback = {'tool_result_DATA':output}
            else:
                raise ValueError('invalid action for this method')
            feedback['remaining_model_calls'] = max_calls-call-1
            messages.append({'role':'user', 'content':json.dumps(feedback, ensure_ascii=False)})
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError, StopIteration, AttributeError) as exc:
            record['error'] = str(exc) or type(exc).__name__
            run['errors'].append(record['error'])
            break
    if not run['errors']:
        run['errors'].append('no_valid_brief_within_call_budget')
