""" Support functions for changewithin.py script.
"""
import time, json, requests, os, sys
import urllib
from lxml import etree
from ModestMaps.Geo import MercatorProjection
from ModestMaps.Geo import Location
from ModestMaps.Core import Coordinate
from tempfile import mkstemp

dir_path = os.path.dirname(os.path.abspath(__file__))


def get_state():
    """
    Downloads the state from OSM replication system

    :return: Actual state as a str
    """

    r = requests.get('http://planet.openstreetmap.org/replication/day/state.txt')
    return r.text.split('\n')[1].split('=')[1]


def get_osc(stateurl=None):
    """
    Function to downloat the osc file

    :param stateurl: str with the url of the osc
    :return: None
    """

    if not stateurl:
        state = get_state()

        # zero-pad state so it can be safely split.
        state = '000000000' + state
        path = '{}/{}/{}'.format(state[-9:-6], state[-6:-3], state[-3:])
        stateurl = 'http://planet.openstreetmap.org/replication/day/{}.osc.gz'.format(path)

    sys.stderr.write('downloading {}...\n'.format(stateurl))
    # prepare a local file to store changes
    handle, filename = mkstemp(prefix='change-', suffix='.osc.gz')
    os.close(handle)
    status = os.system('wget --quiet {} -O {}'.format(stateurl, filename))

    if status:
        status = os.system('curl --silent {} -o {}'.format(stateurl, filename))
    
    if status:
        raise Exception('Failure from both wget and curl')
    
    sys.stderr.write('extracting {}...\n'.format(filename))
    os.system('gunzip -f {}'.format(filename))

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
    """
    Returns the bbox  of the coordinates of a geometry

    :param poly:
    :return: Bounding box
    """

    box = [200, 200, -200, -200]
    for p in poly:
        if p[0] < box[0]: box[0] = p[0]
        if p[0] > box[2]: box[2] = p[0]
        if p[1] < box[1]: box[1] = p[1]
        if p[1] > box[3]: box[3] = p[1]
    return box


def point_in_box(x, y, box):
    """
    Checks if a point is inside a bounding box

    :param x: X coordinate
    :param y: Y coordinate
    :param box: Bounding box as a list
    :return: Boolean
    """

    return x > box[0] and x < box[2] and y > box[1] and y < box[3]


def point_in_poly(x, y, poly):
    """
    To check if a point is inside a polygon

    :param x: X coordiante
    :param y: Y coordinate
    :param poly: Polygon as a disc
    :return: Boolean
    """

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
    """
    Returns the extent of the geojson

    :param gjson: Geojson as a dict
    :return: bounding box extent as a list
    """

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
    """
    Checks if a change has a building tag

    :param n: lxml element
    :return: Boolean
    """

    return n.find(".//tag[@k='building']") is not None


def get_address_tags(tags):
    """
    Returns the addr tags

    :param tags: All tags
    :return: Addr tags
    """

    addr_tags = []
    for t in tags:
        key = t.get('k')
        if key.split(':')[0] == 'addr':
            addr_tags.append(t.attrib)
    return addr_tags


def has_address_change(gid, addr, version, elem):
    """
    Checks if the the address tags has chanes on the change

    :param gid: geometry id
    :param addr: Actual addr tags
    :param version: Version to check
    :param elem: Type of element
    :return: Boolean
    """

    url = 'http://api.openstreetmap.org/api/0.6/{}/{}/history'.format(elem, gid)
    r = requests.get(url)
    if not r.text: return False
    e = etree.fromstring(r.text.encode('utf-8'))
    previous_elem = e.find(".//{}[@version='{}']".format(elem, (version - 1)))
    previous_addr = get_address_tags(previous_elem.findall(".//tag[@k]"))
    if len(addr) != len(previous_addr):
        return True
    else:
        for a in addr:
            if a not in previous_addr:
                return True
    return False


