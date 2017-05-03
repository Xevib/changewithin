import os
import re

from configobj import ConfigObj
import osmium
import requests
import gettext
from jinja2 import Environment
from osconf import config_from_environment
import osmapi
from lib import get_osc


# Env vars:
# AREA_GEOJSON
# MAILGUN_DOMAIN
# MAILGUN_API_KEY
# EMAIL_RECIPIENTS
# EMAIL_LANGUAGE
# CONFIG


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
        self.stats = {}

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
                        if tag_name in self.stats:
                            self.stats[tag_name].append(node.changeset)
                        else:
                            self.stats[tag_name] = [node.changeset]
                        if node.changeset not in self.changeset:
                            self.changeset[node.changeset] = {
                                "changeset": node.changeset,
                                "user": node.user,
                                "uid": node.uid,
                                "nids": [],
                                "wids": []
                            }
                        else:
                            self.changeset[node.changeset]["nids"].append(
                                node.id)
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
                        if tag_name in self.stats:
                            self.stats[tag_name].append(way.changeset)
                        else:
                            self.stats[tag_name] = [way.changeset]
                        if way.changeset in self.changeset:
                            self.changeset[way.changeset]["wids"].append(way.id)
                        else:
                            self.changeset[way.changeset] = {
                                "changeset": way.changeset,
                                "user": way.user,
                                "uid": way.uid,
                                "nids": [],
                                "wids": [way.id]
                            }
                    print("way:changeset a dins:{}".format(way.changeset))
        self.num_ways += 1

    def relation(self, r):
        # print 'rel:{}'.format(self.num_rel)
        # for member in r.members:
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
        self.osc_file = None
        self.changesets = []
        self.stats = {}

        self.jinja_env = Environment(extensions=['jinja2.ext.i18n'])
        self.text_tmpl = self.get_template('text_template.txt')
        self.html_tmpl = self.get_template('html_template.html')

    def get_template(self, template_name):
        """
        Returns the template

        :param template_name: Template name as a string
        :return: Template
        """

        url = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           'templates', template_name)
        with open(url) as f:
            template_text = f.read()
        return self.jinja_env.from_string(template_text)

    def load_config(self, config=None):
        """
        Loads the configuration from the file
        :config_file: Configuration as a dict
        :return: None
        """
        if not config:
            self.env_vars = config_from_environment('bard', ['config'])
            self.conf = ConfigObj(self.env_vars["config"])
        else:
            self.conf = config

        languages = ['en']
        if 'email' in self.conf and 'language' in self.conf['email']:
            languages = [self.conf['email']['language']].extend(languages)
        dir_path = os.path.dirname(os.path.realpath(__file__))
        url_locales = os.path.join(dir_path, 'locales')
        lang = gettext.translation(
            'messages',
            localedir=url_locales,
            languages=languages)
        lang.install()
        translations = gettext.translation(
            'messages',
            localedir=url_locales,
            languages=languages)
        self.jinja_env.install_gettext_translations(translations)

        self.handler.set_bbox(*self.conf["area"]["bbox"])
        for name in self.conf["tags"]:
            value, key = self.conf["tags"][name]["tags"].split("=")
            types = self.conf["tags"][name]["tags"].split(",")
            self.stats["name"] = 0
            self.handler.set_tags(name, key, value, types)

    def process_file(self, filename=None):
        """

        :param filename: 
        :return: 
        """
        if filename is None:
            self.osc_file = get_osc()
            self.handler.apply_file(self.osc_file,
                                    osmium.osm.osm_entity_bits.CHANGESET)
        else:
            self.handler.apply_file(filename,
                                    osmium.osm.osm_entity_bits.CHANGESET)

        self.changesets = self.handler.changeset
        self.stats = self.handler.stats
        self.stats["total"] = len(self.changesets)

    def report(self):
        """
        Generates the report and sends it

        :return: None
        """
        from datetime import datetime
        print ("self.changesets:{}".format(self.changesets))
        if len(self.changesets) > 1000:
            self.changesets = self.changesets[:999]
            self.stats[
                'limit_exceed'] = 'Note: For performance reasons only the first 1000 changesets are displayed.'

        now = datetime.now()

        for state in self.stats:
            if state != "total":
                self.stats[state] = len(set(self.stats[state]))

        template_data = {
            'changesets': self.changesets,
            'stats': self.stats,
            'date': now.strftime("%B %d, %Y"),
            'tags': self.conf['tags'].keys()
        }
        html_version = self.html_tmpl.render(**template_data)
        text_version = self.text_tmpl.render(**template_data)

        if 'domain' in self.conf['mailgun'] and 'api_key' in self.conf[
            'mailgun']:
            if "api_url" in self.conf["mailgun"]:
                url = self.conf["mailgun"]["api_url"]
            else:
                url = 'https://api.mailgun.net/v3/{0}/messages'.format(
                    self.conf['mailgun']['domain'])
            resp = requests.post(
                url,
                auth=("api", self.conf['mailgun']['api_key']),
                data={"from": "OSM Changes <mailgun@{}>".format(
                    self.conf['mailgun']['domain']),
                      "to": self.conf["email"]["recipients"].split(),
                      "subject": 'OSM building and address changes {0}'.format(
                          now.strftime("%B %d, %Y")),
                      "text": text_version,
                      "html": html_version})
            print("response:{}".format(resp.status_code))
            print("mailgun response:{}".format(resp.content))

        file_name = 'osm_change_report_{0}.html'.format(
            now.strftime('%m-%d-%y'))
        f_out = open(file_name, 'w')
        f_out.write(html_version.encode('utf-8'))
        f_out.close()
        print('Wrote {0}'.format(file_name))
        # os.unlink(self.osc_file)


if __name__ == '__main__':
    c = ChangeWithin()
    c.load_config()
    c.process_file()
    c.report()
