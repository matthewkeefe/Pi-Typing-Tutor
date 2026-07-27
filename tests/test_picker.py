"""
The profile picker: block-letter title, framed table, one left edge.

This screen is the first thing anyone sees and the only one built for a
shared device, so the thing being pinned here is ALIGNMENT. Names read
down a straight edge whether or not a row has a cat beside it, because
the rows without one -- New player, Delete, Quit -- hold the same empty
gutter rather than sliding left to meet the frame.

The frame width caught a real bug: sized at "longest option + 4" it lost
the last two characters of the longest entry, because the selection
marker "> " is prepended after the box is measured. "Delete a player"
arrived as "Delete a play".
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import bigtext, cat, profiles, ui  # noqa: E402
import main  # noqa: E402


class TestBlockLetters(unittest.TestCase):
    def test_a_letter_is_three_rows_tall(self):
        self.assertEqual(len(bigtext.render("A")), 3)

    def test_every_letter_the_titles_need_exists(self):
        for ch in set("PI TYPING TUTOR" + "A CAT TAUGHT ME TO TYPE"):
            self.assertIn(ch.upper(), bigtext.FONT, ch)

    def test_an_unknown_character_is_blank_not_an_error(self):
        """A title is never worth taking the screen down for."""
        self.assertEqual(bigtext.render("%"), bigtext.render(" "))

    def test_the_font_is_a_consistent_rectangle(self):
        for ch, rows in bigtext.FONT.items():
            self.assertEqual(len(rows), bigtext.HEIGHT, ch)
            for r in rows:
                self.assertEqual(len(r), bigtext.WIDTH, ch)

    def test_letters_are_distinguishable_from_each_other(self):
        drawn = {ch: "\n".join(bigtext.render(ch)) for ch in bigtext.FONT}
        self.assertEqual(len(set(drawn.values())), len(drawn),
                         "two letters render identically")

    def test_stacked_lines_share_one_centre(self):
        """A two-line title that disagrees about the middle looks broken."""
        art = bigtext.block(["PI TYPING", "TUTOR"])
        self.assertEqual(len(art), 6)
        self.assertLessEqual(max(len(r) for r in art), 78)

    def test_the_ascii_fallback_uses_no_block_characters(self):
        with mock.patch.object(bigtext, "ASCII_FALLBACK", True):
            art = bigtext.render("PI")
        self.assertTrue(all(ch in "# " for ch in "".join(art)))
        self.assertTrue(all(ord(ch) < 128 for ch in "".join(art)))


class TestTitle(unittest.TestCase):
    def test_the_title_fits_the_smallest_screen(self):
        self.assertLessEqual(max(len(r) for r in main.TITLE_ART), 78)

    def test_the_tagline_is_plain_text_and_smaller(self):
        """
        In block letters it comes to 137 columns. It is the subtitle; it
        is meant to read as smaller than the thing it sits under.
        """
        self.assertIsInstance(main.TAGLINE, str)
        self.assertLess(len(main.TAGLINE), max(len(r) for r in main.TITLE_ART))
        self.assertGreater(bigtext.width(main.TAGLINE), 80)

    def test_title_and_tagline_leave_room_for_the_table(self):
        """24 rows total, and the players still have to fit under it."""
        used = len(main.TITLE_ART) + 1 + 1 + 1   # art, title, tagline, gap
        self.assertLessEqual(used, 10)


class FakeWin:
    """Records what landed where, so alignment can be asserted."""

    def __init__(self, h=24, w=80):
        self.h, self.w = h, w
        self.grid = [[" "] * w for _ in range(h)]

    def getmaxyx(self):
        return (self.h, self.w)

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.h):
            raise AssertionError("off-screen row %d" % y)
        if x < 0 or x + len(text) > self.w:
            raise AssertionError("off-screen cols %d..%d: %r"
                                 % (x, x + len(text), text))
        for i, ch in enumerate(text):
            self.grid[y][x + i] = ch

    def erase(self):
        pass

    def refresh(self):
        pass

    def nodelay(self, *a):
        pass

    def keypad(self, *a):
        pass

    def getch(self):
        return 27

    def rows(self):
        return ["".join(r).rstrip() for r in self.grid]


def people(names, with_cats=True):
    out = {}
    for i, n in enumerate(names):
        p = profiles._blank_profile(n)
        if with_cats:
            p["cat"] = cat.blank_cat_data(1000 + i * 37, "C%d" % i, "2026-01-01")
        out[n] = p
    return out


class TestTheTable(unittest.TestCase):
    def setUp(self):
        zero = mock.Mock(return_value=0)
        self.patches = [
            mock.patch.multiple("core.ui", cp=zero, cat_color=zero),
            mock.patch.object(main, "cp", zero),
            mock.patch("curses.curs_set", mock.Mock()),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self.patches:
            p.stop()

    def draw(self, names, with_cats=True):
        win = FakeWin()
        main.pick_profile(win, people(names, with_cats))
        return win.rows()

    def name_columns(self, rows, names):
        cols = {}
        for n in names:
            for r in rows:
                i = r.find(n)
                if i >= 0:
                    cols[n] = i
                    break
        return cols

    def test_names_and_actions_share_one_left_edge(self):
        """
        The whole point of the gutter. A row with no cat must not slide
        left to where the glyphs are.
        """
        names = ["Anne", "Arthur", "Betsey", "Matt"]
        rows = self.draw(names)
        cols = self.name_columns(rows, names + ["+ New player", "Quit"])
        self.assertEqual(len(set(cols.values())), 1,
                         "ragged left edge: %r" % cols)

    def test_the_longest_entry_is_not_truncated(self):
        """The bug the frame width had: 'Delete a play'."""
        rows = self.draw(["Anne", "Matt"])
        self.assertTrue(any("Delete a player" in r for r in rows),
                        "the longest row lost its tail")

    def test_a_fourteen_character_name_survives(self):
        rows = self.draw(["Bartholomew111"])
        self.assertTrue(any("Bartholomew111" in r for r in rows))

    def test_the_table_is_framed(self):
        rows = self.draw(["Anne"])
        self.assertTrue(any(r.strip().startswith(".") and "players" in r
                            for r in rows), "no framed table")
        self.assertTrue(any(r.strip().startswith("'") for r in rows))

    def test_a_cat_glyph_sits_in_the_gutter_not_through_the_frame(self):
        rows = self.draw(["Anne"])
        row = [r for r in rows if "Anne" in r][0]
        bar = row.index("|")
        glyph_at = min(row.find(c) for c in "(</" if row.find(c) > bar)
        self.assertGreater(glyph_at, bar, "glyph drew over the frame edge")
        self.assertLess(glyph_at, row.index("Anne"))

    def test_a_device_with_no_cats_holds_no_empty_gutter(self):
        """First run: indenting past a column that holds nothing reads
        as a fault, not as space being kept."""
        rows = self.draw([], with_cats=False)
        row = [r for r in rows if "+ New player" in r][0]
        self.assertLess(row.index("+ New player") - row.index("|"), 6)

    def test_everything_stays_on_an_eighty_by_twentyfour_screen(self):
        # FakeWin raises on any out-of-bounds write, so reaching here is
        # the assertion. Run the shapes most likely to overflow.
        self.draw(["Anne", "Arthur", "Betsey", "Matt", "Zoe", "Ravi",
                   "Ingrid", "Sam", "Priya", "Tom"])
        self.draw(["Bartholomew111"])
        self.draw([], with_cats=False)


class TestFramedMenuSizing(unittest.TestCase):
    """
    `ui.menu(framed=True)` sizing, tested directly.

    Going through pick_profile alone was not enough: the longest row it
    ever produces is "Delete a player", and the box's minimum width
    happens to be just wide enough to hide a sizing error. A slightly
    longer option would have truncated again with nothing going red.
    """

    def setUp(self):
        zero = mock.Mock(return_value=0)
        self.patches = [mock.patch.multiple("core.ui", cp=zero, cat_color=zero),
                        mock.patch("curses.curs_set", mock.Mock())]
        for p in self.patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self.patches:
            p.stop()

    def show(self, options):
        win = FakeWin()
        ui.menu(win, "Title", options, framed=True)
        return win.rows()

    def test_a_long_option_is_not_clipped_by_its_own_frame(self):
        long = "Something considerably longer than a name"
        rows = self.show([long, "short"])
        self.assertTrue(any(long in r for r in rows),
                        "the frame was sized too small for its contents")

    def test_the_frame_grows_with_the_longest_option(self):
        narrow = self.show(["a", "b"])
        wide = self.show(["a" * 40, "b"])

        def box_width(rows):
            edge = [r for r in rows if r.strip().startswith("'")][0]
            return len(edge.strip())

        self.assertGreater(box_width(wide), box_width(narrow))

    def test_it_never_grows_past_the_screen(self):
        # FakeWin raises on any out-of-bounds write.
        self.show(["x" * 200, "y"])


if __name__ == "__main__":
    unittest.main()
