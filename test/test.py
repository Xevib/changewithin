from lib import get_state, get_bbox, point_in_box, get_point, has_tag
import unittest
import json
from changewithin import ChangesWithin
import os
from lxml import etree


class ChangesWithinTest(unittest.TestCase):
    """
    Unitests for changeswithin
    """
    def test_get_state(self):
        """
        Funntion to test get_state function

        :return: None
        """

        state = get_state()
        self.assertGreater(int(state), 0)

    def test_get_bbox(self):
        """
        Function to test get_bbox

        :return:None
        """

        girona = json.load(open('test/girona.geojson'))
        bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
        self.assertEqual(bbox, [2.7831004, 41.9383698, 2.8982394, 42.0297266])

    def test_point_in_box(self):
        """
        Function to test point_to_box

        :return: None
        """

        girona = json.load(open('test/girona.geojson'))
        bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
        x = 2.82004
        y = 41.97744

        self.assertTrue(point_in_box(x, y, bbox))
        self.assertFalse(point_in_box(0, 0, bbox))

    def test_get_point(self):
        """
        Function to test get_point

        :return: None
        """

        self.assertEqual(get_point({'lat': 1, 'lon': 10}), [10 , 1])

    def test_config(self):
        """
        Function to test the load_configuration

        :return: None
        """

        os.environ['CONFIG'] = 'test/test_config.conf'
        c = ChangesWithin()
        c.load_config()
        sections = ['email', 'area', 'mailgun']
        self.assertEqual(c.get_config().keys(), sections)
        email_vals = {
            'recipients': 'someone@domain.com',
            'language': 'ca'
        }
        self.assertEqual(c.get_config()['email'], email_vals)
        area_vals = {
            'geojson':'test/girona.geojson'
        }
        self.assertEqual(c.get_config()['area'], area_vals)
        mailgun_vals = {
            'domain': 'changewithin.mailgun.org',
            'api_key': '1234'
        }
        self.assertEqual(c.get_config()['mailgun'], mailgun_vals)

    def test_has_tag(self):
        """
        Function to test has_tag
        :return: None
        """
        
        e1 = etree.parse('test/test_hastag_1.xml')
        self.assertTrue(has_tag(e1, 'building'))
        self.assertTrue(has_tag(e1, 'build.*'))
        self.assertTrue(has_tag(e1, 'building', 'junk'))
        self.assertFalse(has_tag(e1, 'building', 'asfas'))
        self.assertFalse(has_tag(e1, 'house'))



if __name__ == '__main__':
    unittest.main()
