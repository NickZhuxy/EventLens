"""Reproducible normalization and integrity checks for saved web-reader captures."""
import re
from .core import digest

LINE = re.compile(r'(?:^|\s)L(\d+): ?(.*?)(?=(?:\n| )L\d+:|$)', re.S)


def normalize_capture(capture):
    """Keep every rendered line; reject gaps, conflicting pages, or wrong URLs."""
    lines = {}
    totals = set()
    for page in capture['pages']:
        header = page.split('\nL', 1)[0]
        if capture['url'] not in header:
            raise ValueError('capture URL mismatch')
        total = re.search(r'Total lines: (\d+)', header)
        if not total:
            raise ValueError('reader response has no line count')
        totals.add(int(total[1]))
        for n, value in LINE.findall(page):
            # Retain link labels, remove reader-only citation wrappers.
            value = re.sub(r'\ue200cite\ue202\d+†([^\ue201]*)\ue201', r'\1', value)
            value = re.sub(r'【\d+†([^】]*)】', r'\1', value).rstrip()
            n = int(n)
            if n in lines and lines[n] != value:
                raise ValueError(f'conflicting reader line {n}')
            lines[n] = value
    if len(totals) != 1 or set(lines) != set(range(next(iter(totals)))):
        raise ValueError('incomplete or inconsistent reader capture')
    text = '\n'.join(lines[i] for i in range(len(lines))) + '\n'
    return text, {'total_lines': len(lines), 'captured_lines': len(lines),
                  'complete': True, 'content_hash': digest(text)}
