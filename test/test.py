from lib import *
import unittest


class ChangesWithinTest(unittest.TestCase):
    def test_get_state(self):
        state = get_state()
        self.assertGreater(int(state),0)


if __name__ == '__main__':
    unittest.main()