def load_changeset(changeset):
    """
    Loads data from a changeset

    :param changeset: Changeset id
    :return: Changeset
    """

    changeset['wids'] = list(changeset['wids'])
    changeset['nids'] = changeset['nodes'].keys()
    changeset['addr_chg_nids'] = changeset['addr_chg_nd'].keys()
    changeset['addr_chg_way'] = list(changeset['addr_chg_way'])
    points = map(get_point, changeset['nodes'].values())
    polygons = map(get_polygon, changeset['wids'])
    gjson = geojson_feature_collection(points=points, polygons=polygons)
    extent = get_extent(gjson)
    url = 'http://api.openstreetmap.org/api/0.6/changeset/{}'.format(changeset['id'])
    r = requests.get(url)
    if not r.text: return changeset
    t = etree.fromstring(r.text.encode('utf-8'))
    changeset['details'] = dict(t.find('.//changeset').attrib)
    comment = t.find(".//tag[@k='comment']")
    created_by = t.find(".//tag[@k='created_by']")
    if comment is not None: changeset['comment'] = comment.get('v')
    if created_by is not None: changeset['created_by'] = created_by.get('v')
    changeset['map_img'] = 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson({})/{},{},{}/600x400.png'.format(urllib.quote(json.dumps(gjson)), extent['lon'], extent['lat'], extent['zoom'])
    if len(changeset['map_img']) > 2048:
        changeset['map_img'] = 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson({})/{},{},{}/600x400.png'.format(urllib.quote(json.dumps(bbox_from_geojson(gjson))), extent['lon'], extent['lat'], extent['zoom'])
    changeset['map_link'] = 'http://www.openstreetmap.org/?lat={}&lon={}&zoom={}&layers=M'.format(extent['lat'], extent['lon'], extent['zoom'])
    changeset['addr_count'] = len(changeset['addr_chg_way']) + len(changeset['addr_chg_nids'])
    changeset['bldg_count'] = len(changeset['wids'])
    return changeset


def add_changeset(el, cid, changesets):
    """
    Add a changeset on the list of rellevant changesets

    :param el:  Element
    :param cid: Changeset id
    :param changesets: list of changesets
    :return: None
    """
    
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
    """
    Adds node to the list of rellevant nodes

    :param el: Element
    :param nid: Node id
    :param nodes: List of nodes
    :return: None
    """

    if not nodes.get(nid, False):
        nodes[nid] = {
            'id': nid,
            'lat': float(el.get('lat')),
            'lon': float(el.get('lon'))
        }


def geojson_multi_point(coords):
    """
    Generates a multipoint geojson from coordinates

    :param coords: Coordinates
    :return: Geojson as a dict
    """

    return {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "MultiPoint",
            "coordinates": coords
        }
    }


def geojson_polygon(coords):
    """
    Generates a multipoint geojson from coordinates

    :param coords: Coordinates
    :return: Geojson as a dict
    """

    return {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "Polygon",
        "coordinates": coords
      }
    }


def extract_coords(gjson):
    """
    Extract the coordinates from a geojson
    :param gjson: geojson as a dict
    :return: Coordinates
    """

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
    """
    Returns the bbox of a geojson

    :param gjson: geojson as a dict
    :return: Bbox
    """

    b = get_bbox(extract_coords(gjson))
    return geojson_polygon([[[b[0], b[1]], [b[0], b[3]], [b[2], b[3]], [b[2], b[1]], [b[0], b[1]]]])


def get_polygon(wid):
    """
    Get a polygon of a way

    :param wid: Way id
    :return: Way polygon
    """

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
    """
    Returns the longitude and latitude from a node

    :param node:
    :return: [lon,lat]
    """

    return [node["lon"], node["lat"]]


def geojson_feature_collection(points=None, polygons=None):
    """
    Generates a geojson feature collection from points and polygons

    :param points: List of points
    :param polygons: List of polygons
    :return: Geojson feature collection as a dict
    """

    collection = {"type": "FeatureCollection", "features": []}
    if len(points):
        collection["features"].append(geojson_multi_point(points))
    for p in polygons:
        if len(p):
            collection["features"].append(geojson_polygon([p]))
    return collection
