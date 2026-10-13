"""Dated occurrences with exact source spans, including tentative date windows."""
from datetime import date
import json
from zoneinfo import ZoneInfo
from .catalog import CATALOG

MARKER = '\n\nEVENTLENS_SCHEDULE_V1\n'
FIELDS = {'family_id', 'name', 'start_date', 'end_date', 'timezone', 'date_status', 'quotes'}


def encode_schedule(text, records):
    if MARKER in text or not 1 <= len(records) <= 500:
        raise ValueError('invalid calendar document')
    for record in records:
        validate_record(record, text)
    return text + MARKER + '\n'.join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records)


def validate_record(record, text):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError('invalid schedule fields')
    if not isinstance(record['family_id'], str) or record['family_id'] not in CATALOG:
        raise ValueError('unknown event family')
    if not isinstance(record['name'], str) or not 1 <= len(record['name']) <= 300:
        raise ValueError('invalid event name')
    if any(not isinstance(record[k], str) for k in ('start_date','end_date','date_status')):
        raise ValueError('schedule dates and status must be strings')
    start, end = (date.fromisoformat(record[k]) for k in ('start_date', 'end_date'))
    if start > end or (end-start).days > 31:
        raise ValueError('event date window must span 1..32 days')
    if record['date_status'] not in {'confirmed', 'tentative', 'window'}:
        raise ValueError('unsupported date status')
    if not isinstance(record['timezone'], str):
        raise ValueError('timezone must be an IANA name')
    try:
        ZoneInfo(record['timezone'])
    except (KeyError, ValueError):
        raise ValueError('unknown IANA timezone') from None
    quotes = record['quotes']
    if (not isinstance(quotes, list) or not 1 <= len(quotes) <= 4 or
            any(not isinstance(q, str) or not q.strip() or len(q) > 2000 or q not in text for q in quotes)):
        raise ValueError('calendar requires exact source quotations')


def decode_schedule(source):
    from .records import citation
    if source.text.count(MARKER) != 1:
        raise ValueError('calendar document requires one schedule section')
    text, encoded = source.text.split(MARKER)
    rows = encoded.splitlines()
    if not 1 <= len(rows) <= 500:
        raise ValueError('invalid calendar record count')
    events = []
    for row in rows:
        record = json.loads(row)
        validate_record(record, text)
        family = CATALOG[record['family_id']]['calendar_family']
        # Release name distinguishes CPI and PPI; unemployment and payrolls share a family.
        from ..core import digest
        suffix = digest(record['name'].casefold())[:8] if family == 'us_inflation' else ''
        event = {**CATALOG[family], **{k:v for k,v in record.items() if k != 'quotes'},
                 'family_id': family, 'event_id': family+'-'+record['end_date']+('-'+suffix if suffix else ''),
                 'date_precision': 'window' if record['date_status'] == 'window' else 'day',
                 'category': family, 'date_evidence': []}
        for quote in record['quotes']:
            start = text.index(quote)
            event['date_evidence'].append(citation(source, start, start+len(quote)))
        events.append(event)
    return events
