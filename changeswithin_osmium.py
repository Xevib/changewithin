import argparse
import os
import re

from configobj import ConfigObj
import osmium
import requests
import json
import gettext
from jinja2 import Environment
from osconf import config_from_environment
import osmapi

#Env vars:
#AREA_GEOJSON
#MAILGUN_DOMAIN
#MAILGUN_API_KEY
#EMAIL_RECIPIENTS
#EMAIL_LANGUAGE
#CONFIG


class ChangeHandler(osmium.SimpleHandler):
    """
    Class that handles the changes
    """

    def __init__(self):
        """
        Class constructor
        """
        osmium.SimpleHandler.__init__(self)
        self.num_nodes = 0
        self.num_ways = 0
        self.num_rel = 0
        self.tags = {}
        self.north = 0
        self.east = 0
        self.south = 0
        self.west = 0
        self.changeset = {}


    def location_in_bbox(self, location):
        """
        Checks if the location is in the bounding box
        
        :param location: Location
        :return: Boolean
        """

        return self.north > location.lat > self.south and self.east > location.lon > self.west

    def way_in_bbox(self, nodes):
        """
        Checks if the way is in the bounding box
        :param nodes: Nodes of the way
        :return: Booelan
        """

        inside = False
        x = 0
        while not inside and x < len(nodes):
            if nodes[x].location.valid():
                inside = self.location_in_bbox(nodes[x].location)
            x += 1
        return inside

    def has_tag_changed(self, gid, old_tags, watch_tags, version, elem):
        """
        Checks if tags has changed on the changeset

        :param gid: Geometry id
        :param old_tags: Old tags
        :param watch_tags: Tags to check
        :param version: version to check
        :param elem: Type of element
        :return: Boolean
        """

        previous_elem = {}
        osm_api = osmapi.OsmApi()
        if elem == 'node':
            previous_elem = osm_api.NodeHistory(gid)[version - 1]
        elif elem == 'way':
            previous_elem = osm_api.WayHistory(gid)[version - 1]
        elif elem == 'relation':
            previous_elem = osm_api.RelationHistory(gid)[version - 1]
        if previous_elem:
            previous_tags = previous_elem['tag']
            out_tags = {}
            for key, value in previous_tags.items():
                if re.match(watch_tags, key):
                    out_tags[key] = value
            previous_tags = out_tags

            return previous_tags != old_tags
        else:
            return False

    def has_tag(self, element, key_re, value_re):
        """
        Checks if the element have the key,value
        
        :param element: Element to check
        :param key_re: Compiled re expression of key 
        :param value_re: Compiled re expression of value
        :return: boolean
        """
        for tag in element:
            key = tag.k
            value = tag.v
            if key_re.match(key) and value_re.match(value):
                    return True
        return False

    def set_tags(self, name, key, value, element_types):
        """
        Sets the tags to wathc on the handler
        :param name: Name of the tags
        :param key: Key value expression
        :param value: Value expression
        :param element_types: List of element types
        :return: None
        """
        self.tags[name] = {}
        self.tags[name]["key_re"] = re.compile(key)
        self.tags[name]["value_re"] = re.compile(value)
        self.tags[name]["types"] = element_types

    def set_bbox(self, north, east, south, west):
        """
        Sets the bounding box to check
        
        :param north: North of bbox
        :param east: East of the bbox
        :param south: South of the bbox
        :param west: West of the bbox
        :return: None
        """
        self.north = float(north)
        self.east = float(east)
        self.south = float(south)
        self.west = float(west)

    def node(self, node):
        """
        Attends the nodes in the file
        
        :param node: Node to check 
        :return: None
        """

        if self.location_in_bbox(node.location):
            for tag_name in self.tags.keys():
                key_re = self.tags[tag_name]["key_re"]
                value_re = self.tags[tag_name]["value_re"]
                if self.has_tag(node.tags, key_re, value_re):
                    if node.deleted:
                        add_node = True
                    elif node.version == 1:
                        add_node = True
                    else:
                        add_node = self.has_tag_changed(
                            node.id, node.tags, key_re, node.version, "node")
                    if add_node:
                        if self.changeset:
                            self.changeset = {
                                "changeset": node.changeset,
                                "user": node.user,
                                "uid": node.uid,
                                "nids": [],
                                "wids": []
                            }
                        else:
                            self.changeset["nids"].append(node.id)
                    print("node:changeset a dins:{}".format(node.changeset))
        self.num_nodes += 1

    def way(self, way):
        """
        Attends the ways in the file
        
        :param way: Way to check
        :return: None
        """

        if self.way_in_bbox(way.nodes):
            for tag_name in self.tags.keys():
                key_re = self.tags[tag_name]["key_re"]
                value_re = self.tags[tag_name]["value_re"]
                if self.has_tag(way.tags, key_re, value_re):
                    if way.deleted:
                        add_way = True
                    elif way.version == 1:
                        add_way = True
                    else:
                        add_way = self.has_tag_changed(
                            way.id, way.tags, key_re, way.version, "way")
                    if add_way:
                        if self.changeset:
                            self.changeset["wids"].append(way.id)
                        else:
                            self.changeset = {
                                "changeset": way.changeset,
                                "user": way.user,
                                "uid": way.uid,
                                "nids": [],
                                "wids": []
                            }
                    print("way:changeset a dins:{}".format(way.changeset))
        self.num_ways += 1

    def relation(self, r):
        #print 'rel:{}'.format(self.num_rel)
        #for member in r.members:
        #    print member
        self.num_rel += 1


