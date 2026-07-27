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

    def test_each_font_is_a_consistent_rectangle(self):
        for name, font in (("FONT", bigtext.FONT), ("NARROW", bigtext.NARROW)):
            cols = len(font[" "][0])   # columns, not rows
            for ch, rows in font.items():
                self.assertEqual(len(rows), bigtext.HEIGHT, "%s %s" % (name, ch))
                for r in rows:
                    self.assertEqual(len(r), cols, "%s %s" % (name, ch))

    def test_the_two_fonts_cover_the_same_letters(self):
        self.assertEqual(set(bigtext.FONT), set(bigtext.NARROW))

    def test_narrow_really_is_narrower(self):
        self.assertLess(bigtext.width("PI TYPING TUTOR", bigtext.NARROW),
                        bigtext.width("PI TYPING TUTOR", bigtext.FONT))

    def test_fit_drops_to_narrow_only_when_it_has_to(self):
        wide = bigtext.width("PI", bigtext.FONT)
        self.assertEqual(bigtext.fit("PI", wide), bigtext.render("PI", bigtext.FONT))
        self.assertEqual(bigtext.fit("PI TYPING TUTOR", 78),
                         bigtext.render("PI TYPING TUTOR", bigtext.NARROW))

    def test_fit_gives_up_rather_than_overflowing(self):
        self.assertIsNone(bigtext.fit("PI TYPING TUTOR", 10))

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

    def test_the_title_is_one_line(self):
        """
        Three rows, not six. This is the entire reason the narrow font
        exists -- see the table test below for what the rows buy.
        """
        self.assertEqual(len(main.TITLE_ART), 3)


class FakeWin:
    """Records what landed where, so alignment can be asserted."""

    def __init__(self, h=24, w=80):
        self.h, self.w = h, w
        self.grid = [[" "] * w for _ in range(h)]
        # Every write, in order. The final grid is not enough: a row
        # drawn outside its frame gets painted over by the footer, so
        # the damage is invisible by the time the screen settles.
        self.calls = []

    def getmaxyx(self):
        return (self.h, self.w)

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.h):
            raise AssertionError("off-screen row %d" % y)
        if x < 0 or x + len(text) > self.w:
            raise AssertionError("off-screen cols %d..%d: %r"
                                 % (x, x + len(text), text))
        self.calls.append((y, x, text))
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

    def test_all_the_names_share_one_left_edge(self):
        names = ["Anne", "Arthur", "Betsey", "Matt"]
        cols = self.name_columns(self.draw(names), names)
        self.assertEqual(len(set(cols.values())), 1,
                         "ragged names: %r" % cols)

    def test_all_the_actions_share_one_left_edge(self):
        acts = ["+ New player", "Delete a player", "Quit"]
        cols = self.name_columns(self.draw(["Anne", "Matt"]), acts)
        self.assertEqual(len(set(cols.values())), 1,
                         "ragged actions: %r" % cols)

    def test_actions_line_up_with_the_glyphs_not_the_names(self):
        """
        The actions are a separate section under the rule. Indenting them
        to meet the names would say they are more people.
        """
        rows = self.draw(["Anne", "Matt"])
        name_row = [r for r in rows if "Anne" in r][0]
        act_row = [r for r in rows if "+ New player" in r][0]
        glyph_col = min(name_row.find(c) for c in "(</"
                        if name_row.find(c) > name_row.index("|"))
        self.assertEqual(act_row.index("+ New player"), glyph_col)
        self.assertLess(act_row.index("+ New player"), name_row.index("Anne"))

    def test_a_rule_separates_the_people_from_the_actions(self):
        rows = self.draw(["Anne", "Matt"])
        rules = [i for i, r in enumerate(rows)
                 if r.strip().startswith("|-") and r.strip().endswith("-|")]
        self.assertEqual(len(rules), 1, "expected exactly one divider")
        last_name = max(i for i, r in enumerate(rows) if "Matt" in r)
        first_act = min(i for i, r in enumerate(rows) if "+ New player" in r)
        self.assertLess(last_name, rules[0])
        self.assertLess(rules[0], first_act)

    def test_no_rule_on_a_device_with_no_players(self):
        """Nothing to separate: a bare rule would be a line to nowhere."""
        rows = self.draw([], with_cats=False)
        self.assertFalse([r for r in rows if r.strip().startswith("|-")])

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

    def test_a_full_household_fits_without_scrolling(self):
        """
        The vertical budget, asserted where it actually matters.

        Four kids plus three actions plus the divider needs fourteen rows
        of frame, and there are only twenty-four rows in the world. A
        title one row taller than it should be pushes the last action out
        and the list starts scrolling -- which is how "it fits" quietly
        stops being true. Checking the arithmetic in the abstract missed
        this; checking the drawn screen does not.
        """
        rows = self.draw(["Anne", "Arthur", "Betsey", "Matt"])
        for wanted in ("Anne", "Matt", "+ New player", "Delete a player",
                       "Quit"):
            self.assertTrue(any(wanted in r for r in rows),
                            "%r fell off the screen" % wanted)
        self.assertTrue(any(r.strip().startswith("|-") for r in rows),
                        "no room left for the divider")
        self.assertFalse(any("more" in r for r in rows),
                         "the list had to scroll")

    def test_everything_stays_on_an_eighty_by_twentyfour_screen(self):
        # FakeWin raises on any out-of-bounds write, so reaching here is
        # the assertion. Run the shapes most likely to overflow.
        self.draw(["Anne", "Arthur", "Betsey", "Matt", "Zoe", "Ravi",
                   "Ingrid", "Sam", "Priya", "Tom"])
        self.draw(["Bartholomew111"])
        self.draw([], with_cats=False)


