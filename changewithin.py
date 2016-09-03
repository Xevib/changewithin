import requests
import json
import os
import sys
from configobj import ConfigObj
from lxml import etree
from datetime import datetime
import argparse
from jinja2 import Environment
import gettext
import osmapi
import re
from multiprocessing import Process, Queue, current_process

from lib import get_bbox, get_osc, point_in_box, point_in_poly, load_changeset
from lib import has_tag


def has_tag_changed(gid, old_tags, watch_tags, version, elem):
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


def get_tags(element, keys):
    """
    Method that returns the tags of a lxml element

    :param element: Lxml element
    :param keys: Keys to select
    :return: Dict with the tag-value
    """
    ntags = element.findall(".//tag[@k]")
    re_keys = re.compile(keys)
    tags = {}
    for element in ntags:
        if re.match(re_keys, element.attrib['k']):
            tags[element.attrib['k']] = element.attrib['v']
    return tags


def proces_ways( work_queue, done_queue, interest_tags, nodes, config, checkhistoy=True):
    """
    Process the ways of the OSC file

    :return: None
    """
    try:
        sys.stderr.write('finding ways proc {}\n'.format(current_process().name))
        # Find ways that contain nodes that were previously determined to fall within specified area

        for str_way in iter(work_queue.get, 'STOP'):
            if str_way == 'STOP':
                print('proc:{} ha trobat stop'.format(current_process().name))
                return True
            changeset = {}
            w = etree.fromstring(str_way)
            cid = w.get('changeset')
            wid = int(w.get('id', -1))
            version = int(w.get('version'))
            modified_node = False
            for int_tag in interest_tags['way']:
                old_tags = get_tags(w, int_tag['k'])
                # Only if the way has 'building' tag

                if has_tag(w, int_tag['k']):
                    for nd in w.iterfind('./nd'):
                        if nd.get('ref', -2) in nodes.keys():
                            changeset[cid] = {
                                'id': cid,
                                'user': w.get('user'),
                                'uid': w.get('uid'),
                                'wids': set(),
                                'nodes': {}
                            }
                            for tag in config['tags'].keys():
                                changeset[cid][tag + '_way'] = set()
                                changeset[cid][tag + '_nd'] = {}
                            nid = nd.get('ref', -2)
                            changeset[cid]['nodes'][nid] = nodes[nid]
                            changeset[cid]['wids'].add(wid)
                            #self.stats[int_tag['name']] += 1
                            modified_node = True

                    if modified_node:
                        #self.stats[int_tag['name']] += 1
                        if checkhistoy and version > 1:
                            if has_tag_changed(wid, old_tags, int_tag['k'], version, 'way'):
                                if cid not in changeset:
                                    changeset[cid] = {
                                        'id': cid,
                                        'user': w.get('user'),
                                        'uid': w.get('uid'),
                                        'wids': set(),
                                        'nodes': {}
                                    }
                                    for tag in config['tags'].keys():
                                        changeset[cid][tag + '_way'] = set()
                                        changeset[cid][tag + '_nd'] = {}
                                changeset[cid][int_tag['name'] + '_way'].add(wid)
                                #self.stats[int_tag['name']] += 1
                        else:
                            if cid not in changeset:
                                changeset[cid] = {
                                    'id': cid,
                                    'user': w.get('user'),
                                    'uid': w.get('uid'),
                                    'wids': set(),
                                    'nodes': {}
                                }
                                for tag in config['tags'].keys():
                                    changeset[cid][tag + '_way'] = set()
                                    changeset[cid][tag + '_nd'] = {}
                            changeset[cid][int_tag['name'] + '_way'].add(wid)
                            #self.stats[int_tag['name']] += 1
                if changeset:
                    done_queue.put(changeset)
        print('proc:{} ha acabat'.format(current_process().name))
    except Exception, e:
        print "%s failed on with: %s" % (current_process().name, e.message)
        done_queue.put(
            "%s failed on with: %s" % (current_process().name, e.message))
    return True



