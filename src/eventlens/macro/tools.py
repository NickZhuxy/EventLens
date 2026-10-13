"""Validated, read-only access to the eligible macro corpus."""
from __future__ import annotations
import re
from .records import calendar, citation, validate_case
from .catalog import CATALOG, intersects, watchlist


class ResearchTools:
    def __init__(self, sources, case, mode='publication', include_watchlist=None):
        validate_case(case)
        self.case = case
        self.sources = {sid: s for sid, s in sources.items()
                        if s.eligible(case['as_of'], mode) and intersects(s.markets, case['markets'])}
        self.broad_scope = include_watchlist is not None
        self.events = calendar(self.sources, case, mode)
        if self.broad_scope:
            self.events = [{**CATALOG[e.get('family_id', 'fomc')], 'date_status': 'confirmed', **e}
                           for e in self.events]
            if include_watchlist:
                self.events += watchlist(self.events, case['markets'])
            self.events.sort(key=lambda e: (e['date_status'] == 'watchlist', e['priority'] != 'high', e['start_date'] or '', e['event_id']))
        self.shown = {sid: [] for sid in self.sources}
        self.seen_events = set()

    def show(self, value):
        """Remember actual returned intervals, including evidence in calendar records."""
        if isinstance(value, dict):
            if {'source_id', 'start', 'end', 'quote'} <= value.keys():
                self.shown[value['source_id']].append((value['start'], value['end']))
            for child in value.values():
                self.show(child)
        elif isinstance(value, list):
            for child in value:
                self.show(child)
        return value

    def execute(self, name, args):
        if not isinstance(args, dict):
            raise ValueError('tool arguments must be an object')
        if name == 'list_events':
            if args:
                raise ValueError('list_events takes no arguments; scope comes from the case')
            self.seen_events.update(e['event_id'] for e in self.events)
            return self.show({'events': self.events, 'coverage': 'Source-verified dates and undated research watchlist' if self.broad_scope else 'Dated events in saved sources',
                              'selection': 'Select up to eight important events. Unselected candidates remain in the coverage export.'})
        if name == 'search_sources':
            if not {'query'} <= set(args) <= {'query', 'event_id', 'kind'} or not isinstance(args['query'], str) or not 1 <= len(args['query']) <= 300:
                raise ValueError('search_sources requires query (1..300 characters)')
            scope = next((e for e in self.events if e['event_id'] == args.get('event_id')), None)
            if 'event_id' in args and scope is None:
                raise ValueError('unknown event_id')
            terms = set(re.findall(r'\w+', args['query'].lower())) - {'the', 'and', 'of', 'to', 'a', 'in'}
            candidates = []
            for source in self.sources.values():
                if args.get('kind') and source.kind != args['kind']:
                    continue
                if scope and not (scope.get('family_id', 'fomc') in source.topics or set(scope.get('markets', [])) & set(source.markets)):
                    continue
                offset = 0
                for paragraph in source.text.splitlines(keepends=True):
                    content = paragraph.rstrip('\r\n')
                    score = len(terms & set(re.findall(r'\w+', content[:1800].lower())))
                    if score and content:
                        end = offset + min(len(content), 1800)
                        candidates.append({**citation(source, offset, end), 'score': score,
                                           'metadata': source.metadata(self.case['as_of'])})
                    offset += len(paragraph)
            candidates.sort(key=lambda x: (-x['score'], -int(x['metadata']['document_date'].replace('-', '')),
                                          x['source_id'], x['start']))
            return self.show({'passages': candidates[:5], 'matching_passages':len(candidates),
                              'ranking': 'query word overlap, then document date; not semantic relevance'})
        if name == 'read_source':
            if set(args) != {'source_id', 'start', 'end'}:
                raise ValueError('read_source requires source_id, start, end')
            sid, start, end = args['source_id'], args['start'], args['end']
            if not isinstance(sid, str) or sid not in self.sources:
                raise ValueError('source outside market scope or information cutoff')
            source = self.sources[sid]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source.text):
                raise ValueError('invalid character offsets')
            if end-start > 6000:
                raise ValueError('read_source is limited to 6000 characters')
            return self.show({**citation(source, start, end), 'metadata':source.metadata(self.case['as_of'])})
        raise ValueError('unknown tool; only list_events, search_sources, read_source are allowed')
