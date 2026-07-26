"""
The framed two-panel menu, and the scrolling it needed.

Written after the layout change surfaced a bug that had nothing to do
with framing: the main menu had grown to eighteen entries, and at 80x24
the last four -- including **Quit** -- simply fell off the bottom. It had
been drifting that way since Phase 6 started adding modes; centring the
options had hidden it, because a centred list looks deliberate right up
until it runs out of screen.

So most of what's here guards the boring property: every option must be
reachable, at the smallest supported terminal, however many there are.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, profiles, ui  # noqa: E402
import main  # noqa: E402


class FakeWin:
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

    def render(self):
        grid = [[" "] * self.w for _ in range(self.h)]
        for y, x, text in self.written:
            for i, ch in enumerate(text):
                if 0 <= y < self.h and 0 <= x + i < self.w:
                    grid[y][x + i] = ch
        return ["".join(r) for r in grid]


def no_color():
    zero = mock.Mock(return_value=0)
    return (mock.patch.multiple("core.ui", cp=zero, cat_color=zero),
            mock.patch.object(main, "cp", zero))


def a_profile():
    p = profiles._blank_profile("Matt")
    p["cat"] = cat.blank_cat_data(4242, "Mittens", "2025-03-14")
    return p


def window(idx, n, avail):
    """The viewport ui.menu computes. Mirrored here as arithmetic."""
    first = 0
    if n > avail:
        first = min(max(0, idx - avail // 2), n - avail)
    return first, first + avail


class TestScrolling(unittest.TestCase):
    def test_the_selection_is_always_visible(self):
        for n in (5, 18, 40):
            for avail in (4, 10, 16):
                for idx in range(n):
                    lo, hi = window(idx, n, avail)
                    self.assertTrue(lo <= idx < hi,
                                    "n=%d avail=%d idx=%d" % (n, avail, idx))

    def test_the_last_option_is_reachable(self):
        """Quit is the last entry. It has to be selectable."""
        for n in (18, 25, 40):
            for avail in (4, 10, 16):
                lo, hi = window(n - 1, n, avail)
                self.assertGreaterEqual(hi, n, "n=%d avail=%d" % (n, avail))

    def test_a_short_list_never_scrolls(self):
        for idx in range(5):
            self.assertEqual(window(idx, 5, 16), (0, 16))

    def test_the_window_never_runs_past_the_list(self):
        for idx in range(18):
            lo, _hi = window(idx, 18, 16)
            self.assertLessEqual(lo, 18 - 16)
            self.assertGreaterEqual(lo, 0)


class TestFrame(unittest.TestCase):
    def test_it_returns_the_inside(self):
        win = FakeWin()
        top, left, h, w = ui.frame(win, 2, 1, 10, 20)
        self.assertEqual((top, left), (3, 2))
        self.assertEqual((h, w), (8, 18))

    def test_it_is_pure_ascii(self):
        """Box-drawing characters don't survive TERM=linux."""
        win = FakeWin()
        ui.frame(win, 0, 0, 8, 30, "Mittens")
        for row in win.render():
            self.assertTrue(row.isascii(), row)

    def test_a_title_sits_in_the_top_edge(self):
        win = FakeWin()
        ui.frame(win, 0, 0, 6, 30, "Mittens")
        self.assertIn("Mittens", win.render()[0])

    def test_a_long_title_cannot_burst_the_frame(self):
        win = FakeWin()
        ui.frame(win, 0, 0, 6, 20, "X" * 60)
        self.assertLessEqual(len(win.render()[0].rstrip()), 20)

    def test_tiny_frames_do_not_crash(self):
        win = FakeWin()
        for h, w in ((1, 1), (3, 4), (2, 2)):
            ui.frame(win, 0, 0, h, w)


class TestTheCatPanel(unittest.TestCase):
    def setUp(self):
        self._patches = no_color()
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def test_a_profile_with_no_cat_gets_no_panel(self):
        blank = profiles._blank_profile("NoCat")
        self.assertIsNone(main.menu_cat_panel(blank, {"free_play": 0}))

    def test_the_panel_reports_a_size_that_fits_its_art(self):
        panel = main.menu_cat_panel(a_profile(), {"free_play": 0})
        self.assertIsNotNone(panel)
        width, height, _draw = panel
        kitty = cat.Cat.from_profile(a_profile())
        for pose in cat.POSES:
            self.assertLessEqual(kitty.width(pose), width, pose)

    def test_the_panel_fits_the_widest_pose_and_the_name(self):
        """
        Sized to the widest pose, so an idle change never reflows the
        frame -- and to the name, which sits in the frame edge and can be
        twelve characters. "Mittens" was arriving as "Mitten".
        """
        kitty = cat.Cat.from_profile(a_profile())
        width, _h, _d = main.menu_cat_panel(a_profile(), {"free_play": 0})
        self.assertGreaterEqual(width, max(kitty.width(p) for p in cat.POSES))
        self.assertGreaterEqual(width, len(kitty.name) + 3)

    def test_a_long_name_survives_the_frame_edge(self):
        p = a_profile()
        p["cat"]["name"] = "Bartholomew1"          # ask_text caps at 12
        width, _h, _d = main.menu_cat_panel(p, {"free_play": 0})
        win = FakeWin()
        ui.frame(win, 1, 1, 6, width + 2, p["cat"]["name"])
        self.assertIn(p["cat"]["name"], win.render()[1])

    def test_the_panel_draws_inside_its_frame(self):
        win = FakeWin()
        width, height, draw = main.menu_cat_panel(a_profile(),
                                                  {"free_play": 0})
        top, left, _h, _w = ui.frame(win, 2, 1, height + 2, width + 2)
        draw(win, top, left)
        for y, x, text in win.written:
            self.assertGreaterEqual(x, 1)
            self.assertLessEqual(x + len(text), 1 + width + 2)

    def test_a_cat_and_a_panel_fit_side_by_side_at_80x24(self):
        """The whole point of the layout: both, on the smallest screen."""
        width, _h, _d = main.menu_cat_panel(a_profile(), {"free_play": 0})
        menu_left = width + 2 + 2
        self.assertLess(menu_left, 40, "the cat must leave room for a menu")
        self.assertGreater(80 - menu_left, 30, "the menu needs real width")


class TestEveryOptionIsReachable(unittest.TestCase):
    def test_the_real_main_menu_fits_or_scrolls(self):
        """
        The bug this file exists for: eighteen entries, sixteen rows, and
        Quit off the bottom with nothing saying so.
        """
        profile = a_profile()
        entries = main.build_menu(profile, False)
        self.assertGreater(len(entries), 12, "menu has grown a lot")
        avail = 16
        reachable = set()
        for idx in range(len(entries)):
            lo, hi = window(idx, len(entries), avail)
            reachable.update(range(lo, min(hi, len(entries))))
        self.assertEqual(reachable, set(range(len(entries))))

    def test_quit_is_the_last_entry_and_reachable(self):
        entries = main.build_menu(a_profile(), False)
        self.assertIn("Quit", entries[-1][0])
        lo, hi = window(len(entries) - 1, len(entries), 16)
        self.assertTrue(lo <= len(entries) - 1 < hi)


if __name__ == "__main__":
    unittest.main()
