"""Mechanical checks for a draft. Semantic support still needs human review."""
from __future__ import annotations
from datetime import date
import re

from ..core import timestamp

CHANNELS = {'policy', 'volatility', 'liquidity', 'credit'}


def narrative_words(brief):
    text = []
    if not isinstance(brief, dict):
        return 0
    for item in brief.get('items', []):
        if isinstance(item, dict):
            claims, gaps = item.get('claims'), item.get('gaps')
            if isinstance(claims, list):
                text.extend(str(c.get('statement', '')) for c in claims if isinstance(c, dict))
            if isinstance(gaps, list):
                text.extend(str(g) for g in gaps)
    text.extend(str(x.get('reason', '')) for x in brief.get('omissions', []) if isinstance(x, dict))
    return len(' '.join(text).split())


def validate_brief(brief, tools, config):
    errors = []
    if not isinstance(brief, dict) or set(brief) != {'items', 'omissions'}:
        return {'valid': False, 'errors': ['brief requires items and omissions only']}
    if not isinstance(brief['items'], list) or not isinstance(brief['omissions'], list):
        return {'valid': False, 'errors': ['items and omissions must be arrays']}
    if len(brief['items']) + len(brief['omissions']) > (200 if tools.broad_scope else 20):
        return {'valid': False, 'errors': ['too many event records']}
    if tools.broad_scope and len(brief['items']) > 8:
        errors.append('select at most eight important events')
    expected = {e['event_id'] for e in tools.events}
    if tools.broad_scope and tools.seen_events != expected:
        errors.append('retrieve the event universe before selecting important events')
    handled = []
    citation_count = 0
    claim_count = 0
    for n, item in enumerate(brief['items']):
        prefix = f'items[{n}]'
        if not isinstance(item, dict) or set(item) != {'event_id', 'claims', 'gaps'}:
            errors.append(prefix + ': invalid item fields')
            continue
        event_id = item['event_id']
        if not isinstance(event_id, str) or event_id not in expected:
            errors.append(prefix + ': unknown/out-of-window event')
            continue
        handled.append(event_id)
        if event_id not in tools.seen_events:
            errors.append(prefix + ': event not retrieved')
        if not isinstance(item['gaps'], list) or len(item['gaps']) > 5 or any(
                not isinstance(g, str) or not 1 <= len(g) <= 400 for g in item['gaps']):
            errors.append(prefix + ': invalid gaps')
        if not isinstance(item['claims'], list) or len(item['claims']) > 8:
            errors.append(prefix + ': claims must be an array of at most eight entries')
            continue
        for j, claim in enumerate(item['claims']):
            where = prefix + f'.claims[{j}]'
            if not isinstance(claim, dict) or set(claim) != {'kind', 'statement', 'context', 'channel', 'evidence'}:
                errors.append(where + ': invalid claim fields')
                continue
            claim_count += 1
            kind, statement = claim['kind'], claim['statement']
            if kind not in ('fact', 'expectation', 'risk', 'historical_impact', 'analyst_view') or claim['context'] not in ('current', 'historical'):
                errors.append(where + ': invalid kind/context')
            if not isinstance(statement, str) or not 1 <= len(statement) <= 1200:
                errors.append(where + ': invalid statement')
                continue
            if kind == 'risk':
                if not isinstance(claim['channel'], str) or claim['channel'] not in CHANNELS:
                    errors.append(where + ': invalid risk channel')
                if re.search(r'\d', statement):
                    errors.append(where + ': numerical risk forecasts are outside scope')
            elif claim['channel'] is not None:
                errors.append(where + ': channel must be null for facts/expectations')
            evidence = claim['evidence']
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 4:
                errors.append(where + ': each claim requires 1..4 citations')
                continue
            quotes = []
            for k, cite in enumerate(evidence):
                at = where + f'.evidence[{k}]'
                if not isinstance(cite, dict) or set(cite) != {'source_id', 'start', 'end', 'quote'}:
                    errors.append(at + ': invalid citation fields')
                    continue
                sid = cite['source_id']
                if not isinstance(sid, str) or sid not in tools.sources:
                    errors.append(at + ': source outside market scope or information cutoff')
                    continue
                source = tools.sources[sid]
                start, end, quote = cite['start'], cite['end'], cite['quote']
                if (type(start) is not int or type(end) is not int or not isinstance(quote, str)
                        or not 0 <= start < end <= len(source.text) or not quote.strip()
                        or end-start > 2000 or source.text[start:end] != quote):
                    errors.append(at + ': citation offsets/quote do not match source')
                    continue
                if not any(a <= start and end <= b for a, b in tools.shown[sid]):
                    errors.append(at + ': citation was not returned to this method')
                if claim['context'] == 'current':
                    age = (timestamp(tools.case['as_of']).date() - date.fromisoformat(source.document_date)).days
                    if age > config['freshness_days']:
                        errors.append(at + ': stale material cannot be labeled current')
                if kind == 'historical_impact' and (source.kind != 'market_history' or claim['context'] != 'historical'):
                    errors.append(at + ': historical impact requires a market_history source and historical context')
                if kind == 'analyst_view' and source.kind != 'analyst_report':
                    errors.append(at + ': analyst views require a dated analyst_report source')
                if kind == 'expectation' and (source.kind != 'market_expectations' or claim['context'] != 'current'):
                    errors.append(at + ': current market expectations need a dedicated, dated expectations source')
                quotes.append(quote)
                citation_count += 1
            # A conservative lexical screen, not a semantic or numerical proof.
            if kind != 'risk':
                numbers = set(re.findall(r'\d+(?:[.,]\d+)*', statement))
                if not numbers <= set(re.findall(r'\d+(?:[.,]\d+)*', ' '.join(quotes))):
                    errors.append(where + ': number not present in cited evidence')
    for omission in brief['omissions']:
        if (not isinstance(omission, dict) or set(omission) != {'event_id', 'reason'}
                or not isinstance(omission['event_id'], str) or omission['event_id'] not in expected
                or not isinstance(omission['reason'], str) or not 1 <= len(omission['reason']) <= 400):
            errors.append('invalid omission record')
        else:
            handled.append(omission['event_id'])
    if len(handled) != len(set(handled)):
        errors.append('duplicate event or event both included and omitted')
    if not tools.broad_scope and set(handled) != expected:
        errors.append('each calendar event must be included or explicitly omitted')
    words = narrative_words(brief)
    if words > config['max_brief_words']:
        errors.append('brief exceeds narrative word budget')
    return {'valid': not errors, 'errors': errors, 'narrative_words': words,
            'claims': claim_count, 'citations': citation_count,
            'semantic_review': 'pending' if claim_count else 'not_applicable'}
