from lib import get_state, get_bbox, point_in_box, get_point
import unittest
import json
from changewithin import ChangesWithin
import os


class ChangesWithinTest(unittest.TestCase):
    def test_get_state(self):
        state = get_state()
        self.assertGreater(int(state), 0)

    def test_get_bbox(self):
        girona = json.load(open('test/girona.geojson'))
        bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
        self.assertEqual(bbox, [2.7831004, 41.9383698, 2.8982394, 42.0297266])

    def test_point_in_box(self):
        girona = json.load(open('test/girona.geojson'))
        bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
        x = 2.82004
        y = 41.97744

        self.assertTrue(point_in_box(x, y, bbox))
        self.assertFalse(point_in_box(0, 0, bbox))

    def test_get_point(self):
        self.assertEqual(get_point({'lat': 1, 'lon': 10}), [10 , 1])
        
if __name__ == '__main__':
    unittest.main()
