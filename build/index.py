"""Regenerate index.html from routes.json and build/template.html.

Stdlib only, so it runs anywhere (local, GitHub Actions).
Usage: python3 build/index.py [site_dir]
"""
import html
import json
import os
import re
import sys


def area_of(name):
    nm = re.sub(r'^\[[^\]]*\]\s*', '', name)
    return nm.split(',')[0].strip() if ',' in nm else ''


def build_index(site):
    routes = json.load(open(os.path.join(site, 'routes.json'), encoding='utf-8'))
    regions = sorted({(r['num'], r['region']) for r in routes})
    ridx = {name: i for i, (_, name) in enumerate(regions)}
    routes = sorted(routes, key=lambda r: (ridx[r['region']], area_of(r['name']).lower(), r['name'].lower()))
    rows = []
    for r in routes:
        rows.append('<li data-r="%d" data-a="%s" data-d="%s" data-w="%d"><a href="/gpx/%s.gpx">%s</a> <span class="w">%d pts</span></li>' % (
            ridx[r['region']], html.escape(area_of(r['name']), quote=True), r['added'], r['n'],
            r['slug'], html.escape(r['name'], quote=False), r['n']))
    regjs = ','.join('"%s"' % name.replace('"', '\\"') for _, name in regions)
    page = open(os.path.join(site, 'build', 'template.html'), encoding='utf-8').read()
    page = page.replace('{{COUNT}}', str(len(routes))).replace('{{REGIONS}}', regjs).replace('{{ROWS}}', '\n'.join(rows))
    with open(os.path.join(site, 'index.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(page)
    return len(routes), len(regions)


if __name__ == '__main__':
    site = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    n, r = build_index(site)
    print(n, 'routes', r, 'regions')
