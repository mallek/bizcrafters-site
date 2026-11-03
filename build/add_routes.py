"""Turn pasted Discord event text into GPX route files on the site.

Usage (local test):
  python3 build/add_routes.py --site . --body-file paste.txt [--title "Add route"] [--summary out.md]
Usage (GitHub Actions, issue event):
  python3 build/add_routes.py --site . --event "$GITHUB_EVENT_PATH" --summary summary.md

Format it understands: a heading line (any text, markdown and emoji are stripped), followed by
coordinate lines like `19.4350330, -99.1413480`. Several headings in one paste make several routes.
Lines like "(Click to Copy)", "Your Time", dates and blank lines are ignored.

Stdlib only. Input is treated strictly as data: only numbers and a sanitized short name are used.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import unicodedata

REGION_NUM = 16
REGION_NAME = 'Event spots (jump lists)'
MAX_SECTIONS = 12
MAX_POINTS = 300
MAX_BODY = 30000

COORD = re.compile(r'(-?\d{1,2}\.\d{3,})\s*[,;/ ]\s*(-?\d{1,3}\.\d{3,})')
IGNORE = re.compile(
    r'click to copy|your time|<t:|\bunknown\b|^\W*$|'
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b',
    re.I)


def clean_text(s):
    s = re.sub(r'<!--.*?-->', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]*>', ' ', s)
    s = re.sub(r'[*_#>`~]', '', s)
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if ord(ch) > 0xFFFF or cat in ('So', 'Sk', 'Cs', 'Cn', 'Cc', 'Cf'):
            continue
        out.append(ch)
    s = ''.join(out)
    s = s.replace('\u2014', '-').replace('\u2013', '-')
    s = re.sub(r'\s*\|\s*', ', ', s)
    s = re.sub(r'^[\s\u2022\-:.]+', '', s)
    s = re.sub(r'[^\w ,.\-()&\'/]', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' :.-,')
    return s[:80]


def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()[:60]


def xesc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def parse(body, title_fallback, merge=False):
    body = re.sub(r'<!--.*?-->', ' ', body[:MAX_BODY], flags=re.S)
    sections = []
    cur = None
    closed = False
    pending = None
    for line in body.splitlines():
        coords = COORD.findall(line)
        if coords:
            if cur is None or closed:
                name = pending or title_fallback or 'Event spots'
                cur = {'header': name, 'pts': []}
                sections.append(cur)
                closed = False
            for la, lo in coords:
                lat, lon = float(la), float(lo)
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    if not cur['pts'] or cur['pts'][-1] != (lat, lon):
                        cur['pts'].append((lat, lon))
            pending = None
        else:
            txt = clean_text(line)
            if not txt or IGNORE.search(line) or IGNORE.search(txt) or not re.search(r'[^\W\d_]', txt):
                continue
            pending = txt
            closed = True
    sections = [s for s in sections if s['pts']]
    if merge and sections:
        pts = []
        for sec in sections:
            for p in sec['pts']:
                if not pts or pts[-1] != p:
                    pts.append(p)
        return [{'header': title_fallback, 'pts': pts}]
    return sections[:MAX_SECTIONS]


def gpx_text(display, short, pts):
    out = ['<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
           '<gpx version="1.1" creator="rocky (event spots from Discord paste)" '
           'xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
           '<metadata><name>%s</name></metadata>' % xesc(display)]
    for i, (la, lo) in enumerate(pts, 1):
        out.append('<wpt lat="%.7f" lon="%.7f"><name>%s</name></wpt>' % (la, lo, xesc('%s spot %d' % (short, i))))
    out.append('</gpx>')
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default='.')
    ap.add_argument('--body-file')
    ap.add_argument('--event')
    ap.add_argument('--title', default='')
    ap.add_argument('--summary')
    ap.add_argument('--domain', default='https://pogo.bizcrafters.com')
    a = ap.parse_args()

    title, body = a.title, ''
    if a.event:
        ev = json.load(open(a.event, encoding='utf-8'))
        title = ev['issue'].get('title') or ''
        body = ev['issue'].get('body') or ''
    elif a.body_file:
        body = open(a.body_file, encoding='utf-8').read()
    title_fallback = clean_text(re.sub(r'^\s*add( routes?)?\s*[:\-]?\s*', '', title, flags=re.I))

    sections = parse(body, title_fallback, merge=bool(title_fallback))
    lines = []
    if not sections:
        msg = ('No coordinates found. Paste the Discord text with lines like `19.4350330, -99.1413480` '
               'under a heading, then edit this issue to try again.')
        print(msg)
        if a.summary:
            open(a.summary, 'w', encoding='utf-8').write(msg + '\n')
        return 2

    site = a.site
    manifest_path = os.path.join(site, 'routes.json')
    routes = json.load(open(manifest_path, encoding='utf-8'))
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    for sec in sections:
        header = sec['header']
        display = header + ' (event spots)'
        short = header.split(',')[-1].strip() or header
        slug = 'event-' + (slugify(header) or 'spots')
        pts = sec['pts'][:MAX_POINTS]
        with open(os.path.join(site, 'gpx', slug + '.gpx'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(gpx_text(display, short, pts))
        entry = {'slug': slug, 'name': display, 'num': REGION_NUM, 'region': REGION_NAME, 'added': today, 'n': len(pts)}
        existing = [i for i, r in enumerate(routes) if r['slug'] == slug]
        if existing:
            routes[existing[0]] = entry
        else:
            routes.append(entry)
        lines.append('- **%s**: %d spot%s - [map](%s/#p=%s) - [gpx](%s/gpx/%s.gpx)' % (display, len(pts), '' if len(pts) == 1 else 's', a.domain, slug, a.domain, slug))
    with open(manifest_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(routes, f, ensure_ascii=False, indent=0)
        f.write('\n')
    subprocess.run([sys.executable, os.path.join(site, 'build', 'index.py'), site], check=True)

    summary = 'Added %d route%s:\n\n%s\n\nThe site updates in a minute or two.' % (len(sections), '' if len(sections) == 1 else 's', '\n'.join(lines))
    print(summary)
    if a.summary:
        open(a.summary, 'w', encoding='utf-8').write(summary + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
