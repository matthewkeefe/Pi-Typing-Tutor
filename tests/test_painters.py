"""
The `draw_extra` contract -- every menu painter, called the way ui.menu
actually calls it.

This exists because of a real crash found in the first minute of the
first playtest. `ui.menu` passes `(win, idx)` to its `draw_extra`; the
care board's painter took only `(win)`. Phase 5 added the index for the
shop painter and never updated the care one, so **entering the care board
raised TypeError for four phases** -- in the pedagogical core of the game,
the screen a kid is supposed to open every single day.

643 tests did not catch it, because not one of them called a painter.
Every painter test in this file would have.

The general lesson: a duck-typed callback contract needs a test that
actually exercises the contract, or the only thing enforcing it is
whoever last remembered it existed.
"""

import inspect
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, contests, profiles, scrapbook, shop, ui  # noqa: E402
from modes import care  # noqa: E402
import main  # noqa: E402


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
    zero = mock.Mock(return_value=0)
    return (mock.patch.multiple("core.ui", cp=zero, cat_color=zero),
            mock.patch.object(care, "cp", zero),
            mock.patch.object(main, "cp", zero))


def a_profile():
    p = profiles._blank_profile("Test")
    p["cat"] = cat.blank_cat_data(4242, "Mittens", "2025-03-14")
    p["fish"] = 400
    shop.buy(p, "yarn_ball")
    scrapbook.catch_from_word(p, "eel")
    return p


def painters(profile):
    """
    Every draw_extra this game builds, by the call that builds it.

    None is a legitimate answer -- `menu_cat_painter` returns it for a
    profile with no cat, and `ui.menu` guards with `if draw_extra`. Those
    are dropped rather than treated as failures.
    """
    kitty = cat.Cat.from_profile(profile)
    built = {
        "menu cat": main.menu_cat_painter(profile, {"free_play": 0}),
        "shop": main._shop_painter(profile, kitty, shop.shelf(profile)),
    }
    return {name: fn for name, fn in built.items() if fn is not None}


def panels(profile):
    """
    Every framed left column, by the call that builds it.

    A panel is `(width, height, draw)` and `draw(win, top, left)` -- a
    different contract from draw_extra, and one that needs the same
    guarding, since these are now on most screens a kid touches.
    """
    kitty = cat.Cat.from_profile(profile)
    built = {
        "care board": care._board_panel(profile, kitty),
        "main menu": main.menu_cat_panel(profile, {"free_play": 0}),
        "plain cat": cat.panel(kitty, "sit"),
    }
    return {name: p for name, p in built.items() if p is not None}


class TestTheContract(unittest.TestCase):
    def test_ui_menu_passes_two_arguments(self):
        """
        Pin the contract itself. If ui.menu ever changes what it passes,
        this fails here rather than in a kid's hands.
        """
        src = inspect.getsource(ui.menu)
        self.assertIn("draw_extra(stdscr, idx)", src)

    def test_a_cat_less_profile_gets_no_menu_painter(self):
        """None is allowed, and ui.menu guards for it."""
        blank = profiles._blank_profile("NoCat")
        self.assertIsNone(main.menu_cat_painter(blank, {"free_play": 0}))
        self.assertIn("if draw_extra", inspect.getsource(ui.menu))

    def test_the_painters_exist_for_a_normal_profile(self):
        self.assertEqual(sorted(painters(a_profile())), ["menu cat", "shop"])

    def test_the_panels_exist_for_a_normal_profile(self):
        self.assertEqual(sorted(panels(a_profile())),
                         ["care board", "main menu", "plain cat"])

    def test_every_painter_accepts_what_ui_menu_sends(self):
        profile = a_profile()
        for name, paint in painters(profile).items():
            sig = inspect.signature(paint)
            try:
                sig.bind(FakeWin(), 0)
            except TypeError as exc:
                self.fail("%s painter rejects (win, idx): %s" % (name, exc))

    def test_every_painter_actually_runs(self):
        profile = a_profile()
        patches = no_color()
        for p in patches:
            p.start()
        try:
            for name, paint in painters(profile).items():
                win = FakeWin()
                try:
                    paint(win, 0)
                except Exception as exc:          # noqa: BLE001
                    self.fail("%s painter raised: %r" % (name, exc))
        finally:
            for p in patches:
                p.stop()

    def test_painters_survive_every_highlighted_row(self):
        """idx walks the whole menu -- the shop painter reads it."""
        profile = a_profile()
        patches = no_color()
        for p in patches:
            p.start()
        try:
            for name, paint in painters(profile).items():
                for idx in range(0, 12):
                    win = FakeWin()
                    try:
                        paint(win, idx)
                    except Exception as exc:      # noqa: BLE001
                        self.fail("%s painter raised at idx=%d: %r"
                                  % (name, idx, exc))
        finally:
            for p in patches:
                p.stop()

    def test_painters_survive_the_smallest_supported_screen(self):
        profile = a_profile()
        patches = no_color()
        for p in patches:
            p.start()
        try:
            for name, paint in painters(profile).items():
                for size in ((24, 80), (20, 60)):
                    win = FakeWin(*size)
                    try:
                        paint(win, 0)
                    except Exception as exc:      # noqa: BLE001
                        self.fail("%s painter raised at %r: %r"
                                  % (name, size, exc))
        finally:
            for p in patches:
                p.stop()


