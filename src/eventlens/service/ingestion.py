"""Public Fed RSS ingestion and timestamped text imports, without model access."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from ..core import canonical, digest, now, timestamp
from ..macro.records import MacroSource

FED_FEED = 'https://www.federalreserve.gov/feeds/press_monetary.xml'
MAX_BYTES = 2_000_000


def check_fed_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'www.federalreserve.gov'
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.query or parsed.fragment or '\\' in url
            or not re.fullmatch(r'/(?:feeds/press_monetary\.xml|newsevents/pressreleases/monetary\d{8}[a-z]\.htm|monetarypolicy/fomcminutes\d{8}\.htm)', parsed.path)):
        raise ValueError('URL is outside the supported Federal Reserve source paths')


class FedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_fed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_fed(url):
    check_fed_url(url)
    request = Request(url, headers={'User-Agent': 'EventLens/0.3 research agent',
                                   'Accept': 'application/xml,text/html', 'Accept-Encoding': 'identity'})
    try:
        with build_opener(FedRedirect()).open(request, timeout=20) as response:
            check_fed_url(response.url)
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError('source response exceeds size limit')
            return content.decode('utf-8-sig')
    except HTTPError as exc:
        raise RuntimeError(f'fed_http_error_{exc.code}') from None
    except (URLError, TimeoutError, UnicodeError):
        raise RuntimeError('fed_transport_or_encoding_error') from None


class Article(HTMLParser):
    """Keep the article's text and paragraph boundaries, omitting navigation/scripts."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
    BLOCK = {'p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'tr', 'br'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.hidden = 0
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if not self.depth:
            if attrs.get('id') != 'article':
                return
            self.depth = 1
        elif tag not in self.VOID:
            self.depth += 1
        if tag in {'script', 'style'}:
            self.hidden += 1
        if tag in self.BLOCK and not self.hidden:
            self.parts.append('\n\n')

    def handle_endtag(self, tag):
        if self.depth:
            if tag in {'script', 'style'}:
                self.hidden = max(0, self.hidden-1)
            if tag in self.BLOCK and not self.hidden:
                self.parts.append('\n\n')
            if tag not in self.VOID:
                self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.hidden:
            self.parts.append(data)

    def text(self):
        paragraphs = [' '.join(p.split()) for p in ''.join(self.parts).split('\n\n')]
        result = '\n\n'.join(p for p in paragraphs if p)
        if len(result) < 100:
            raise ValueError('Federal Reserve article text was not found')
        return result


def make_source(*, title, publisher, url, published_at, document_date, kind, text,
                available_at=None, retrieved_at=None, topics=None, markets=None):
    published = timestamp(published_at).isoformat()
    retrieved = retrieved_at or now()
    if timestamp(published) > timestamp(retrieved):
        raise ValueError('publication time is in the future')
    data = dict(title=title, publisher=publisher, url=url, published_at=published,
                available_at=timestamp(available_at or published).isoformat(),
                document_date=document_date, kind=kind, markets=markets or ['US'], topics=topics or ['monetary_policy'],
                content_hash=digest(text), text=text)
    sid = 'source-' + digest(canonical(data))[:32]
    return MacroSource(source_id=sid, retrieved_at=retrieved, **data)


def refresh_fed(database, limit=8, fetch=fetch_fed):
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('refresh limit must be 1..20')
    raw_feed = fetch(FED_FEED)
    if '<!DOCTYPE' in raw_feed.upper() or '<!ENTITY' in raw_feed.upper():
        raise ValueError('XML declarations are not supported')
    feed = ET.fromstring(raw_feed)
    result = {'feed': FED_FEED, 'retrieved_at': now(), 'added': 0, 'unchanged': 0,
              'source_ids': [], 'errors': []}
    selected = []
    for item in feed.findall('./channel/item'):
        title = item.findtext('title', '').strip()
        if title.startswith('Minutes of the Federal Open Market Committee'):
            kind = 'minutes'
        elif title == 'Federal Reserve issues FOMC statement':
            kind = 'statement'
        else:
            continue
        selected.append((item, title, kind))
        if len(selected) == limit:
            break
    if not selected:
        raise ValueError('feed contains no supported FOMC releases')
    for item, title, kind in selected:
        url = item.findtext('link', '').strip()
        try:
            published = parsedate_to_datetime(item.findtext('pubDate')).astimezone(timezone.utc).isoformat()
            if timestamp(published) > timestamp(now()):
                raise ValueError('feed publication time is in the future')
            check_fed_url(url)
            release_html = fetch(url)
            article = Article()
            article.feed(release_html)
            captures = [{'url': url, 'sha256': digest(release_html), 'content': release_html}]
            if kind == 'minutes':
                paths = [p for p in article.links if re.fullmatch(r'/monetarypolicy/fomcminutes\d{8}\.htm', p)]
                if len(set(paths)) != 1:
                    raise ValueError('release must identify one minutes document')
                url = urljoin(url, paths[0])
                full_html = fetch(url)
                article = Article()
                article.feed(full_html)
                captures.append({'url': url, 'sha256': digest(full_html), 'content': full_html})
                document_date = datetime.strptime(re.search(r'(\d{8})\.htm$', url)[1], '%Y%m%d').date().isoformat()
            else:
                document_date = timestamp(published).date().isoformat()
            source = make_source(title=title, publisher='Federal Reserve', url=url, published_at=published,
                                 document_date=document_date, kind=kind, text=article.text(), markets=['US', 'GLOBAL'])
            added = database.add_source(source, {
                'method': 'fed-rss-v1', 'feed_url': FED_FEED, 'feed_sha256': digest(raw_feed),
                'feed_item': ET.tostring(item, encoding='unicode'), 'captures': captures,
                'normalization': 'article element text; whitespace collapsed within paragraphs',
            })
            result['added' if added else 'unchanged'] += 1
            result['source_ids'].append(source.source_id)
        except (ValueError, RuntimeError, TypeError, IndexError) as exc:
            # Errors are actionable and partial refreshes retain successful imports.
            result['errors'].append({'url': url, 'error': str(exc)})
    return result
