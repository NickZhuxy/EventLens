"""Scripted actions for controller tests. These are not LLM outputs or findings."""
from copy import deepcopy
from ..llm import MockAdapter
from .baseline import build_baseline
from .records import citation
from .tools import ResearchTools


def scripted_adapter(sources, case, repair=False, cutoff_mode='publication'):
    tools = ResearchTools(sources, case, cutoff_mode)
    brief = build_baseline(tools)
    for item in brief['items']:
        if not item['claims']:
            continue
        source = sources[item['claims'][0]['evidence'][0]['source_id']]
        paragraph = next((p for p in source.text.splitlines() if p.startswith('In assessing the appropriate stance')), None)
        if paragraph:
            start = source.text.index(paragraph)
            item['claims'].append({'kind':'risk', 'context':'historical', 'channel':'policy',
                                  'statement':'A change in the assessment of incoming information could change the policy outlook. Review the next statement for changes to these policy conditions.',
                                  'evidence':[citation(source, start, start+len(paragraph))]})
            item['gaps'] = ['Current market consensus is not established by the supplied corpus.',
                            'The policy note is a scripted interpretation for analyst review. Historical market reactions are not established.']
    replies = [{'action':'tool', 'name':'list_events', 'arguments':{},
                'reason':'Scripted fixture: inspect events in this time window.'},
               {'action':'tool', 'name':'search_sources', 'arguments':{'query':'target range federal funds rate'},
                'reason':'Scripted fixture: find the last policy decision.'}]
    # Exact reads demonstrate interval validation independently of search ranking.
    intervals = {}
    for item in brief['items']:
        for claim in item['claims']:
            cite = claim['evidence'][0]
            previous = intervals.get(cite['source_id'], (cite['start'], cite['end']))
            intervals[cite['source_id']] = (min(previous[0], cite['start']), max(previous[1], cite['end']))
    for sid, (start, end) in intervals.items():
        replies.append({'action':'tool', 'name':'read_source',
                        'arguments':{'source_id':sid, 'start':start, 'end':end},
                        'reason':'Scripted fixture: read policy context and the conditions for changing it.'})
    if repair and brief['items'] and brief['items'][0]['claims']:
        invalid = deepcopy(brief)
        invalid['items'][0]['claims'][0]['evidence'][0]['quote'] = 'This text is not in the source.'
        replies.append({'action':'finish', 'brief':invalid})
    replies.append({'action':'finish', 'brief':brief})
    return MockAdapter(replies)
