import unittest
from changewithin import ChangeWithin
from changewithin import ChangeHandler
from osmium.osm import Location
from lib import get_state


class LibTest(unittest.TestCase):
    """
    Unitest for the lif module
    """

    def test_get_state(self):
        """
        Tests get_state 
        :return: None
        """

        state = get_state()
        self.assertNotEquals(state, "")


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
        conf = {
            'area': {
                'bbox': ['41.9933', '2.8576', '41.9623', '2.7847']
            },
            'tags': {
                'all': {
                    'tags': '.*=.*',
                    'type': 'node,way'
                }
            }
        }
        self.cw.conf = conf
        self.cw.load_config(conf)
        self.cw.handler.set_bbox('41.9933', '2.8576', '41.9623', '2.7847')
        self.assertEqual(self.cw.handler.north, 41.9933)
        self.assertEqual(self.cw.handler.east, 2.8576)
        self.assertEqual(self.cw.handler.south, 41.9623)
        self.assertEqual(self.cw.handler.west, 2.7847)
        self.cw.handler.set_tags("all", ".*", ".*", ["node", "way"])
        self.cw.process_file("test/test1.osc")
        self.assertTrue("all" in self.cw.handler.tags)
        self.assertTrue(48153728 in self.cw.changesets)

    def test_osc1_multiple(self):
        """
        Tests load of test1.osc
        :return: None
        """
        conf = {
            'area': {
                'bbox': ['41.9933', '2.8576', '41.9623', '2.7847']
            },
            'tags': {
                'highway': {
                    'tags': "highway=.*",
                    'type': 'node,way'
                },
                "housenumber": {
                    "tags": "addr:housenumber=.*",
                    "type": "way,node"
                },
                "building": {
                    "tags": "building=public",
                    "type": "way,node"
                }
            }
        }
        self.cw.conf = conf
        self.cw.load_config(conf)
        self.cw.handler.set_bbox('41.9933', '2.8576', '41.9623', '2.7847')
        self.assertEqual(self.cw.handler.north, 41.9933)
        self.assertEqual(self.cw.handler.east, 2.8576)
        self.assertEqual(self.cw.handler.south, 41.9623)
        self.assertEqual(self.cw.handler.west, 2.7847)
        self.cw.handler.set_tags("all", ".*", ".*", ["node", "way"])
        self.cw.process_file("test/test2.osc")
        self.assertTrue("all" in self.cw.handler.tags)
        self.assertEqual(len(set(self.cw.stats["all"])), len(self.cw.stats["all"]))
        self.assertEqual(len(set(self.cw.stats["building"])), len(self.cw.stats["building"]))
        self.assertTrue(48153728 in self.cw.changesets)

if __name__ == '__main__':
    unittest.main()
