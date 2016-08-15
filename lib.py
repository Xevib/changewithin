''' Support functions for changewithin.py script.
'''
import time, json, requests, os, sys
import urllib
from lxml import etree
from ModestMaps.Geo import MercatorProjection
from ModestMaps.Geo import Location
from ModestMaps.Core import Coordinate
from tempfile import mkstemp

dir_path = os.path.dirname(os.path.abspath(__file__))


def get_state():
    r = requests.get('http://planet.openstreetmap.org/replication/day/state.txt')
    return r.text.split('\n')[1].split('=')[1]


def get_osc(stateurl=None):
    if not stateurl:
        state = get_state()

        # zero-pad state so it can be safely split.
        state = '000000000' + state
        path = '%s/%s/%s' % (state[-9:-6], state[-6:-3], state[-3:])
        stateurl = 'http://planet.openstreetmap.org/replication/day/%s.osc.gz' % path

    sys.stderr.write('downloading %s...\n' % stateurl)
    # prepare a local file to store changes
    handle, filename = mkstemp(prefix='change-', suffix='.osc.gz')
    os.close(handle)
    status = os.system('wget --quiet %s -O %s' % (stateurl, filename))

    if status:
        status = os.system('curl --silent %s -o %s' % (stateurl, filename))
    
    if status:
        raise Exception('Failure from both wget and curl')
    
    sys.stderr.write('extracting %s...\n' % filename)
    os.system('gunzip -f %s' % filename)

    # knock off the ".gz" suffix and return
    return filename[:-3]

# Returns -lon, -lat, +lon, +lat
#
#    +---[+lat]---+
#    |            |
# [-lon]       [+lon]
#    |            |
#    +---[-lat]-- +


def get_bbox(poly):
    box = [200, 200, -200, -200]
    for p in poly:
        if p[0] < box[0]: box[0] = p[0]
        if p[0] > box[2]: box[2] = p[0]
        if p[1] < box[1]: box[1] = p[1]
        if p[1] > box[3]: box[3] = p[1]
    return box


def point_in_box(x, y, box):
    return x > box[0] and x < box[2] and y > box[1] and y < box[3]


def point_in_poly(x, y, poly):
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def get_extent(gjson):
    extent = {}
    m = MercatorProjection(0)

    b = get_bbox(extract_coords(gjson))
    points = [[b[3], b[0]], [b[1], b[2]]]

    if (points[0][0] - points[1][0] == 0) or (points[1][1] - points[0][1] == 0):
        extent['lat'] = points[0][0]
        extent['lon'] = points[1][1]
        extent['zoom'] = 18
    else:
        i = float('inf')
         
        w = 800
        h = 600
         
        tl = [min(map(lambda x: x[0], points)), min(map(lambda x: x[1], points))]
        br = [max(map(lambda x: x[0], points)), max(map(lambda x: x[1], points))]
         
        c1 = m.locationCoordinate(Location(tl[0], tl[1]))
        c2 = m.locationCoordinate(Location(br[0], br[1]))
         
        while (abs(c1.column - c2.column) * 256.0) < w and (abs(c1.row - c2.row) * 256.0) < h:
            c1 = c1.zoomBy(1)
            c2 = c2.zoomBy(1)
         
        center = m.coordinateLocation(Coordinate(
            (c1.row + c2.row) / 2,
            (c1.column + c2.column) / 2,
            c1.zoom))
        
        extent['lat'] = center.lat
        extent['lon'] = center.lon
        if c1.zoom > 18:
            extent['zoom'] = 18
        else:
            extent['zoom'] = c1.zoom
        
    return extent


def has_building_tag(n):
    return n.find(".//tag[@k='building']") is not None


def get_address_tags(tags):
    addr_tags = []
    for t in tags:
        key = t.get('k')
        if key.split(':')[0] == 'addr':
            addr_tags.append(t.attrib)
    return addr_tags
    
def has_address_change(gid, addr, version, elem):
    url = 'http://api.openstreetmap.org/api/0.6/%s/%s/history' % (elem, gid)
    r = requests.get(url)
    if not r.text: return False
    e = etree.fromstring(r.text.encode('utf-8'))
    previous_elem = e.find(".//%s[@version='%s']" % (elem, (version - 1)))
    previous_addr = get_address_tags(previous_elem.findall(".//tag[@k]"))
    if len(addr) != len(previous_addr):
        return True
    else:
        for a in addr:
            if a not in previous_addr: return True
    return False

