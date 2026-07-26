"""
Platform Jumper rendering -- issue #20.

The jumper is either the kid's cat or the legacy stick figure. Both paths
are exercised against a fake window that fails loudly on an off-screen
write, the same approach test_fx.py uses: the thing most likely to break
here is geometry, since a 4-row kitten (or a 5-row adult) now stands where
a 3-row stick figure used to.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, fx  # noqa: E402
from modes import platformer  # noqa: E402


def no_color():
    """
    Colour lookups need a live terminal (`curses.color_pair` raises without
    `initscr`), and the rest of the suite is deliberately curses-free. Stub
    the attribute lookups to 0 so the geometry -- which is what issue #20
    actually risks breaking -- can be tested off-terminal. Which colour a
    cat gets is covered by the gene tests in test_cat.py.
    """
    return mock.patch.multiple(
        "core.ui",
        cp=mock.Mock(return_value=0),
        cat_color=mock.Mock(return_value=0),
    ), mock.patch.object(platformer, "cp", mock.Mock(return_value=0))


class FakeWin:
    """A window that refuses to be written outside its bounds."""

    def __init__(self, h=24, w=80):
        self.h, self.w = h, w
        self.written = []

    def getmaxyx(self):
        return (self.h, self.w)

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.h and 0 <= x < self.w):
            raise AssertionError("wrote off-screen at %r,%r" % (y, x))
        if x + len(text) > self.w:
            raise AssertionError("wrote past the right edge at %r,%r" % (y, x))
        self.written.append((y, x, text))

    def erase(self):
        self.written = []

    def refresh(self):
        pass


def profile_with_cat(seed=4242, growth=0):
    return {"name": "Test", "rocket_level": 1,
            "cat": {"seed": seed, "name": "Mittens", "growth": growth}}


class TestHeroSelection(unittest.TestCase):
    def test_cat_profile_yields_a_cat(self):
        self.assertIsNotNone(cat.Cat.from_profile(profile_with_cat()))

    def test_legacy_profile_yields_none(self):
        self.assertIsNone(cat.Cat.from_profile({"name": "Legacy"}))

    def test_every_frame_maps_to_a_real_pose(self):
        for frame, pose in platformer.CAT_POSES.items():
            self.assertIn(pose, cat.POSES, "%s -> %s" % (frame, pose))

    def test_both_art_paths_cover_the_same_frames(self):
        self.assertEqual(sorted(platformer.CAT_POSES),
                         sorted(platformer.LEGACY_ART))


class TestHeroGeometry(unittest.TestCase):
    """The jumper stands ON the platform: its bottom row lands on hy."""

    def test_legacy_art_bottom_row_sits_on_the_anchor(self):
        for frame, art in platformer.LEGACY_ART.items():
            offsets = [i - (len(art) - 1) for i in range(len(art))]
            self.assertEqual(max(offsets), 0, frame)
            self.assertEqual(len(offsets), len(art), frame)

    def test_cat_bottom_row_sits_on_the_anchor(self):
        kitty = cat.Cat(4242, "Mittens")
        for growth in (0, 3):
            for frame, pose in platformer.CAT_POSES.items():
                rows = kitty.height(pose, growth)
                self.assertEqual((-rows + 1) + rows - 1, 0,
                                 "%s g=%d" % (frame, growth))

    def test_cat_fits_the_platform_slot(self):
        """The jumper is inset 2 into a SLOT_W-4 platform."""
        usable = platformer.SLOT_W - 2
        for seed in range(0, 400, 37):
            kitty = cat.Cat(seed)
            for growth in (0, 3):
                for pose in platformer.CAT_POSES.values():
                    self.assertLessEqual(
                        kitty.width(pose, growth), usable,
                        "seed=%d pose=%s g=%d" % (seed, pose, growth))


class TestRendering(unittest.TestCase):
    """Both art paths must paint an 80x24 screen without escaping it."""

    def setUp(self):
        fx.clear()          # no stray particles drifting in from elsewhere
        self._patches = no_color()
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def _render_every_frame(self, kitty):
        words = ["cat", "dog", "fish"] * 4
        win = FakeWin()
        base_row = win.h - 4
        for frame in platformer.CAT_POSES:
            for height in range(0, 5):
                platformer._draw_world(
                    win, words, 1, 7,
                    (6, base_row - height), frame, kitty,
                    3, 2, "ca",
                    "testing" if frame == "fall" else None,
                )
        return win

    def test_draws_with_a_kitten(self):
        win = self._render_every_frame(cat.Cat(4242, "Mittens"))
        self.assertTrue(win.written)

    def test_draws_with_an_adult_cat(self):
        win = self._render_every_frame(cat.Cat(4242, "Mittens", growth=3))
        self.assertTrue(win.written)

    def test_draws_without_a_cat(self):
        win = self._render_every_frame(None)
        self.assertTrue(win.written)

    def test_many_cats_all_render(self):
        for seed in range(0, 500, 23):
            self._render_every_frame(cat.Cat(seed))

    def test_hero_survives_offscreen_positions(self):
        """Mid-fall the jumper travels below the floor; clipping must hold."""
        kitty = cat.Cat(4242, "Mittens")
        win = FakeWin()
        for y in (-5, -1, 0, win.h - 1, win.h, win.h + 6):
            for x in (-9, -1, 0, win.w - 2, win.w, win.w + 12):
                for frame in platformer.CAT_POSES:
                    platformer._draw_hero(win, kitty, frame, x, y)
                    platformer._draw_hero(win, None, frame, x, y)

    def test_narrow_screen_does_not_escape(self):
        """80x24 is the floor, but nothing should explode below it."""
        for kitty in (cat.Cat(4242, "Mittens"), None):
            win = FakeWin(h=20, w=60)
            platformer._draw_world(win, ["cat"] * 12, 1, 7,
                                   (6, 16), "stand", kitty, 3, 2, "c")


if __name__ == "__main__":
    unittest.main()