class TestPanels(unittest.TestCase):
    """
    The framed-column contract: (width, height, draw), drawing inside the
    box it was given. Most screens use one now, so a break here is a
    break nearly everywhere.
    """

    def setUp(self):
        self._patches = no_color()
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def test_every_panel_reports_a_sane_size(self):
        for name, (w, h, _d) in panels(a_profile()).items():
            self.assertGreater(w, 0, name)
            self.assertGreater(h, 0, name)
            self.assertLess(w, 40, "%s leaves no room for a menu" % name)

    def test_every_panel_draws_inside_its_frame(self):
        for name, (w, h, draw) in panels(a_profile()).items():
            win = FakeWin()
            top, left, _ih, _iw = ui.frame(win, 1, 1, h + 2, w + 2)
            try:
                draw(win, top, left)
            except Exception as exc:            # noqa: BLE001
                self.fail("%s panel raised: %r" % (name, exc))
            for y, x, text in win.written:
                self.assertLessEqual(x + len(text), 1 + w + 2,
                                     "%s drew past its frame" % name)

    def test_panels_survive_every_profile_state(self):
        for state, profile in _states().items():
            for name, (w, h, draw) in panels(profile).items():
                win = FakeWin()
                top, left, _ih, _iw = ui.frame(win, 1, 1, h + 2, w + 2)
                try:
                    draw(win, top, left)
                except Exception as exc:        # noqa: BLE001
                    self.fail("%s panel raised on a %s profile: %r"
                              % (name, state, exc))

    def test_a_cat_less_profile_gets_no_panel(self):
        blank = profiles._blank_profile("NoCat")
        self.assertIsNone(cat.panel(None))
        self.assertIsNone(main.menu_cat_panel(blank, {"free_play": 0}))

    def test_panel_contents_are_evaluated_at_draw_time(self):
        """
        The care board's gauges change as a kid works through the tasks.
        A snapshot taken when the menu opened would show stale numbers.
        """
        profile = a_profile()
        kitty = cat.Cat.from_profile(profile)
        _w, _h, draw = care._board_panel(profile, kitty)
        win = FakeWin()
        draw(win, 1, 1)
        before = [t for _y, _x, t in win.written]
        for task in cat.CARE_TASKS:
            cat.stamp_care(profile, task)
        win2 = FakeWin()
        draw(win2, 1, 1)
        after = [t for _y, _x, t in win2.written]
        self.assertNotEqual(before, after, "gauges did not refresh")


def _states():
    fresh = profiles._blank_profile("Fresh")
    no_cat = profiles._blank_profile("NoCat")
    no_cat["cat"] = {}
    loved = a_profile()
    for task in cat.CARE_TASKS:
        cat.stamp_care(loved, task)
    neglected = a_profile()
    neglected["cat"]["care"] = {}
    neglected["cat"]["wary"] = True
    decked = a_profile()
    decked["fish"] = 9999
    for item in ("rug", "cushion", "plant"):
        shop.buy(decked, item)
    contests.award(decked, 0)
    return {"fresh": fresh, "no cat": no_cat, "cared for": loved,
            "wary": neglected, "full of decor": decked}


class TestAcrossProfileStates(unittest.TestCase):
    """
    The crash was found with a save from the day before, not a fresh one.
    Painters have to cope with every shape of profile, including the ones
    only time produces.
    """

    def test_every_painter_on_every_profile_state(self):
        patches = no_color()
        for p in patches:
            p.start()
        try:
            for state, profile in _states().items():
                for name, paint in painters(profile).items():
                    win = FakeWin()
                    try:
                        paint(win, 0)
                    except Exception as exc:      # noqa: BLE001
                        self.fail("%s painter raised on a %s profile: %r"
                                  % (name, state, exc))
        finally:
            for p in patches:
                p.stop()

    def test_an_old_save_reaches_the_care_board(self):
        """
        The exact reported scenario: yesterday's save, ENTER on "Care
        for ...". Drives the painter the way the board does.
        """
        old = {"name": "Yesterday", "cat": {"seed": 4242, "name": "Mittens",
                                            "hatched": "2026-07-25",
                                            "care": {}, "wary": False}}
        profile = profiles.get_or_create({"Yesterday": old}, "Yesterday")
        patches = no_color()
        for p in patches:
            p.start()
        try:
            kitty = cat.Cat.from_profile(profile)
            w, h, draw = care._board_panel(profile, kitty)
            win = FakeWin()
            top, left, _ih, _iw = ui.frame(win, 1, 1, h + 2, w + 2)
            draw(win, top, left)
        finally:
            for p in patches:
                p.stop()


if __name__ == "__main__":
    unittest.main()
