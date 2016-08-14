import requests
import json
import os
import sys
from configparser import ConfigParser
from lxml import etree
from datetime import datetime
import argparse
from jinja2 import Environment
import gettext

from lib import get_bbox, get_osc, point_in_box, point_in_poly, has_building_tag
from lib import get_address_tags, has_address_change, load_changeset
from lib import add_changeset, add_node

dir_path = os.path.dirname(os.path.abspath(__file__))


parser = argparse.ArgumentParser(description='Generates an email digest of OpenStreetMap building and address changes.')
parser.add_argument('--oscurl', type=str,
                   help='OSC file URL. For example: http://planet.osm.org/replication/hour/000/021/475.osc.gz. If none given, defaults to latest available day.')
parser.add_argument('--config', type=str,
                   help='Config file')
args = parser.parse_args()

#
# Configure for use. See config.ini for details.
#
print(args.config)
config = ConfigParser()
if args.config:
    config.read(os.path.join(dir_path, args.config))
else:
    config.read(os.path.join(dir_path, 'config.ini'))
languages = ['en']
if config.get('email', 'language'):
    languages += config.get('email', 'language') + languages
jinja_env = Environment(extensions=['jinja2.ext.i18n'])
lang = gettext.translation('messages', localedir='./locales/', languages=languages)
lang.install()
jinja_env.install_gettext_translations(gettext.translation('messages', localedir='./locales/', languages=languages))


def get_template(template_name):
    url = os.path.join('templates', template_name)
    with open(url) as f:
        template_text = f.read()
    return jinja_env.from_string(template_text)
#
# Set up arguments and parse them.
#
text_tmpl = get_template('text_template.txt')
html_tmpl = get_template('html_template.html')


#
# Environment variables override config file.
#
if 'AREA_GEOJSON' in os.environ:
    config.set('area', 'geojson', os.environ['AREA_GEOJSON'])

if 'MAILGUN_DOMAIN' in os.environ:
    config.set('mailgun', 'domain', os.environ['MAILGUN_DOMAIN'])

if 'MAILGUN_API_KEY' in os.environ:
    config.set('mailgun', 'api_key', os.environ['MAILGUN_API_KEY'])

if 'EMAIL_RECIPIENTS' in os.environ:
    config.set('email', 'recipients', os.environ['EMAIL_RECIPIENTS'])

if 'LANGUAGE' in os.environ:
    config.set('email', 'language', os.environ['LANGUAGE'])
#
# Get started with the area of interest (AOI).
#

aoi_href = config.get('area', 'geojson')
aoi_file = os.path.join(dir_path, aoi_href)

if os.path.exists(aoi_file):
    # normal file, available locally
    aoi = json.load(open(aoi_file))

else:
    # possible remote file, try to request it
    aoi = requests.get(aoi_href).json()

aoi_poly = aoi['features'][0]['geometry']['coordinates'][0]
aoi_box = get_bbox(aoi_poly)
sys.stderr.write('getting state\n')
osc_file = get_osc(args.oscurl)

sys.stderr.write('reading file\n')

nodes = {}
changesets = {}
stats = {}
stats['buildings'] = 0
stats['addresses'] = 0

sys.stderr.write('finding points\n')

# Find nodes that fall within specified area
context = iter(etree.iterparse(osc_file, events=('start', 'end')))
event, root = context.next()
for event, n in context:
    if event == 'start':
        if n.tag == 'node':
            lon = float(n.get('lon', 0))
            lat = float(n.get('lat', 0))
            if point_in_box(lon, lat, aoi_box) and point_in_poly(lon, lat, aoi_poly):
                cid = n.get('changeset')
                nid = n.get('id', -1)
                add_node(n, nid, nodes)
                ntags = n.findall(".//tag[@k]")
                addr_tags = get_address_tags(ntags)
                version = int(n.get('version'))
                
                # Capture address changes
                if version != 1:
                    if has_address_change(nid, addr_tags, version, 'node'):
                        add_changeset(n, cid, changesets)
                        changesets[cid]['nodes'][nid] = nodes[nid]
                        changesets[cid]['addr_chg_nd'][nid] = nodes[nid]
                        stats['addresses'] += 1
                elif len(addr_tags):
                    add_changeset(n, cid, changesets)
                    changesets[cid]['nodes'][nid] = nodes[nid]
                    changesets[cid]['addr_chg_nd'][nid] = nodes[nid]
                    stats['addresses'] += 1
    n.clear()
    root.clear()

sys.stderr.write('finding changesets\n')

# Find ways that contain nodes that were previously determined to fall within specified area
context = iter(etree.iterparse(osc_file, events=('start', 'end')))
event, root = context.next()
for event, w in context:
    if event == 'start':
        if w.tag == 'way':
            relevant = False
            cid = w.get('changeset')
            wid = w.get('id', -1)
            
            # Only if the way has 'building' tag
            if has_building_tag(w):
                for nd in w.iterfind('./nd'):
                    if nd.get('ref', -2) in nodes.keys():
                        relevant = True
                        add_changeset(w, cid, changesets)
                        nid = nd.get('ref', -2)
                        changesets[cid]['nodes'][nid] = nodes[nid]
                        changesets[cid]['wids'].add(wid)
            if relevant:
                stats['buildings'] += 1
                wtags = w.findall(".//tag[@k]")
                version = int(w.get('version'))
                addr_tags = get_address_tags(wtags)
                
                # Capture address changes
                if version != 1:
                    if has_address_change(wid, addr_tags, version, 'way'):
                        changesets[cid]['addr_chg_way'].add(wid)
                        stats['addresses'] += 1
                elif len(addr_tags):
                    changesets[cid]['addr_chg_way'].add(wid)
                    stats['addresses'] += 1
    w.clear()
    root.clear()

changesets = map(load_changeset, changesets.values())

stats['total'] = len(changesets)

if len(changesets) > 1000:
    changesets = changesets[:999]
    stats['limit_exceed'] = 'Note: For performance reasons only the first 1000 changesets are displayed.'
    
now = datetime.now()


template_data = {
    'changesets': changesets,
    'stats': stats,
    'date': now.strftime("%B %d, %Y")
}
html_version = html_tmpl.render(**template_data)
text_version = text_tmpl.render(**template_data)

if config.has_option('mailgun', 'domain') and config.has_option('mailgun', 'api_key'):
    resp = requests.post(('https://api.mailgun.net/v2/%s/messages' % config.get('mailgun', 'domain')),
        auth=('api', config.get('mailgun', 'api_key')),
        data={
                'from': 'Change Within <changewithin@%s>' % config.get('mailgun', 'domain'),
                'to': config.get('email', 'recipients').split(),
                'subject': 'OSM building and address changes %s' % now.strftime("%B %d, %Y"),
                'text': text_version,
                "html": html_version,
        })

file_name = 'osm_change_report_%s.html' % now.strftime("%m-%d-%y")
f_out = open(file_name, 'w')
f_out.write(html_version.encode('utf-8'))
f_out.close()
print('Wrote {}'.format(file_name))

os.unlink(osc_file)