class ChangeWithin(object):
    """
    Class that process the OSC files
    """
    def __init__(self):
        """
        Initiliazes the class
        """
        self.conf = {}
        self.env_vars = {}
        self.handler = ChangeHandler()

    def load_config(self, config=None):
        """
        Loads the configuration from the file
        :config_file: Configuration as a dict
        :return: None
        """

        self.env_vars = config_from_environment('bard', ['config'])

        self.conf = ConfigObj(self.env_vars["config"])

        self.handler.set_bbox(*self.conf["area"]["bbox"])
        for name in self.conf["tags"]:
            value, key = self.conf["tags"][name]["tags"].split("=")
            types = self.conf["tags"][name]["tags"].split(",")
            self.handler.set_tags(name, key, value, types)
        print(self.conf)

    def process_file(self, filename):
        """
        
        :param filename: 
        :return: 
        """
        self.handler.apply_file(filename, osmium.osm.osm_entity_bits.CHANGESET)


if __name__ == '__main__':
    c = ChangeWithin()
    c.load_config()
    c.process_file("662.osc")

    #h = CounterHandler()
    #h.apply_file("662.osc", osmium.osm.osm_entity_bits.CHANGESET)

    #print("Number of nodes: %d" % h.num_nodes)
    #print("Number of ways: %d" % h.num_ways)
    #print("Number of rel: %d" % h.num_rel)

    {'comment': '#maproulette Open_Rings_(Europe)',
     'all_count': 0,
     'uid': '2973031',
     'all_way': [],
     'map_img': 'http://api.tiles.mapbox.com/v3/lxbarth.map-lxoorpwz/geojson(%7B%22type%22%3A%20%22FeatureCollection%22%2C%20%22features%22%3A%20%5B%7B%22geometry%22%3A%20%7B%22type%22%3A%20%22MultiPoint%22%2C%20%22coordinates%22%3A%20%5B%5B2.8103142%2C%2041.9846208%5D%5D%7D%2C%20%22type%22%3A%20%22Feature%22%2C%20%22properties%22%3A%20%7B%7D%7D%2C%20%7B%22geometry%22%3A%20%7B%22type%22%3A%20%22Polygon%22%2C%20%22coordinates%22%3A%20%5B%5B%5B2.8111286%2C%2041.980141%5D%2C%20%5B2.811019%2C%2041.9808931%5D%2C%20%5B2.8109375%2C%2041.9814244%5D%2C%20%5B2.8108287%2C%2041.9818106%5D%2C%20%5B2.8104375%2C%2041.9831589%5D%2C%20%5B2.8104067%2C%2041.983415%5D%2C%20%5B2.8103113%2C%2041.9844798%5D%2C%20%5B2.8103142%2C%2041.9846208%5D%5D%5D%7D%2C%20%22type%22%3A%20%22Feature%22%2C%20%22properties%22%3A%20%7B%7D%7D%5D%7D)/2.81071995,41.9823809394,15/600x400.png',
     'all_nids': [],
     'all_nd': {},
     'map_link': 'http://www.openstreetmap.org/?lat=41.9823809394&lon=2.81071995&zoom=15&layers=M',
     'created_by': 'JOSM/1.5 (11639 de)',
     'nids': ['368023616'],
     'user': 'edtha',
     'wids': [54740188],
     'nodes': {
         '368023616': {
             'lat': 41.9846208,
             'lon': 2.8103142,
             'id': '368023616'
         }
     },
     'total': 0,
     'id': '47330980',
     'details': {
         'uid': '2973031',
         'min_lat': '41.9432239',
         'created_at': '2017-03-31T16:07:01Z',
         'max_lat': '41.9912105',
         'max_lon': '2.8359893',
         'comments_count': '0',
         'user': 'edtha',
         'min_lon': '2.7564161',
         'closed_at': '2017-03-31T16:07:08Z',
         'open': 'false',
         'id': '47330980'}
     }

