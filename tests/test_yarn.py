"""
Yarn Chase -- issue #18.

The mode's whole promise is that a mistake costs nothing but the streak, so
most of these tests are about what does NOT happen on a miss. Rendering is
checked against a fake window (see test_fx.py) since the suite stays
curses-free; colour lookups are stubbed because `curses.color_pair` needs a
live terminal.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, fx, profiles, shop  # noqa: E402
from modes import yarn  # noqa: E402


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


def no_color():
    return (
        mock.patch.multiple("core.ui",
                            cp=mock.Mock(return_value=0),
                            cat_color=mock.Mock(return_value=0)),
        mock.patch.object(yarn, "cp", mock.Mock(return_value=0)),
    )


def source():
    with open(yarn.__file__, encoding="utf-8") as fh:
        return fh.read()


def a_profile(**over):
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0}
    p.update(over)
    return p


class TestToyVariant(unittest.TestCase):
    """Owning a toy swaps the art -- the shop's first appearance in a game."""

    def test_default_when_nothing_is_owned(self):
        self.assertEqual(yarn.toy_for(a_profile()), yarn.DEFAULT_TOY)

    def test_each_toy_has_its_own_art(self):
        seen = {}
        for item_id, art, name in yarn.TOY_ART:
            p = a_profile()
            p["inventory"]["toys"] = [item_id]
            got_art, got_name = yarn.toy_for(p)
            self.assertEqual(got_name, name, item_id)
            seen[name] = "".join(got_art)
        self.assertEqual(len(set(seen.values())), len(seen),
                         "two toys render identically: %r" % seen)

    def test_priority_is_stable_when_several_are_owned(self):
        p = a_profile()
        p["inventory"]["toys"] = [i for i, _, _ in yarn.TOY_ART]
        self.assertEqual(yarn.toy_for(p)[1], yarn.TOY_ART[0][2])

    def test_every_toy_id_is_a_real_shop_item(self):
        for item_id, _, _ in yarn.TOY_ART:
            self.assertIn(item_id, shop.BY_ID, item_id)
            self.assertEqual(shop.BY_ID[item_id]["kind"], shop.KIND_TOY, item_id)

    def test_toy_art_is_terminal_safe(self):
        arts = [art for _, art, _ in yarn.TOY_ART] + [yarn.DEFAULT_TOY[0]]
        for art in arts:
            for glyph in art:
                self.assertEqual(len(glyph), 1, art)
                self.assertTrue(glyph.isascii() and glyph.isprintable(), art)


class TestNothingIsLost(unittest.TestCase):
    """
    #18: "any error = the yarn wiggles away (streak resets, nothing else
    lost -- no lives, no falls)". These assert the absence of the mechanics
    the platformer has, so a later well-meaning edit can't quietly add them.
    """

    def test_module_has_no_lives_concept(self):
        for name in ("LIVES", "lives"):
            self.assertFalse(hasattr(yarn, name), name)

    def test_source_never_deducts_anything(self):
        body = source().split('"""', 2)[-1]   # skip the module docstring
        for banned in ("lives -=", "fish -=", "-= 1"):
            self.assertNotIn(banned, body, banned)

    def test_a_round_is_always_the_same_length(self):
        """A miss consumes a flick like a hit does -- the round can't shrink."""
        self.assertEqual(source().count("flicks += 1"), 2)


class TestRendering(unittest.TestCase):
    def setUp(self):
        fx.clear()
        self._patches = no_color()
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def _scene(self, win, kitty, pose, **over):
        art, name = yarn.DEFAULT_TOY
        kw = dict(target="tin", typed="ti", flicks=3, streak=2,
                  cat_pos=(yarn.REST_X, win.h - 5), toy_x=win.w - 22,
                  msg=None, wrong=False)
        kw.update(over)
        yarn._draw_scene(win, kitty, pose, art, name, **kw)

    def test_draws_every_pose_with_a_cat(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for pose in ("sit", "pounce", "overjoyed", "wary"):
            self._scene(win, kitty, pose)
        self.assertTrue(win.written)

    def test_draws_without_a_cat(self):
        win = FakeWin()
        self._scene(win, None, "sit")
        self.assertTrue(win.written)

    def test_draws_an_adult_cat(self):
        win = FakeWin()
        self._scene(win, cat.Cat(4242, "Mittens", growth=3), "pounce")

    def test_many_cats_and_toys(self):
        win = FakeWin()
        for seed in range(0, 400, 41):
            kitty = cat.Cat(seed)
            for _, art, name in yarn.TOY_ART:
                yarn._draw_scene(win, kitty, "sit", art, name, "tin", "t",
                                 1, 0, (yarn.REST_X, win.h - 5), win.w - 22)

    def test_pounce_arc_stays_on_screen(self):
        """The cat travels the width of the floor and must never escape."""
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        floor = win.h - 5

        def draw(pose, pos, toy_x=None, msg=None, wrong=False):
            self._scene(win, kitty, pose, cat_pos=pos,
                        toy_x=win.w - 22 if toy_x is None else toy_x,
                        msg=msg, wrong=wrong)

        with mock.patch.object(yarn.curses, "napms", lambda _ms: None):
            yarn._pounce(draw, floor, yarn.REST_X, win.w - 22)

    def test_wiggle_away_pushes_the_toy_off_the_edge(self):
        """The toy slides past the right margin; clipping must hold."""
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        floor = win.h - 5

        def draw(pose, pos, toy_x=None, msg=None, wrong=False):
            self._scene(win, kitty, pose, cat_pos=pos,
                        toy_x=win.w - 22 if toy_x is None else toy_x,
                        msg=msg, wrong=wrong)

        with mock.patch.object(yarn.curses, "napms", lambda _ms: None):
            yarn._wiggle_away(draw, floor, yarn.REST_X, win.w - 22,
                              "yarn ball", "tin")

    def test_long_word_and_long_toy_name_fit(self):
        win = FakeWin()
        self._scene(win, cat.Cat(1), "sit",
                    target="w" * 40, typed="w" * 20,
                    msg="x" * 70, wrong=True)

    def test_narrow_screen_does_not_escape(self):
        for kitty in (cat.Cat(4242), None):
            win = FakeWin(h=20, w=60)
            self._scene(win, kitty, "sit", cat_pos=(yarn.REST_X, 15),
                        toy_x=40)


if __name__ == "__main__":
    unittest.main()
