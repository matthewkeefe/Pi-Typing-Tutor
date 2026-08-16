"""
Moth Catch -- the badge thresholds, the fallback art, and the one
invariant that decides whether the mode is fair.

The cat's catching zone is a constant, not the drawn sprite's width. A
kid with a big adult cat and a kid with a kitten have to get the same
game, and the speed ramp is tuned against that number.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import badges  # noqa: E402
from modes import moth  # noqa: E402


class TestArt(unittest.TestCase):
    def test_both_poses_are_the_same_size(self):
        """A swat that changes the cat's footprint makes it twitch."""
        self.assertEqual(len(moth.LEGACY_CAT), len(moth.LEGACY_SWAT))
        for idle, swat in zip(moth.LEGACY_CAT, moth.LEGACY_SWAT):
            self.assertEqual(len(idle), len(swat), "%r vs %r" % (idle, swat))

    def test_the_fallback_cat_is_rectangular(self):
        for art in (moth.LEGACY_CAT, moth.LEGACY_SWAT):
            widths = {len(line) for line in art}
            self.assertEqual(len(widths), 1, widths)

    def test_it_is_pure_ascii(self):
        """Box-drawing characters don't survive TERM=linux."""
        lines = list(moth.LEGACY_CAT) + list(moth.LEGACY_SWAT) + [moth.FLOOR]
        for pair in moth.WINGS:
            lines += list(pair)
        for line in lines:
            self.assertTrue(all(ord(c) < 128 for c in line), repr(line))

    def test_the_cat_fits_inside_its_own_reach(self):
        """
        The sprite is drawn at column 2 and moths are caught at 2 + REACH.
        A sprite wider than the reach would be drawn over the catch line,
        so a moth would look eaten before it counted.
        """
        self.assertLessEqual(len(moth.LEGACY_CAT[0]), moth.REACH)

    def test_wings_come_in_pairs(self):
        for pair in moth.WINGS:
            self.assertEqual(len(pair), 2)
            for wing in pair:
                self.assertEqual(len(wing), 1, repr(wing))


class TestPacing(unittest.TestCase):
    def test_speed_rises_with_score_then_flattens(self):
        self.assertLess(moth._speed_for(0), moth._speed_for(100))
        self.assertEqual(moth._speed_for(10000), moth._speed_for(20000))

    def test_spawn_gap_shrinks_but_has_a_floor(self):
        self.assertGreater(moth._spawn_gap(0), moth._spawn_gap(100))
        self.assertEqual(moth._spawn_gap(10000), moth._spawn_gap(20000))
        self.assertGreater(moth._spawn_gap(10000), 0)


class TestBadges(unittest.TestCase):
    """
    The ids are frozen on purpose -- they are what an earned badge is
    stored under, so renaming them would un-earn badges on every save.
    """

    def test_the_reskinned_badges_kept_their_ids(self):
        ids = {b["id"] for b in badges.BADGES}
        for kept in ("rocket_3", "rocket_full", "dino_50", "dino_150", "dino_300"):
            self.assertIn(kept, ids)

    def test_they_read_against_the_new_keys(self):
        earned = {"tower_tiers": 7, "moth_high_score": 300}
        for b in badges.BADGES:
            if b["id"] in ("rocket_3", "rocket_full", "dino_50", "dino_150", "dino_300"):
                self.assertTrue(b["check"](earned), b["id"])

    def test_no_badge_still_advertises_the_old_theme(self):
        for b in badges.BADGES:
            blob = (b["name"] + " " + b["desc"]).lower()
            self.assertNotIn("rocket", blob, b["id"])
            self.assertNotIn("dino", blob, b["id"])
            self.assertNotIn("ship", blob, b["id"])


if __name__ == "__main__":
    unittest.main()
