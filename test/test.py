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
        self.cw.conf = {
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
        self.cw.process_file("test/test1.osc")

if __name__ == '__main__':
    unittest.main()
