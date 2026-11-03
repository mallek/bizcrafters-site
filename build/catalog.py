# ONE-TIME seed script (reads the original zip on the author machine). Retired: routes.json is now the source of truth.
# New routes are added by build/add_routes.py, which also runs in CI. Do not re-run this; it would reset routes.json.
import os, re, hashlib, unicodedata, html, shutil, datetime

SRC = 'C:/Users/travi/AppData/Local/Temp/gpxsample/GPX Routes 02-03-2024'
SITE = 'D:/Skunkworks/bizcrafters-site'
OUT = SITE + '/gpx'
TODAY = datetime.date.today().isoformat()
ZIPDATE = '2024-02-03'

def clean_region(folder):
    m = re.match(r'(\d+)\.\s*(.*)', folder)
    num, name = int(m.group(1)), m.group(2)
    name = {'New City Routes from 2024': 'City routes (2024)',
            'Old City Routes': 'City routes (older)',
            'Massive City Routes from BlisseyBuster': 'Massive city routes',
            'Hotspots & Events by GMT DST ON': 'Hotspots and events (DST on)',
            'Hotspots & Events by GMT DST OFF': 'Hotspots and events (DST off)',
            'Game Disabled Countries': 'Game disabled countries (Russia, Belarus)'}.get(name, name)
    return num, folder, name

def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s

def xesc(s):
    return html.escape(s, quote=False)

items = []
seen_hash = {}
used_slugs = set()

def add(path, folder, name_base, added, wpt_src_text=None, fixed_slug=None):
    raw = open(path, 'rb').read()
    text = raw.decode('utf-8-sig', errors='replace').replace('\r\n', '\n')
    num, _, region = clean_region(folder)
    h = hashlib.md5(raw).hexdigest()
    name = re.sub(r'\s*\(\d+\)\s*$', '', name_base).strip()
    name = name.replace('Arentina,', 'Argentina,')
    m = re.match(r'\[[^\]]*\]\s*(.*)', name)
    disp = name
    n = len(re.findall(r'<(?:wpt|rtept|trkpt)\b', text))
    slug = fixed_slug or slugify(('%s %s' % (region if num >= 12 else '', name)).strip())
    if not slug:
        slug = 'route-' + h[:8]
    base = slug
    k = 2
    while slug in used_slugs:
        slug = '%s-%d' % (base, k); k += 1
    used_slugs.add(slug)
    items.append(dict(num=num, region=region, name=disp, n=n, added=added, slug=slug, text=text, fixed=bool(fixed_slug)))

# zip routes
for folder in sorted(os.listdir(SRC)):
    p = os.path.join(SRC, folder)
    if not os.path.isdir(p) or folder.startswith('00.'):
        continue
    for f in sorted(os.listdir(p)):
        if f.lower().endswith('.gpx'):
            add(os.path.join(p, f), folder, f[:-4], ZIPDATE)

# our two routes (already in site/gpx with metadata)
ours = [('alameda-central-cdmx', 'Mexico, Mexico City - Alameda Central Loop (long)'),
        ('reforma-gengar-raids-cdmx', 'Mexico, Mexico City - Reforma Gengar Raids Loop (long)'),
        ('alameda-central-short-cdmx', 'Mexico, Mexico City - Alameda Central Short Loop'),
        ('reforma-gengar-raids-short-cdmx', 'Mexico, Mexico City - Reforma Gengar Raid Lap (short)')]
for slug, nm in ours:
    used_slugs.add(slug)
for slug, nm in ours:
    p = '%s/gpx/%s.gpx' % (SITE, slug)
    text = open(p, encoding='utf-8').read().replace('\r\n', '\n')
    n = len(re.findall(r'<wpt\b', text))
    items.append(dict(num=1, region='North America - Mexico', name=nm, n=n, added=TODAY, slug=slug, text=text, fixed=True, mine=True))

# write gpx files (zip ones), name metadata
for it in items:
    if it['fixed']:
        continue
    t = it['text']
    if '<metadata' not in t:
        t = re.sub(r'(<gpx\b[^>]*>)', lambda m: m.group(1) + '\n<metadata><name>%s</name></metadata>' % xesc(it['name']), t, 1)
    with open('%s/%s.gpx' % (OUT, it['slug']), 'w', encoding='utf-8', newline='\n') as f:
        f.write(t)

# manifest + index (index.py is the single index writer, also used by CI)
import json, subprocess, sys
routes = [dict(slug=it['slug'], name=it['name'], num=it['num'], region=it['region'], added=it['added'], n=it['n']) for it in items]
with open(SITE + '/routes.json', 'w', encoding='utf-8', newline='\n') as f:
    json.dump(routes, f, ensure_ascii=False, indent=0)
    f.write('\n')
subprocess.run([sys.executable, '-I', SITE + '/build/index.py', SITE], check=True)
