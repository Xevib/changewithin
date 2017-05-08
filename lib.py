""" Support functions for changewithin.py script.
"""
import json
import requests
import os
import sys
import urllib
from lxml import etree
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
