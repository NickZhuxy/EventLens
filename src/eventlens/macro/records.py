"""Source identity, publication-time boundaries, and a source-derived calendar."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from ..core import digest, timestamp
from .catalog import MARKETS, intersects


@dataclass(frozen=True)
class MacroSource:
    source_id: str
    title: str
    publisher: str
    url: str
    published_at: str
    available_at: str
    retrieved_at: str
    document_date: str
    kind: str
    markets: list[str]
    topics: list[str]
    content_hash: str
    text: str

    def __post_init__(self):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', self.source_id):
            raise ValueError('invalid macro source identity')
        url = urlparse(self.url)
        if url.scheme != 'https' or not url.netloc or url.username or url.password:
            raise ValueError('source requires an HTTPS URL without credentials')
        times = [timestamp(v) for v in (self.published_at, self.available_at, self.retrieved_at)]
        if times != sorted(times):
            raise ValueError('source timestamps out of order')
        if date.fromisoformat(self.document_date) > times[0].date():
            raise ValueError('document date is later than publication')
        if not self.text.strip() or digest(self.text) != self.content_hash:
            raise ValueError('source text is empty or hash-mismatched')
        if self.kind not in {'statement', 'minutes', 'market_expectations', 'economic_release', 'calendar', 'analyst_report', 'market_history', 'news'}:
            raise ValueError('unsupported source kind')
        if any(m not in MARKETS for m in self.markets):
            raise ValueError('unsupported market code')
        if not self.title or not self.publisher or not self.markets or not self.topics:
            raise ValueError('source metadata is incomplete')

    def eligible(self, as_of, mode='publication'):
        if mode not in {'publication', 'snapshot'}:
            raise ValueError('invalid cutoff mode')
        times = [self.published_at, self.available_at]
        if mode == 'snapshot':
            times.append(self.retrieved_at)
        return all(timestamp(v) <= timestamp(as_of) for v in times)

    def metadata(self, as_of):
        record = asdict(self)
        record.pop('text')
        record['characters'] = len(self.text)
        record['context_age_days'] = (timestamp(as_of).date() - date.fromisoformat(self.document_date)).days
        return record


def _local_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('source file outside corpus directory')
    return path


def load_sources(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    sources = {}
    for record in manifest['sources']:
        meta = dict(record)
        text = _local_file(path.parent, meta.pop('path')).read_text()
        capture = _local_file(path.parent, meta.pop('capture_path')).read_text()
        if digest(capture) != meta.pop('capture_hash'):
            raise ValueError('capture hash mismatch')
        meta.pop('capture_lines')
        release = meta.pop('release_evidence', None)
        if release and digest(_local_file(path.parent, release['path']).read_text()) != release['hash']:
            raise ValueError('release evidence hash mismatch')
        source = MacroSource(text=text, **meta)
        if source.source_id in sources:
            raise ValueError('duplicate macro source ID')
        sources[source.source_id] = source
    return manifest, sources


def validate_case(case):
    required = {'case_id', 'as_of', 'start_date', 'end_date', 'markets', 'split', 'question'}
    if set(case) != required:
        raise ValueError('invalid case fields')
    if not re.fullmatch(r'[a-z0-9-]+', case['case_id']):
        raise ValueError('invalid case identity')
    start, end = (date.fromisoformat(case[k]) for k in ('start_date', 'end_date'))
    if start > end or (end-start).days > 31:
        raise ValueError('briefing window must be 1..32 days')
    if timestamp(case['as_of']).astimezone(ZoneInfo('America/New_York')).date() > start:
        raise ValueError('briefing starts before its information cutoff')
    if not isinstance(case['markets'], list) or not case['markets'] or any(x not in MARKETS for x in case['markets']):
        raise ValueError('unsupported market code')
    if case['split'] not in {'development', 'temporal_check', 'custom', 'synthetic'}:
        raise ValueError('invalid case split')
    if not isinstance(case['question'], str) or not 1 <= len(case['question']) <= 1000:
        raise ValueError('question must contain 1..1000 characters')


MONTHS = {datetime(2025, n, 1).strftime('%B'): n for n in range(1, 13)}
NEXT_MEETING = re.compile(
    r'It was agreed that the next meeting of the Committee would be held on '
    r'[A-Za-z–—-]+, (?P<month>[A-Za-z]+) (?P<first>\d{1,2})[–—-](?P<last>\d{1,2}), (?P<year>\d{4})\.'
)


def citation(source, start, end):
    return {'source_id': source.source_id, 'start': start, 'end': end, 'quote': source.text[start:end]}


def calendar(sources, case, mode='publication'):
    """Extract exact meeting dates from eligible minutes, never from later outcomes."""
    validate_case(case)
    events = {}
    for source in sources.values():
        if not source.eligible(case['as_of'], mode) or not intersects(source.markets, case['markets']):
            continue
        if source.kind == 'calendar':
            from .schedules import decode_schedule
            for event in decode_schedule(source):
                if not intersects(event['markets'], case['markets']):
                    continue
                if event['end_date'] < case['start_date'] or event['start_date'] > case['end_date']:
                    continue
                previous = events.get(event['event_id'])
                if previous and any(previous.get(k, 'confirmed') != event[k] for k in ('start_date', 'end_date', 'date_status')):
                    raise ValueError('conflicting event dates require calendar review')
                if previous:
                    previous['date_evidence'].extend(event['date_evidence'])
                else:
                    events[event['event_id']] = event
            continue
        if source.kind != 'minutes':
            continue
        for match in NEXT_MEETING.finditer(source.text):
            month = MONTHS.get(match['month'])
            if month is None:
                continue
            start = date(int(match['year']), month, int(match['first'])).isoformat()
            end = date(int(match['year']), month, int(match['last'])).isoformat()
            if start > end:
                raise ValueError('reversed event date range')
            if end < case['start_date'] or start > case['end_date']:
                continue
            event_id = 'fomc-' + end
            event = events.setdefault(event_id, {
                'event_id': event_id, 'name': 'FOMC policy meeting', 'start_date': start,
                'end_date': end, 'timezone': 'America/New_York', 'date_precision': 'day',
                'markets': ['US'], 'category': 'monetary_policy', 'date_evidence': []})
            if event['start_date'] != start:
                raise ValueError('conflicting event dates require calendar review')
            event['date_evidence'].append(citation(source, match.start(), match.end()))
    return sorted(events.values(), key=lambda e: e['start_date'])
