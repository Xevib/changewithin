from lib import get_state, get_bbox
import unittest
import json


class ChangesWithinTest(unittest.TestCase):
    def test_get_state(self):
        state = get_state()
        self.assertGreater(int(state), 0)

    def test_get_bbox(self):
        girona = json.load(open('test/girona.geojson'))
        bbox = get_bbox(girona['features'][0]['geometry']['coordinates'][0])
        self.assertEqual(bbox, [2.7831004, 41.9383698, 2.8982394, 42.0297266])


if __name__ == '__main__':
    unittest.main()