class TestEveryLayoutMode(unittest.TestCase):
    """
    ui.menu has three layouts and every one of them must actually run.

    This exists because it shipped broken. A variable was initialised
    inside two of the three branches, and the third -- the panel layout,
    used by the main menu, the care board, the shop and the play picker
    -- raised UnboundLocalError on its first frame. The whole suite was
    green: 786 tests, and not one of them called `ui.menu` with a panel.

    Same shape as the care-board painter crash that started
    test_painters.py. A duck-typed branch nobody exercises is a branch
    nobody knows is broken.
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

    def layouts(self):
        def paint(win, top, left):
            win.addstr(top, left, "cat")
        return {
            "plain": {},
            "panel": {"panel": (10, 4, paint), "panel_title": "Mochi"},
            "framed": {"framed": True, "frame_title": "players"},
            "framed + divider": {"framed": True, "divider_after": 1},
            "framed + icons": {"framed": True, "icon_gutter": 7,
                               "option_icons": [("(^.^)", 0), None, None]},
        }

    def test_every_layout_draws_without_raising(self):
        for name, kw in self.layouts().items():
            try:
                ui.menu(FakeWin(), "Title", ["one", "two", "three"],
                        subtitle="sub", footer="foot", **kw)
            except Exception as exc:          # noqa: BLE001
                self.fail("%s layout raised: %r" % (name, exc))

    def test_every_layout_survives_the_smallest_screen(self):
        for name, kw in self.layouts().items():
            for size in ((24, 80), (20, 60)):
                try:
                    ui.menu(FakeWin(*size), "Title",
                            ["one", "two", "three"], **kw)
                except Exception as exc:      # noqa: BLE001
                    self.fail("%s at %r raised: %r" % (name, size, exc))

    def test_every_layout_survives_a_long_list(self):
        opts = ["option %d" % i for i in range(30)]
        for name, kw in self.layouts().items():
            kw = dict(kw)
            kw.pop("option_icons", None)
            try:
                ui.menu(FakeWin(), "Title", opts, **kw)
            except Exception as exc:          # noqa: BLE001
                self.fail("%s with 30 options raised: %r" % (name, exc))


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

    def test_a_squeezed_divider_is_dropped_not_drawn_through_the_frame(self):
        """
        When the box is too short for the rule, the rule goes -- it does
        not get drawn anyway.

        Reserving three rows for a divider that then scrolls out of view
        left blank rows sitting under a "v more". Taking the rows back
        fixed that and caused the opposite: the boundary came back into
        view, the rule was drawn without room for it, and an option
        landed on top of the frame's bottom edge.
        """
        opts = ["row %d" % i for i in range(12)]
        art = ["#" * 40] * 9        # a tall title, squeezing the box
        win = FakeWin()
        ui.menu(win, "T", opts, art=art, framed=True, divider_after=3)
        tops = [y for y, _x, t in win.calls if t.startswith(".-")]
        bottoms = [y for y, _x, t in win.calls if t.startswith("'-")]
        self.assertTrue(tops and bottoms, "no frame was drawn")
        top_y, bottom_y = tops[0], bottoms[0]
        for y, _x, text in win.calls:
            if "row " in text:
                self.assertGreater(y, top_y, "option above its frame")
                self.assertLess(y, bottom_y,
                                "option drawn on or below the frame edge")

    def test_the_divider_survives_when_there_is_room(self):
        """Guard: the test above must not pass by never drawing one."""
        win = FakeWin()
        ui.menu(win, "T", ["a", "b", "c", "d"], framed=True, divider_after=1)
        self.assertTrue(any(r.strip().startswith("|-") for r in win.rows()))

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
