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
ours = [('alameda-central-cdmx', 'Mexico, Mexico City - Alameda Central'),
        ('reforma-gengar-raids-cdmx', 'Mexico, Mexico City - Reforma Gengar Raids')]
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

# region order
regions = {}
for it in items:
    regions.setdefault((it['num'], it['region']), 0)
    regions[(it['num'], it['region'])] += 1
# merge ordering: use sort key (num, name)
rorder = sorted(regions)
ridx = {r[1]: i for i, r in enumerate(rorder)}

def area_of(name):
    nm = re.sub(r'^\[[^\]]*\]\s*', '', name)
    return nm.split(',')[0].strip() if ',' in nm else ''

items.sort(key=lambda it: (ridx[it['region']], area_of(it['name']).lower(), it['name'].lower()))

def a(s): return html.escape(s, quote=True)

rows = []
for it in items:
    rows.append('<li data-r="%d" data-a="%s" data-d="%s" data-w="%d"><a href="/gpx/%s.gpx">%s</a> <span class="w">%d pts</span></li>' % (
        ridx[it['region']], a(area_of(it['name'])), it['added'], it['n'], it['slug'], xesc(it['name']), it['n']))

regjs = ','.join('"%s"' % r[1].replace('"', '\\"') for r in rorder)
page = open(SITE + '/build/template.html', encoding='utf-8').read()
page = page.replace('{{COUNT}}', str(len(items))).replace('{{REGIONS}}', regjs).replace('{{ROWS}}', '\n'.join(rows))
open(SITE + '/index.html', 'w', encoding='utf-8', newline='\n').write(page)
print(len(items), 'routes', len(rorder), 'regions')
