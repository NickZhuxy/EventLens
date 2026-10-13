"""Allowlisted official calendars with isolated failures and retained captures."""
from datetime import date, datetime
from html.parser import HTMLParser
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..core import digest, now, timestamp
from ..macro.catalog import CATALOG
from ..macro.schedules import encode_schedule
from .ingestion import MAX_BYTES, make_source, refresh_fed

URLS = {
    'nyfed': 'https://www.newyorkfed.org/research/calendars/nationalecon_cal.html',
    'ecb': 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html',
    'usda': 'https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report',
    'cftc': 'https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm',
    'nbs': 'https://www.stats.gov.cn/sj/fbrc/bnxxfb/',
}
PUBLISHERS = {'nyfed': 'Federal Reserve Bank of New York', 'ecb': 'European Central Bank', 'usda': 'US Department of Agriculture',
              'cftc': 'Commodity Futures Trading Commission', 'nbs': 'National Bureau of Statistics of China',
              'bls': 'US Bureau of Labor Statistics'}
PROVIDERS = ('fed', 'ecb', 'usda', 'cftc', 'nbs', 'nyfed', 'bls')
MONTHS = {datetime(2026, m, 1).strftime('%B').lower(): m for m in range(1, 13)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


def check_url(url):
    parsed = urlparse(url)
    allowed = url in URLS.values() or bool(re.fullmatch(r'https://www\.bls\.gov/schedule/20\d{2}/home\.htm', url))
    allowed = allowed or bool(re.fullmatch(r'https://www\.newyorkfed\.org/research/calendars/i-(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{2}\.html', url))
    if not allowed or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('URL is outside the supported official calendar paths')


class CalendarRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_calendar(url):
    check_url(url)
    try:
        with build_opener(CalendarRedirect()).open(Request(url, headers={
            'User-Agent': 'EventLens/0.4 research agent', 'Accept': 'text/html', 'Accept-Encoding': 'identity'}), timeout=20) as response:
            check_url(response.url)
            raw = response.read(MAX_BYTES+1)
            if len(raw) > MAX_BYTES:
                raise ValueError('source response exceeds size limit')
            return raw.decode('utf-8-sig')
    except HTTPError as exc:
        raise RuntimeError('calendar_http_error_'+str(exc.code)) from None
    except (URLError, TimeoutError, UnicodeError):
        raise RuntimeError('calendar_transport_or_encoding_error') from None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1
        if not self.hidden:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden-1)
        if not self.hidden:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(html):
    parser = PlainText(); parser.feed(html)
    return ' '.join(''.join(parser.parts).split())


def record(family, start, quotes, *, end=None, name=None, status='confirmed', zone='UTC'):
    return dict(family_id=family, name=name or CATALOG[family]['name'], start_date=start,
                end_date=end or start, timezone=zone, date_status=status, quotes=quotes)


def parse_ecb(html):
    rows = [(plain(d), plain(v)) for d,v in re.findall(r'<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>', html, re.S)]
    records, evidence, pending = [], [], None
    for index, (day, description) in enumerate(rows):
        if 'monetary policy meeting' not in description or 'non-monetary' in description:
            continue
        value = datetime.strptime(day, '%d/%m/%Y').date().isoformat()
        quote = day+' '+description
        evidence.append(quote)
        if '(Day 1)' in description:
            pending = (value, quote)
        elif '(Day 2)' in description:
            if pending is None or (date.fromisoformat(value)-date.fromisoformat(pending[0])).days != 1:
                raise ValueError('ECB meeting pair is incomplete')
            records.append(record('ecb_policy', pending[0], [pending[1], quote], end=value, zone='Europe/Berlin'))
            pending = None
        else:
            if pending:
                raise ValueError('ECB meeting pair is incomplete')
            following = rows[index+1] if index+1 < len(rows) else ('', '')
            if '(Day 2)' in following[1] and 'monetary policy meeting' in following[1]:
                pending = (value, quote)
            else:
                records.append(record('ecb_policy', value, [quote], zone='Europe/Berlin'))
    if pending:
        raise ValueError('ECB meeting pair is incomplete')
    return '\n'.join(evidence), records


def parse_usda(html):
    text = plain(html)
    # Month abbreviations include periods; stop at the end of the December entry.
    match = re.search(r'In (20\d{2}) the WASDE report will be released on (.+?Dec\.?\s+\d{1,2})\.', text)
    if not match:
        raise ValueError('WASDE annual release sentence was not found')
    pairs = re.findall(r'([A-Za-z]+)\.?\s+(\d{1,2})', match[2])
    if len(pairs) != 12:
        raise ValueError('WASDE calendar must contain twelve releases')
    records = [record('usda_wasde', date(int(match[1]), MONTHS[m.lower()], int(d)).isoformat(),
                      [match[0]], zone='America/New_York') for m,d in pairs]
    return match[0], records


