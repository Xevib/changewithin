from lib import get_state, get_bbox, point_in_box, get_point, has_tag
import unittest
from changewithin import ChangeWithin
from changewithin import ChangeHandler
from osmium.osm import Location


class HandlerTest(unittest.TestCase):
    """
    Unittest for the handler
    """
    def setUp(self):
        """
        Initialization
        """
        self.handler = ChangeHandler()

    def test_in_bbox(self):
        """
        Tests the location_in_bbox of handler
        :return: None
        """

        self.handler.set_bbox(41.9933, 2.8576, 41.9623, 2.7847)
        l = Location(2.81372, 41.98268)
        self.assertTrue(self.handler.location_in_bbox(l))

    def test_set_tags(self):
        """
        Test set_tags of handler
        :return: None
        """

        self.handler.set_tags("test", "key_tag", "element_tag", ["nodes", "ways"])
        self.assertTrue("test" in self.handler.tags)

    def test_set_bbox(self):
        """
        Test set_bbox of handler
        :return: None 
        """

        self.handler.set_bbox(41.9933, 2.8576, 41.9623, 2.7847)
        self.assertEqual(self.handler.north, 41.9933)
        self.assertEqual(self.handler.east, 2.8576)
        self.assertEqual(self.handler.south, 41.9623)
        self.assertEqual(self.handler.west, 2.7847)


class ChangesWithinTest(unittest.TestCase):
    """
    Initest for changeswithin using osmium
    """
    def setUp(self):
        """
        Constructor
        """
        self.cw = ChangeWithin()

    def test_osc1(self):
        """
        Tests load of test1.osc
        :return: None
        """
        self.cw.load_file("test/test1.osc")


# class ChangesWithinTest(unittest.TestCase):
#     """
#     Unitests for changeswithin
#     """
#     def test_get_state(self):
#         """
#         Funntion to test get_state function
#
#         :return: None
#         """
#
#         state = get_state()
#         self.assertGreater(int(state), 0)
#
#     def test_get_bbox(self):
#         """
#         Function to test get_bbox
#
#         :return:None
#         """
#
#         girona = json.load(open('test/girona.geojson'))
#         bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
#         self.assertEqual(bbox, [2.7831004, 41.9383698, 2.8982394, 42.0297266])
#
#     def test_point_in_box(self):
#         """
#         Function to test point_to_box
#
#         :return: None
#         """
#
#         girona = json.load(open('test/girona.geojson'))
#         bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
#         x = 2.82004
#         y = 41.97744
#
#         self.assertTrue(point_in_box(x, y, bbox))
#         self.assertFalse(point_in_box(0, 0, bbox))
#
#     def test_get_point(self):
#         """
#         Function to test get_point
#
#         :return: None
#         """
#
#         self.assertEqual(get_point({'lat': 1, 'lon': 10}), [10 , 1])
#
#     def test_config(self):
#         """
#         Function to test the load_configuration
#
#         :return: None
#         """
#
#         os.environ['CONFIG'] = 'test/test_config.conf'
#         c = ChangesWithin()
#         c.load_config()
#         sections = ['email', 'area', 'mailgun']
#         self.assertEqual(c.get_config().keys(), sections)
#         email_vals = {
#             'recipients': 'someone@domain.com',
#             'language': 'ca'
#         }
#         self.assertEqual(c.get_config()['email'], email_vals)
#         area_vals = {
#             'geojson':'test/girona.geojson'
#         }
#         self.assertEqual(c.get_config()['area'], area_vals)
#         mailgun_vals = {
#             'domain': 'changewithin.mailgun.org',
#             'api_key': '1234'
#         }
#         self.assertEqual(c.get_config()['mailgun'], mailgun_vals)
#
#     def test_has_tag(self):
#         """
#         Function to test has_tag
#
#         :return: None
#         """
#
#         e1 = etree.parse('test/test_hastag_1.xml')
#         self.assertTrue(has_tag(e1, 'building'))
#         self.assertTrue(has_tag(e1, 'build.*'))
#         self.assertTrue(has_tag(e1, 'building', 'junk'))
#         self.assertFalse(has_tag(e1, 'building', 'asfas'))
#         self.assertFalse(has_tag(e1, 'house'))
#
#     def test_prety_tags(self):
#         """
#         Function to test prety_tags
#
#         :return:  Nne
#         """
#         c = ChangesWithin()
#         test_in = [{'k': 'hi', 'v': 'bye'}, {'k': 'one', 'v': 'two'}]
#         test_out = {'hi': 'bye', 'one': 'two'}
#         self.assertEqual(c._prety_tags(test_in), test_out)
#
#     def test_has_tag_changed(self):
#         """
#         Function to test has_tag_changed
#
#         :return:
#         """
#         c = ChangesWithin()
#         old_tags = {'addr:housenumber': '49',
#                     'addr:postcode': '17001',
#                     'addr:street': 'Carrer de Santa Clara',
#                     'addr:city': 'Girona',
#                     'addr:country': 'ES'}
#         self.assertTrue(c._has_tag_changed('781488074', old_tags, 'addr:.*', 4, 'node'))
#         self.assertFalse(c._has_tag_changed('781488074', old_tags, 'addr:.*', 5, 'node'))

if __name__ == '__main__':
    unittest.main()
