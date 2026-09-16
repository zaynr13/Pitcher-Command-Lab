import unittest
import numpy as np
from src.game import Count, advance

class CoreTests(unittest.TestCase):

    def test_walk(self):
        self.assertEqual(advance(Count(3, 1), 'ball').result, 'walk')

    def test_strikeout(self):
        for event in ['whiff', 'called_strike', 'tipped_strike']:
            self.assertEqual(advance(Count(1, 2), event).result, 'strikeout')

    def test_two_strike_foul(self):
        self.assertEqual(advance(Count(2, 2), 'foul'), Count(2, 2))

    def test_full_pa(self):
        c = Count()
        for e in ['ball', 'called_strike', 'foul', 'foul', 'whiff']:
            c = advance(c, e)
        self.assertTrue(c.ended)
        self.assertEqual(c.result, 'strikeout')

    def test_impossible(self):
        for (b, s) in [(4, 0), (0, 3), (-1, 0)]:
            with self.assertRaises(ValueError):
                Count(b, s)
        with self.assertRaises(ValueError):
            advance(Count(0, 0, True), 'ball')
        with self.assertRaises(ValueError):
            advance(Count(), 'unknown')

    def test_all_contacts_end(self):
        for e in ['out', 'single', 'double', 'triple', 'home_run', 'reach_on_error', 'fielders_choice']:
            self.assertTrue(advance(Count(), e).ended)
if __name__ == '__main__':
    unittest.main()