def parse_cftc(html):
    text = plain(html)
    heading = re.search(r'(20\d{2}) Release Schedule', text)
    if not heading:
        raise ValueError('CFTC calendar year not found')
    year = int(heading[1]); evidence = [heading[0]]; records = []
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, re.S):
        cells = [plain(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', row, re.S)]
        if not cells or cells[0].lower() not in MONTHS:
            continue
        quote = ' '.join(cells).strip(); evidence.append(quote)
        for cell in cells[1:]:
            if not cell:
                continue
            if not re.fullmatch(r'\d{2}\*?', cell):
                raise ValueError('unrecognized CFTC release cell')
            value = date(year, MONTHS[cells[0].lower()], int(cell.rstrip('*'))).isoformat()
            records.append(record('cftc_cot', value, [heading[0], quote], status='tentative', zone='America/New_York'))
    if len(records) < 48:
        raise ValueError('CFTC annual calendar is incomplete')
    return '\n'.join(evidence), records


def parse_nbs(html):
    text = plain(html)
    heading = re.search(r'(20\d{2})年国家统计局主要统计信息发布日程表', text)
    if not heading:
        raise ValueError('NBS calendar year not found')
    evidence, records = [heading[0]], []
    rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, re.S)
    for row in rows:
        cells = [plain(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', row, re.S)]
        if len(cells) != 14 or cells[1] != '采购经理指数月度报告':
            continue
        # Preserve month labels when normalizing a table; never infer the last day.
        for month, cell in enumerate(cells[2:], 1):
            quote = f'{month}月 采购经理指数月度报告 {cell}'
            evidence.append(quote)
            for day in re.findall(r'(\d{1,2})/[一二三四五六日天]', cell):
                value = date(int(heading[1]), month, int(day)).isoformat()
                records.append(record('cn_pmi', value, [heading[0], quote], status='tentative', zone='Asia/Shanghai'))
    if len(records) != 12:
        raise ValueError('NBS annual PMI calendar must contain twelve releases')
    return '\n'.join(evidence), records


def parse_bls(html):
    text = plain(html)
    year_match = re.search(r'(20\d{2}) News Releases', text) or re.search(r'Schedule.*?(20\d{2})', text)
    if not year_match:
        raise ValueError('BLS calendar year not found')
    year = int(year_match[1]); evidence, records = [], []
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, re.S):
        quote = plain(row)
        names = [('Employment Situation', 'us_employment'), ('Consumer Price Index', 'us_inflation'),
                 ('Producer Price Index', 'us_inflation')]
        family = next(((n,f) for n,f in names if n+' for ' in quote), None)
        if family is None:
            continue
        match = re.search(r'([A-Z][a-z]+)\.?\s+(\d{1,2})(?:,?\s+(20\d{2}))?', quote)
        if not match or match[1].lower() not in MONTHS:
            raise ValueError('BLS release date not recognized')
        release = date(int(match[3] or year), MONTHS[match[1].lower()], int(match[2])).isoformat()
        evidence.append(quote)
        records.append(record(family[1], release, [str(year)+' News Releases', quote], name='US '+family[0], zone='America/New_York'))
    return '\n'.join([str(year)+' News Releases']+evidence), records


PARSERS = {'ecb': parse_ecb, 'usda': parse_usda, 'cftc': parse_cftc, 'nbs': parse_nbs, 'bls': parse_bls}


def refresh_calendars(database, providers=PROVIDERS, limit=8, fetch=fetch_calendar, fed_fetch=None):
    if not providers or len(providers) != len(set(providers)) or any(p not in PROVIDERS for p in providers):
        raise ValueError('invalid calendar provider selection')
    result = {'retrieved_at': now(), 'added': 0, 'unchanged': 0, 'source_ids': [], 'errors': [], 'providers': {}}
    for provider in providers:
        try:
            if provider in {'fed', 'nyfed'}:
                extra = {} if fed_fetch is None else {'fetch': fed_fetch}
                value = refresh_fed(database, limit, **extra) if provider == 'fed' else refresh_nyfed(database, fetch)
                for key in ('added', 'unchanged'):
                    result[key] += value[key]
                result['source_ids'].extend(value['source_ids'])
                result['errors'].extend({'provider': provider, **e} for e in value['errors'])
                result['providers'][provider] = {'status': 'partial' if value['errors'] else 'ok', 'sources': len(value['source_ids'])}
                continue
            url = URLS.get(provider) or f'https://www.bls.gov/schedule/{timestamp(now()).year}/home.htm'
            raw = fetch(url)
            text, events = PARSERS[provider](raw)
            if not events:
                raise ValueError('calendar contains no supported events')
            encoded = encode_schedule(text, events)
            # An unchanged page retains its first-observed cutoff; never backdate a capture.
            existing = next((s for s in database.sources().values() if s.url == url and s.content_hash == digest(encoded)), None)
            if existing:
                result['unchanged'] += 1
                source = existing
            else:
                observed = now()
                markets = sorted({m for e in events for m in CATALOG[e['family_id']]['markets']})
                source = make_source(title=PUBLISHERS[provider]+' release calendar', publisher=PUBLISHERS[provider],
                    url=url, published_at=observed, retrieved_at=observed, document_date=timestamp(observed).date().isoformat(),
                    kind='calendar', text=encoded, markets=markets, topics=sorted({e['family_id'] for e in events}))
                database.add_source(source, {'method': provider+'-calendar-v1', 'timestamp_basis': 'first observed; publication time unknown',
                    'captures': [{'url': url, 'sha256': digest(raw), 'content': raw}],
                    'normalization': 'calendar rows with year/month headings retained; parsed occurrences appended'})
                result['added'] += 1
            result['source_ids'].append(source.source_id)
            result['providers'][provider] = {'status': 'ok', 'occurrences': len(events), 'source_id': source.source_id}
        except (ValueError, RuntimeError, TypeError, IndexError, KeyError) as exc:
            result['errors'].append({'provider': provider, 'error': str(exc)})
            result['providers'][provider] = {'status': 'failed'}
    return result


def parse_nyfed(html):
    """Read publisher calendar cells; do not substitute usual release weekdays."""
    heading = next((plain(c) for c in re.findall(r'<td\b[^>]*class="ts-data-table-head"[^>]*>(.*?)</td>', html, re.S)
                    if re.fullmatch(r'[A-Z][a-z]+ 20\d{2}', plain(c))), None)
    if not heading:
        raise ValueError('NY Fed calendar month not found')
    month, year = heading.split(); month, year = MONTHS[month.lower()], int(year)
    names = {'Employment Situation': ('us_employment', 'US Employment Situation'),
             'Consumer Price Index': ('us_inflation', 'US Consumer Price Index'),
             'Producer Price Index (PPI)': ('us_inflation', 'US Producer Price Index'),
             'ISM Manufacturing': ('us_ism', 'US ISM manufacturing PMI'),
             'Consumer Confidence': ('us_confidence', 'US consumer confidence')}
    records, evidence = [], [heading]
    for cell in re.findall(r'<td\b[^>]*>(.*?)</td>', html, re.S):
        labels = [plain(c) for c in re.findall(r'<a\b[^>]*>(.*?)</a>', cell, re.S)]
        supported = [name for name in labels if name in names]
        if not supported:
            continue
        quote = plain(cell)
        day = re.match(r'(\d{1,2})\s', quote)
        if not day:
            raise ValueError('NY Fed release cell has no day')
        value = date(year, month, int(day[1])).isoformat()
        evidence.append(quote)
        for name in supported:
            family, title = names[name]
            records.append(record(family, value, [heading, quote], name=title, zone='America/New_York'))
    if not records:
        raise ValueError('NY Fed calendar has no supported releases')
    return '\n'.join(evidence), records


def refresh_nyfed(database, fetch=fetch_calendar):
    result = {'added':0, 'unchanged':0, 'source_ids':[], 'errors':[]}
    url, visited = URLS['nyfed'], set()
    for _ in range(3):
        try:
            check_url(url)
            if url in visited:
                raise ValueError('NY Fed next-month link repeats a page')
            visited.add(url)
            raw = fetch(url)
            text, events = parse_nyfed(raw)
            encoded = encode_schedule(text, events)
            existing = next((s for s in database.sources().values() if s.url == url and s.content_hash == digest(encoded)), None)
            if existing:
                source = existing
                result['unchanged'] += 1
            else:
                observed = now()
                source = make_source(title='NY Fed economic indicators calendar', publisher=PUBLISHERS['nyfed'], url=url,
                    published_at=observed, retrieved_at=observed, document_date=timestamp(observed).date().isoformat(),
                    kind='calendar', markets=['US','GLOBAL'], topics=sorted({e['family_id'] for e in events}), text=encoded)
                database.add_source(source, {'method':'nyfed-calendar-v1',
                    'timestamp_basis':'first observed; publication time unknown',
                    'captures':[{'url':url,'sha256':digest(raw),'content':raw}],
                    'normalization':'month heading and calendar cells retained; parsed occurrences appended'})
                result['added'] += 1
            result['source_ids'].append(source.source_id)
            link = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>\s*NEXT MONTH', raw, re.I)
            if not link:
                break
            url = urljoin(url, link[1])
        except (ValueError, RuntimeError, TypeError, IndexError, KeyError) as exc:
            result['errors'].append({'url':url, 'error':str(exc)})
            break
    return result
