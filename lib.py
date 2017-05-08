""" Support functions for changewithin.py script.
"""
import time
import json
import requests
import os
import sys
import re
import urllib
from lxml import etree
import osmapi

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
    Function to download the osc file

    :param stateurl: str with the url of the osc
    :return: None
    """

    if not stateurl:
        state = get_state()

        # zero-pad state so it can be safely split.
        state = '000000000' + state
        path = '{0}/{1}/{2}'.format(state[-9:-6], state[-6:-3], state[-3:])
        stateurl = 'http://planet.openstreetmap.org/replication/day/{0}.osc.gz'.format(path)

    sys.stderr.write('downloading {0}...\n'.format(stateurl))
    # prepare a local file to store changes
    handle, filename = mkstemp(prefix='change-', suffix='.osc.gz')
    os.close(handle)
    status = os.system('wget --quiet {0} -O {1}'.format(stateurl, filename))

    if status:
        status = os.system('curl --silent {0} -o {1}'.format(stateurl, filename))
    
    if status:
        raise Exception('Failure from both wget and curl')
    
    sys.stderr.write('extracting {0}...\n'.format(filename))
    os.system('gunzip -f {0}'.format(filename))

    # knock off the ".gz" suffix and return
    return filename[:-3]


def load_changeset(changeset):
    """
    Loads data from a changeset

    :param changeset: Changeset id
    :return: Changeset
    """

    changeset['wids'] = list(changeset['wids'])
    changeset['nids'] = changeset['nodes'].keys()
    total_count = 0
    for key in changeset.keys():
        if key[-3:] == '_nd':
            name = key[:-3]
            changeset[name + '_nids'] = changeset[key].keys()
            changeset[name + '_way'] = list(changeset[name + '_way'])
            changeset[name + '_count'] = len(changeset[name + '_way']) + len(changeset[name + '_nids'])
            total_count += changeset[name + '_count']
    #changeset['addr_chg_nids'] = changeset['addr_chg_nd'].keys()
    #changeset['addr_chg_way'] = list(changeset['addr_chg_way'])
    points = map(get_point, changeset['nodes'].values())
    polygons = map(get_polygon, changeset['wids'])
    gjson = geojson_feature_collection(points=points, polygons=polygons)
    extent = get_extent(gjson)
    url = 'http://api.openstreetmap.org/api/0.6/changeset/{0}'.format(changeset['id'])
    r = requests.get(url)
    if not r.text: return changeset
    t = etree.fromstring(r.text.encode('utf-8'))
    changeset['details'] = dict(t.find('.//changeset').attrib)
    comment = t.find(".//tag[@k='comment']")
    created_by = t.find(".//tag[@k='created_by']")
    if comment is not None: changeset['comment'] = comment.get('v')
    if created_by is not None: changeset['created_by'] = created_by.get('v')
    changeset['map_img'] = 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson({0})/{1},{2},{3}/600x400.png'.format(urllib.quote(json.dumps(gjson)), extent['lon'], extent['lat'], extent['zoom'])
    if len(changeset['map_img']) > 2048:
        changeset['map_img'] = 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson({0})/{1},{2},{3}/600x400.png'.format(urllib.quote(json.dumps(bbox_from_geojson(gjson))), extent['lon'], extent['lat'], extent['zoom'])
    changeset['map_link'] = 'http://www.openstreetmap.org/?lat={0}&lon={1}&zoom={2}&layers=M'.format(extent['lat'], extent['lon'], extent['zoom'])
    #changeset['addr_count'] = len(changeset['addr_chg_way']) + len(changeset['addr_chg_nids'])
    #changeset['bldg_count'] = len(changeset['wids'])
    changeset['total'] = total_count
    return changeset


def get_point(node):
    """
    Returns the longitude and latitude from a node

    :param node:
    :return: [lon,lat]
    """

    return [node["lon"], node["lat"]]