def load_changeset(changeset):
    changeset['wids'] = list(changeset['wids'])
    changeset['nids'] = changeset['nodes'].keys()
    changeset['addr_chg_nids'] = changeset['addr_chg_nd'].keys()
    changeset['addr_chg_way'] = list(changeset['addr_chg_way'])
    points = map(get_point, changeset['nodes'].values())
    polygons = map(get_polygon, changeset['wids'])
    gjson = geojson_feature_collection(points=points, polygons=polygons)
    extent = get_extent(gjson)
    url = 'http://api.openstreetmap.org/api/0.6/changeset/%s' % changeset['id']
    r = requests.get(url)
    if not r.text: return changeset
    t = etree.fromstring(r.text.encode('utf-8'))
    changeset['details'] = dict(t.find('.//changeset').attrib)
    comment = t.find(".//tag[@k='comment']")
    created_by = t.find(".//tag[@k='created_by']")
    if comment is not None: changeset['comment'] = comment.get('v')
    if created_by is not None: changeset['created_by'] = created_by.get('v')
    changeset['map_img'] = 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson(%s)/%s,%s,%s/600x400.png' % (urllib.quote(json.dumps(gjson)), extent['lon'], extent['lat'], extent['zoom'])
    if len(changeset['map_img']) > 2048:
        changeset['map_img'] = 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson(%s)/%s,%s,%s/600x400.png' % (urllib.quote(json.dumps(bbox_from_geojson(gjson))), extent['lon'], extent['lat'], extent['zoom'])
    changeset['map_link'] = 'http://www.openstreetmap.org/?lat=%s&lon=%s&zoom=%s&layers=M' % (extent['lat'], extent['lon'], extent['zoom'])
    changeset['addr_count'] = len(changeset['addr_chg_way']) + len(changeset['addr_chg_nids'])
    changeset['bldg_count'] = len(changeset['wids'])
    return changeset

def add_changeset(el, cid, changesets):
    if not changesets.get(cid, False):
        changesets[cid] = {
            'id': cid,
            'user': el.get('user'),
            'uid': el.get('uid'),
            'wids': set(),
            'nodes': {},
            'addr_chg_way': set(),
            'addr_chg_nd': {}
        }

def add_node(el, nid, nodes):
    if not nodes.get(nid, False):
        nodes[nid] = {
            'id': nid,
            'lat': float(el.get('lat')),
            'lon': float(el.get('lon'))
        }

def geojson_multi_point(coords):
    return {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "MultiPoint",
        "coordinates": coords
      }
    }

def geojson_polygon(coords):
    return {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "Polygon",
        "coordinates": coords
      }
    }

def extract_coords(gjson):
    coords = []
    for f in gjson['features']:
        if f['geometry']['type'] == 'Polygon':
            for c in f['geometry']['coordinates']:
                coords.extend(c)
        elif f['geometry']['type'] == 'MultiPoint':
            coords.extend(f['geometry']['coordinates'])
        elif f['type'] == 'Point':
            coords.append(f['geometry']['coordinates'])
    return coords

def bbox_from_geojson(gjson):
    b = get_bbox(extract_coords(gjson))
    return geojson_polygon([[[b[0], b[1]], [b[0], b[3]], [b[2], b[3]], [b[2], b[1]], [b[0], b[1]]]])

def get_polygon(wid):
    coords = []
    query = '''
        [out:xml][timeout:25];
        (
          way(%s);
        );
        out body;
        >;
        out skel qt;
    '''
    r = requests.post('http://overpass-api.de/api/interpreter', data=(query % wid))
    if not r.text: return coords
    e = etree.fromstring(r.text.encode('utf-8'))
    lookup = {}
    for n in e.findall(".//node"):
        lookup[n.get('id')] = [float(n.get('lon')), float(n.get('lat'))]
    for n in e.findall(".//nd"):
        if n.get('ref') in lookup:
            coords.append(lookup[n.get('ref')])
    return coords

def get_point(node):
    return [node["lon"], node["lat"]]

def geojson_feature_collection(points=[], polygons=[]):
    collection = {"type": "FeatureCollection", "features": []}
    if len(points):
        collection["features"].append(geojson_multi_point(points))
    for p in polygons:
        if len(p):
            collection["features"].append(geojson_polygon([p]))
    return collection
