"""
Cat Tower geometry, and the save migration that carried the old rocket
progress onto it.

The tower is drawn on a fixed canvas so it grows upward in place rather
than jumping around the screen -- that promise is only worth anything if
every piece is exactly the canvas width and the canvas never changes
height, which is what most of this file checks. A tier that is one column
wide gets drawn one column off and the whole stack shears.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import profiles  # noqa: E402
from modes import tower  # noqa: E402

WIDTH = 14
HEIGHT = 18


class TestCanvas(unittest.TestCase):
    def test_every_tier_is_the_same_size(self):
        for tiers in range(8):
            canvas = tower.build_tower(tiers)
            self.assertEqual(len(canvas), HEIGHT, "tiers=%d" % tiers)
            for i, line in enumerate(canvas):
                self.assertEqual(len(line), WIDTH,
                                 "tiers=%d line=%d: %r" % (tiers, i, line))

    def test_the_toy_overlay_keeps_the_canvas_square(self):
        canvas = tower.build_tower(7, toy=True)
        self.assertEqual(len(canvas), HEIGHT)
        for line in canvas:
            self.assertEqual(len(line), WIDTH, repr(line))

    def test_every_named_piece_is_canvas_width(self):
        """A piece of the wrong width shears the stack below it."""
        pieces = [tower.BLANK, tower.POST_PLAIN, tower.POST_HAMMOCK,
                  tower.POST_CUBBY, tower.POST_TOY, tower.POST_SISAL,
                  tower.POST_BOTTOM, tower.WING_T, tower.WING_M,
                  tower.WING_B, tower.RUG]
        pieces += tower.PERCH + tower.BASE
        for piece in pieces:
            self.assertEqual(len(piece), WIDTH, repr(piece))

    def test_it_is_pure_ascii(self):
        """Box-drawing characters don't survive TERM=linux."""
        for tiers in range(8):
            for line in tower.build_tower(tiers):
                self.assertTrue(all(ord(c) < 128 for c in line), repr(line))


class TestGrowth(unittest.TestCase):
    def test_nothing_is_drawn_at_zero_tiers(self):
        """Bar the rug it stands on -- there is no tower yet."""
        canvas = tower.build_tower(0)
        self.assertEqual(canvas[16], tower.RUG)
        self.assertEqual(set("".join(canvas[:16])), {" "})

    def test_the_tower_only_ever_grows(self):
        """
        Tier N+1 never removes ink that tier N had drawn. This is the whole
        point of building bottom-up: the kid watches the thing they built
        get taller, never redraw.
        """
        for tiers in range(7):
            before = tower.build_tower(tiers)
            after = tower.build_tower(tiers + 1)
            painted = sum(c != " " for line in before for c in line)
            grown = sum(c != " " for line in after for c in line)
            self.assertGreater(grown, painted, "tier %d added nothing" % (tiers + 1))

    def test_the_base_lands_first_and_stays_put(self):
        """The base occupies the same rows from tier 1 to tier 7."""
        first = tower.build_tower(1)[12:16]
        self.assertEqual(first, tower.BASE)
        for tiers in range(1, 8):
            self.assertEqual(tower.build_tower(tiers)[12:16], tower.BASE,
                             "base moved at tier %d" % tiers)

    def test_there_is_a_name_for_every_tier(self):
        self.assertEqual(len(tower.TIER_NAMES), 7)


class TestMigration(unittest.TestCase):
    """
    A kid who was midway through the rocket keeps that progress on the
    tower. Losing it would be a silent punishment for a reskin they had
    no say in.
    """

    def test_old_keys_are_carried_across(self):
        old = {"Kid": {"name": "Kid", "rocket_level": 4, "rocket_parts": 3,
                       "dino_high_score": 210}}
        p = profiles.get_or_create(old, "Kid")
        self.assertEqual(p["tower_level"], 4)
        self.assertEqual(p["tower_tiers"], 3)
        self.assertEqual(p["moth_high_score"], 210)

    def test_old_keys_are_removed(self):
        old = {"Kid": {"name": "Kid", "rocket_level": 4, "rocket_parts": 3,
                       "dino_high_score": 210}}
        p = profiles.get_or_create(old, "Kid")
        for dead in ("rocket_level", "rocket_parts", "dino_high_score"):
            self.assertNotIn(dead, p)

    def test_a_newer_value_wins_over_an_older_one(self):
        """
        A save opened on a newer build and then an older one can carry both
        keys. The new key is the one that was actually being written to.
        """
        both = {"Kid": {"name": "Kid", "rocket_parts": 1, "tower_tiers": 6}}
        p = profiles.get_or_create(both, "Kid")
        self.assertEqual(p["tower_tiers"], 6)
        self.assertNotIn("rocket_parts", p)

    def test_a_save_with_neither_key_gets_the_defaults(self):
        p = profiles.get_or_create({"New": {"name": "New"}}, "New")
        self.assertEqual(p["tower_level"], 1)
        self.assertEqual(p["tower_tiers"], 0)
        self.assertEqual(p["moth_high_score"], 0)

    def test_migration_is_idempotent(self):
        old = {"Kid": {"name": "Kid", "rocket_parts": 3}}
        first = dict(profiles.get_or_create(old, "Kid"))
        second = profiles.get_or_create(old, "Kid")
        self.assertEqual(second["tower_tiers"], first["tower_tiers"])


if __name__ == "__main__":
    unittest.main()