class ChangesWithin(object):
    """
    Function that manages te changeswithin program
    """

    def __init__(self):
        """
        Initiliazes the class
        """

        self.jinja_env = Environment(extensions=['jinja2.ext.i18n'])
        self.nodes = {}
        self.changesets = {}
        self.stats = {}
        self.osc_file = ''
        self.text_tmpl = ''
        self.html_tmpl = ''
        self.aoi_box = []
        self.aoi_poly = {}
        self.config = ConfigObj()
        self.osc_url = ''
        self.tree = etree.ElementTree()
        self.interest_tags = {
            'node': [],
            'way': []
        }
        self.osm_api = osmapi.OsmApi()
        self.stats = {}

    def get_template(self, template_name):
        """
        Returns the template

        :param template_name: Template name as a string
        :return: Template
        """

        url = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', template_name)
        with open(url) as f:
            template_text = f.read()
        return self.jinja_env.from_string(template_text)

    def load_config(self):
        """
        Loads the configuration from os env and config file

        :return: None
        """

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
        if 'CONFIG' in os.environ:
            args.config = os.environ['CONFIG']

        if args.config:
            self.config = ConfigObj(os.path.join(dir_path, args.config))
        else:
            self.config = ConfigObj(os.path.join(dir_path, 'config.ini'))
        languages = ['en']
        if 'language' in self.config['email']:
            languages = [self.config['email']['language']].extend(languages)

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

        #
        # Set up arguments and parse them.
        #
        self.text_tmpl = self.get_template('text_template.txt')
        self.html_tmpl = self.get_template('html_template.html')
        #
        # Environment variables override config file.
        #
        if 'AREA_GEOJSON' in os.environ:
            self.config['area']['geojson'] = os.environ['AREA_GEOJSON']

        if 'MAILGUN_DOMAIN' in os.environ:
            self.config['mailgun']['domain'] = os.environ['MAILGUN_DOMAIN']

        if 'MAILGUN_API_KEY' in os.environ:
            self.config['mailgun']['api_key'] = os.environ['MAILGUN_API_KEY']

        if 'EMAIL_RECIPIENTS' in os.environ:
            self.config['email']['recipients'] = os.environ['EMAIL_RECIPIENTS']

        if 'EMAIL_LANGUAGE' in os.environ:
            self.config['email']['language'] = os.environ['EMAIL_LANGUAGE']


        #
        # Get started with the area of interest (AOI).
        #

        aoi_href = self.config['area']['geojson']
        aoi_file = os.path.join(dir_path, aoi_href)

        if os.path.exists(aoi_file):
            # normal file, available locally
            aoi = json.load(open(aoi_file))

        else:
            # possible remote file, try to request it
            aoi = requests.get(aoi_href).json()

        self.aoi_poly = aoi['features'][0]['geometry']['coordinates'][0]
        self.aoi_box = get_bbox(self.aoi_poly)
        self.osc_url = args.oscurl

        for tag in self.config.get('tags', {}):
            conf_tag = self.config['tags'][tag]['tags'].split('=')
            watch_tag = {'k': conf_tag[0], 'v': conf_tag[1], 'name': tag}
            self.stats[tag] = 0
            if 'node' in self.config['tags'][tag]['type'].split(','):
                self.interest_tags['node'].append(watch_tag)

            if 'way' in self.config['tags'][tag]['type'].split(','):
                self.interest_tags['way'].append(watch_tag)

    def get_config(self):
        """
        Returns the config of the class
        :return: ConfigParser
        """

        return self.config

    def load_file(self):
        """
        Loads the OSC file

        :return: None
        """

        sys.stderr.write('getting state\n')
        self.osc_file = get_osc(self.osc_url)
        sys.stderr.write('reading file\n')
        self.tree = etree.parse(self.osc_file)

    def _parallel_process(self, function, elements, **kwargs):
        """
        Method that parallelizes a function over a list of elements

        :param function: Method to parallelize
        :param elements: List of elements
        :return: None
        """

        workers = 1
        work_queue = Queue()
        done_queue = Queue()
        processes = []
        #Entre 6500 i 6575
        for element in elements:
            work_queue.put(etree.tostring(element))
        del elements
        kwargs['work_queue'] = work_queue
        kwargs['done_queue'] = done_queue
        for w in range(workers):
            p = Process(target=function, kwargs=kwargs)
            p.start()
            processes.append(p)
            work_queue.put('STOP')
        print 'abans de join'
        for p in processes:
            p.join()
            print 'passat join {}'.format(p)
        print('vies procesades')
        done_queue.put('STOP')

        for changes in iter(done_queue.get, 'STOP'):
            self.changesets.update(changes)

    def proces_data(self):
        """
        Proces the whole OSC file

        :return: None
        """
        sys.stderr.write('finding points\n')

        # Find nodes that fall within specified area
        self.proces_nodes()

        elements = self.tree.xpath('//modify/way')
        print 'modificats:{}'.format(len(elements))
        #elements = self.tree.xpath('//way')
        #print 'tots:{}'.format(len(elements))
        self._parallel_process(proces_ways, elements, interest_tags=self.interest_tags, nodes=self.nodes, config=self.config, checkhistoy=True)
        self.changesets = map(load_changeset, self.changesets.values())
        self.stats['total'] = len(self.changesets)

    def proces_nodes(self):
        """
        Proces the nodes

        :return: None
        """
        # Find nodes that fall within specified area
        #context = iter(etree.iterparse(self.osc_file, events=('start', 'end')))

        elements = self.tree.xpath('//node')
        for n in elements:
            lon = float(n.get('lon', 0))
            lat = float(n.get('lat', 0))
            if point_in_box(lon, lat, self.aoi_box) and point_in_poly(lon, lat, self.aoi_poly):
                cid = n.get('changeset')
                nid = n.get('id', -1)
                self._add_node(n, nid)
                version = int(n.get('version'))
                for int_tag in self.interest_tags['node']:
                    if has_tag(n, int_tag['k'], int_tag['v']):
                        old_tags = self._get_tags(n, int_tag['k'])

                        # Capture address changes
                        if version != 1:
                            if self._has_tag_changed(nid, old_tags, int_tag['k'], version, 'node'):
                                self._add_changeset(n, cid)
                                self.changesets[cid]['nodes'][nid] = self.nodes[nid]
                                self.changesets[cid][int_tag['name'] + '_nd'][nid] = self.nodes[nid]
                                self.stats[int_tag['name']] += 1
                        elif len(old_tags):
                            self._add_changeset(n, cid)
                            self.changesets[cid]['nodes'][nid] = self.nodes[nid]
                            self.changesets[cid][int_tag['name'] + '_nd'][nid] = self.nodes[nid]
                            self.stats[int_tag['name']] += 1

    def _prety_tags(self, tags):
        """
        Converts list of k-v dict into python dict
        :param tags: list of k-v dicts
        :return: Dict
        """

        out_tags = {}
        for tag in tags:
            out_tags[tag['k']] = tag['v']
        return out_tags

    def _has_tag_changed(self, gid, old_tags, watch_tags, version, elem):
        """
        Checks if tags has changed on the changeset

        :param gid: Geometry id
        :param old_tags: Old tags
        :param watch_tags: Tags to check
        :param version: version to check
        :param elem: Type of element
        :return: Boolean
        """
        import time
        time.sleep(0.1)
        print '_has_tag_changed-> gid:{}'.format(gid)
        previous_elem = {}
        if elem == 'node':
            previous_elem = self.osm_api.NodeHistory(gid)[version-1]
        elif elem == 'way':
            previous_elem = self.osm_api.WayHistory(gid)[version - 1]
        elif elem == 'relation':
            previous_elem = self.osm_api.RelationHistory(gid)[version - 1]
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

    def _get_tags(self, element, keys):
        """
        Method that returns the tags of a lxml element

        :param element: Lxml element
        :param keys: Keys to select
        :return: Dict with the tag-value
        """
        ntags = element.findall(".//tag[@k]")
        re_keys = re.compile(keys)
        tags = {}
        for element in ntags:
            if re.match(re_keys,element.attrib['k']):
                tags[element.attrib['k']] = element.attrib['v']
        return tags



    def report(self):
        """
        Generates the report and sends it

        :return: None
        """

        if len(self.changesets) > 1000:
            self.changesets = self.changesets[:999]
            self.stats['limit_exceed'] = 'Note: For performance reasons only the first 1000 changesets are displayed.'

        now = datetime.now()

        template_data = {
            'changesets': self.changesets,
            'stats': self.stats,
            'date': now.strftime("%B %d, %Y"),
            'tags': self.config['tags'].keys()
        }
        print template_data
        html_version = self.html_tmpl.render(**template_data)
        text_version = self.text_tmpl.render(**template_data)

        if 'domain' in self.config['mailgun'] and 'api_key' in self.config['mailgun']:
            resp = requests.post(('https://api.mailgun.net/v2/{0}/messages'.format( self.config['mailgun']['domain'])),
                auth=('api', self.config['mailgun']['api_key']),
                data={
                        'from': 'Change Within <changewithin@{}>'.format(self.config['mailgun']['domain']),
                        'to': self.config['email']['recipients'].split(),
                        'subject': 'OSM building and address changes {0}'.format(now.strftime("%B %d, %Y")),
                        'text': text_version,
                        "html": html_version,
                })
        file_name = 'osm_change_report_{0}.html'.format(now.strftime('%m-%d-%y'))
        f_out = open(file_name, 'w')
        f_out.write(html_version.encode('utf-8'))
        f_out.close()
        print('Wrote {0}'.format(file_name))
        os.unlink(self.osc_file)

    def _add_changeset(self, el, cid):
        """
        Add a changeset on the list of rellevant changesets

        :param el:  Element
        :param cid: Changeset id
        :return: None
        """

        if not self.changesets.get(cid, False):
            self.changesets[cid] = {
                'id': cid,
                'user': el.get('user'),
                'uid': el.get('uid'),
                'wids': set(),
                'nodes': {}
            }
        for tag in self.config['tags'].keys():
            self.changesets[cid][tag + '_way'] = set()
            self.changesets[cid][tag + '_nd'] = {}

    def _add_node(self, el, nid):
        """
        Adds node to the list of rellevant nodes

        :param el: Element
        :param nid: Node id
        :return: None
        """

        if not self.nodes.get(nid, False):
            self.nodes[nid] = {
                'id': nid,
                'lat': float(el.get('lat')),
                'lon': float(el.get('lon'))
            }

if __name__ == '__main__':
    c = ChangesWithin()
    c.load_config()
    c.load_file()
    c.proces_data()
    c.report()
