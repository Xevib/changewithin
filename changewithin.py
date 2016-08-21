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
        self.config = ConfigParser()
        self.osc_url = ''
        self.tree = etree.ElementTree()

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
            self.config.read(os.path.join(dir_path, args.config))
        else:
            self.config.read(os.path.join(dir_path, 'config.ini'))
        languages = ['en']
        for option, value in self.config.items('email'):
            if option == 'language':
                languages = [value].extend(languages)

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
            self.config.set('area', 'geojson', os.environ['AREA_GEOJSON'])

        if 'MAILGUN_DOMAIN' in os.environ:
            self.config.set('mailgun', 'domain', os.environ['MAILGUN_DOMAIN'])

        if 'MAILGUN_API_KEY' in os.environ:
            self.config.set('mailgun', 'api_key', os.environ['MAILGUN_API_KEY'])

        if 'EMAIL_RECIPIENTS' in os.environ:
            self.config.set('email', 'recipients', os.environ['EMAIL_RECIPIENTS'])

        if 'LANGUAGE' in os.environ:
            self.config.set('email', 'language', os.environ['LANGUAGE'])


        #
        # Get started with the area of interest (AOI).
        #

        aoi_href = self.config.get('area', 'geojson')
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
        self.stats['buildings'] = 0
        self.stats['addresses'] = 0
        self.tree = etree.parse(self.osc_file)

    def proces_data(self):
        """
        Proces the whole OSC file

        :return: None
        """
        sys.stderr.write('finding points\n')

        # Find nodes that fall within specified area

        self.proces_nodes()
        self.proces_ways()
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
                add_node(n, nid, self.nodes)
                ntags = n.findall(".//tag[@k]")
                addr_tags = get_address_tags(ntags)
                version = int(n.get('version'))

                # Capture address changes
                if version != 1:
                    if has_address_change(nid, addr_tags, version, 'node'):
                        add_changeset(n, cid, self.changesets)
                        self.changesets[cid]['nodes'][nid] = self.nodes[nid]
                        self.changesets[cid]['addr_chg_nd'][nid] = self.nodes[nid]
                        self.stats['addresses'] += 1
                elif len(addr_tags):
                    add_changeset(n, cid, self.changesets)
                    self.changesets[cid]['nodes'][nid] = self.nodes[nid]
                    self.changesets[cid]['addr_chg_nd'][nid] = self.nodes[nid]
                    self.stats['addresses'] += 1

    def proces_ways(self):
        """
        Process the ways of the OSC file

        :return: None
        """

        sys.stderr.write('finding changesets\n')
        # Find ways that contain nodes that were previously determined to fall within specified area

        elements = self.tree.xpath('//way')
        for w in elements:
            relevant = False
            cid = w.get('changeset')
            wid = w.get('id', -1)

            # Only if the way has 'building' tag
            if has_building_tag(w):
                for nd in w.iterfind('./nd'):
                    if nd.get('ref', -2) in self.nodes.keys():
                        relevant = True
                        add_changeset(w, cid, self.changesets)
                        nid = nd.get('ref', -2)
                        self.changesets[cid]['nodes'][nid] = self.nodes[nid]
                        self.changesets[cid]['wids'].add(wid)
            if relevant:
                self.stats['buildings'] += 1
                wtags = w.findall(".//tag[@k]")
                version = int(w.get('version'))
                addr_tags = get_address_tags(wtags)

                # Capture address changes
                if version != 1:
                    if has_address_change(wid, addr_tags, version, 'way'):
                        self.changesets[cid]['addr_chg_way'].add(wid)
                        self.stats['addresses'] += 1
                elif len(addr_tags):
                    self.changesets[cid]['addr_chg_way'].add(wid)
                    self.stats['addresses'] += 1

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
            'date': now.strftime("%B %d, %Y")
        }
        html_version = self.html_tmpl.render(**template_data)
        text_version = self.text_tmpl.render(**template_data)

        if self.config.has_option('mailgun', 'domain') and self.config.has_option('mailgun', 'api_key'):
            resp = requests.post(('https://api.mailgun.net/v2/{0}/messages'.format( self.config.get('mailgun', 'domain'))),
                auth=('api', self.config.get('mailgun', 'api_key')),
                data={
                        'from': 'Change Within <changewithin@{}>'.format(self.config.get('mailgun', 'domain')),
                        'to': self.config.get('email', 'recipients').split(),
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

if __name__ == '__main__':
    c = ChangesWithin()
    c.load_config()
    c.load_file()
    c.proces_data()
    c.report()
