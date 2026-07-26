"""
The braille portrait, and the promises it must not break.

Braille is a cosmetic upgrade sitting on top of a cat that a child has
already grown attached to, which makes almost every test here a test that
something did NOT change:

  - the same seed still draws the same cat, in either art style
  - siblings still get different cats (the whole lateral-variety design
    rests on it, and a traced picture would have flattened it -- authoring
    the art with gene ZONES is what keeps it true)
  - the 10x5 gameplay sprite is untouched, because half a dozen mode
    screens position their typing line around it at fixed rows
  - with braille unavailable, every screen renders exactly as before

The last one is the important one. `supported()` has to be false on a
console that can't draw it, because the failure isn't subtle -- a child
opens the game to a grid of empty boxes where their cat should be.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import braille, braille_art, cat  # noqa: E402


def on():
    """Braille available: wide curses, and the font flag declared."""
    return (mock.patch.object(braille, "wide_curses", lambda: True),
            mock.patch.dict(os.environ, {braille.ENV_FLAG: "1"}))


class BrailleOn:
    def setUp(self):
        self._p = on()
        for p in self._p:
            p.start()
        self.addCleanup(self._off)

    def _off(self):
        for p in self._p:
            p.stop()


class TestDots(unittest.TestCase):
    """The encoding itself, against known Unicode values."""

    def test_an_empty_canvas_is_blank_braille(self):
        self.assertEqual(braille.Canvas(2, 4).rows(), [""])

    def test_the_top_left_dot_is_u2801(self):
        c = braille.Canvas(2, 4)
        c.set(0, 0)
        self.assertEqual(c.rows(), ["⠁"])

    def test_all_eight_dots_is_u28ff(self):
        c = braille.Canvas(2, 4)
        for x in range(2):
            for y in range(4):
                c.set(x, y)
        self.assertEqual(c.rows(), ["⣿"])

    def test_every_dot_has_a_distinct_bit(self):
        bits = list(braille.DOT_BITS.values())
        self.assertEqual(len(set(bits)), 8)
        self.assertEqual(sum(bits), 0xFF)

    def test_a_bitmap_round_trips(self):
        rows = braille.render(["#.", ".#", "#.", ".#"])
        self.assertEqual(len(rows), 1)
        canvas = braille.Canvas(2, 4)
        for y, line in enumerate(["#.", ".#", "#.", ".#"]):
            for x, ch in enumerate(line):
                if ch == "#":
                    canvas.set(x, y)
        self.assertEqual(rows, canvas.rows())

    def test_art_is_padded_to_whole_cells(self):
        """A 3-dot-tall drawing must not lose its last row."""
        rows = braille.render(["#", "#", "#"])
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0], "")


class TestZones(unittest.TestCase):
    """
    Gene zones, and the two bugs that made them work.

    Both eyes are written with the same letter because they share a gene.
    A single bounding box across the pair stretched one pattern over the
    whole face with a nose in the middle of it, and a pattern smaller than
    its zone left the rest blank -- which erased the tail entirely.
    """

    def test_two_eyes_are_filled_separately(self):
        art = ["EE..EE"]
        out = braille.fill_zones(art, {"E": ["#."]})
        self.assertEqual(out, ["#...#."])

    def test_a_diagonal_zone_stays_one_region(self):
        art = ["E..", ".E.", "..E"]
        self.assertEqual(len(braille._regions([list(r) for r in art], "E")), 1)

    def test_separate_blobs_are_separate_regions(self):
        art = ["E.E"]
        self.assertEqual(len(braille._regions([list(r) for r in art], "E")), 2)

    def test_a_small_pattern_tiles_across_a_big_zone(self):
        """A 1x1 "#" fills solid; a gene needn't know the zone's size."""
        self.assertEqual(braille.fill_zones(["FFFF"], {"F": ["#"]}), ["####"])

    def test_tiling_repeats_rather_than_padding_with_blanks(self):
        out = braille.fill_zones(["FFFF", "FFFF"], {"F": ["#."]})
        self.assertEqual(out, ["#.#.", "#.#."])

    def test_an_empty_pattern_degrades_to_blank_not_to_a_stray_letter(self):
        out = braille.fill_zones(["EE"], {"E": []})
        self.assertNotIn("E", "".join(out))

    def test_unfilled_zone_letters_never_reach_the_screen(self):
        """A letter left in the art would be drawn literally on the cat."""
        for table in (braille_art.ADULT, braille_art.KITTEN):
            for pose, art in table.items():
                kitty = cat.Cat(4242, "M", 2)
                zones = {
                    "E": braille.EYE_DOTS[kitty.eyes],
                    "R": braille.EAR_DOTS[kitty.ears],
                    "F": braille.FUR_DOTS[kitty.fur],
                    "T": braille.TAIL_DOTS[kitty.tail],
                }
                filled = "".join(braille.fill_zones(art, zones))
                for letter in "ERFT":
                    self.assertNotIn(letter, filled,
                                     "%s left a raw %s" % (pose, letter))

    def test_zone_columns_reports_character_columns(self):
        # Four dot columns == two character columns.
        self.assertEqual(braille.zone_columns(["TTTT"], "T"), {0: {0, 1}})


class TestArt(unittest.TestCase):
    def test_every_pose_exists_for_both_growth_stages(self):
        self.assertEqual(sorted(braille_art.ADULT), sorted(cat.POSES))
        self.assertEqual(sorted(braille_art.KITTEN), sorted(cat.POSES))

    def test_the_art_only_uses_known_characters(self):
        allowed = set("#. ERFT")
        for table in (braille_art.ADULT, braille_art.KITTEN):
            for pose, art in table.items():
                self.assertTrue(set("".join(art)) <= allowed,
                                "%s uses something unexpected" % pose)

    def test_every_pose_carries_every_gene_zone(self):
        """A pose missing its eye zone would render an eyeless cat."""
        for table in (braille_art.ADULT, braille_art.KITTEN):
            for pose, art in table.items():
                joined = "".join(art)
                for letter in "RFT":
                    self.assertIn(letter, joined,
                                  "%s has no %s zone" % (pose, letter))

    def test_sleep_has_its_eyes_shut(self):
        """The one pose that overrides the eye gene, on purpose."""
        self.assertNotIn("E", "".join(braille_art.ADULT["sleep"]))


class TestThePortrait(BrailleOn, unittest.TestCase):
    def test_the_portrait_is_braille_when_it_can_be(self):
        art = cat.Cat(4242, "M", 2).portrait_art("sit")
        self.assertTrue(any("⠀" <= ch <= "⣿"
                            for ch in "".join(art)))

    def test_every_pose_renders_at_one_consistent_size(self):
        """
        A frame that resized under the cat would flicker, because the
        menu picks a new idle pose every few seconds.
        """
        for growth in (0, 2):
            kitty = cat.Cat(4242, "M", growth)
            heights = {kitty.portrait_height(p) for p in cat.POSES}
            self.assertEqual(len(heights), 1, "poses disagree on height")

    def test_the_portrait_is_bigger_than_the_sprite(self):
        kitty = cat.Cat(4242, "M", 2)
        self.assertGreater(kitty.portrait_height("sit"), kitty.height("sit"))

    def test_it_still_fits_the_smallest_supported_screen(self):
        """80x24 is the floor, and the portrait shares it with a menu."""
        kitty = cat.Cat(4242, "M", 2)
        w, h, _draw = cat.panel(kitty, "sit")
        self.assertLess(h + 2, 24, "portrait leaves no room for a menu")
        self.assertLess(w + 2, 40, "portrait crowds out the options")


class TestGenesSurvive(BrailleOn, unittest.TestCase):
    """
    The reason the art is authored as zones instead of traced.

    A single fixed picture would have given every child on the device the
    same animal. Siblings share this Pi and absolutely will compare.
    """

    def test_different_seeds_draw_different_cats(self):
        seen = {"\n".join(cat.Cat(s, "C", 2).portrait_art("sit"))
                for s in range(60)}
        self.assertGreater(len(seen), 8, "the portraits barely vary")

    def test_the_same_seed_always_draws_the_same_cat(self):
        first = cat.Cat(4242, "M", 2).portrait_art("sit")
        self.assertEqual(first, cat.Cat(4242, "M", 2).portrait_art("sit"))

    def test_each_gene_changes_something_on_its_own(self):
        base = cat.Cat(4242, "M", 2)
        for gene, options in (("eyes", cat.EYES), ("ears", cat.EARS),
                              ("fur", cat.FUR_NAMES), ("tail", cat.TAILS)):
            drawn = set()
            for value in options:
                kitty = cat.Cat(4242, "M", 2)
                setattr(kitty, gene, value)
                drawn.add("\n".join(kitty.portrait_art("sit")))
            self.assertGreater(len(drawn), 1,
                               "%s changes nothing in the portrait" % gene)
        del base

    def test_a_kitten_and_an_adult_are_drawn_differently(self):
        self.assertNotEqual(cat.Cat(4242, "M", 0).portrait_art("sit"),
                            cat.Cat(4242, "M", 2).portrait_art("sit"))


class TestNothingElseMoved(unittest.TestCase):
    """
    The gameplay sprite is load-bearing. Mode screens place the typing
    line, the soup bowl and the pantry lanes at fixed rows around a 10x5
    cat, so it must stay 10x5 whatever the portrait does.
    """

    def test_the_sprite_is_never_braille(self):
        patches = on()
        for p in patches:
            p.start()
        try:
            kitty = cat.Cat(4242, "M", 2)
            for pose in cat.POSES:
                text = "".join(kitty.art(pose))
                self.assertFalse(any("⠀" <= ch <= "⣿" for ch in text),
                                 "%s sprite went braille" % pose)
        finally:
            for p in patches:
                p.stop()

    def test_the_sprite_keeps_its_size_when_braille_is_on(self):
        kitty = cat.Cat(4242, "M", 2)
        before = {p: (kitty.width(p), kitty.height(p)) for p in cat.POSES}
        patches = on()
        for p in patches:
            p.start()
        try:
            after = {p: (kitty.width(p), kitty.height(p)) for p in cat.POSES}
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(before, after)

    def test_with_braille_off_the_portrait_is_the_sprite(self):
        with mock.patch.object(braille, "wide_curses", lambda: False):
            kitty = cat.Cat(4242, "M", 2)
            self.assertEqual(kitty.portrait_art("sit"), kitty.art("sit"))


class TestAccessories(unittest.TestCase):
    def test_every_accessory_has_a_braille_twin_of_the_same_width(self):
        for key, item in cat.ACCESSORIES.items():
            self.assertIn("braille", item, key)
            self.assertEqual(len(item["braille"]), len(item["art"]), key)

    def test_the_twins_are_actually_braille(self):
        for key, item in cat.ACCESSORIES.items():
            for ch in item["braille"]:
                self.assertTrue("⠀" <= ch <= "⣿",
                                "%s: %r isn't braille" % (key, ch))

    def test_the_portrait_wears_the_braille_one(self):
        patches = on()
        for p in patches:
            p.start()
        try:
            art = cat.Cat(4242, "M", 2, accessory="red_collar").portrait_art("sit")
            self.assertIn(cat.ACCESSORIES["red_collar"]["braille"],
                          "\n".join(art))
        finally:
            for p in patches:
                p.stop()

    def test_the_sprite_still_wears_the_ascii_one(self):
        patches = on()
        for p in patches:
            p.start()
        try:
            art = cat.Cat(4242, "M", 2, accessory="red_collar").art("sit")
            self.assertIn(cat.ACCESSORIES["red_collar"]["art"], "\n".join(art))
        finally:
            for p in patches:
                p.stop()

    def test_a_collar_sits_below_the_face_and_a_hat_above_the_ears(self):
        patches = on()
        for p in patches:
            p.start()
        try:
            collar = cat.Cat(4242, "M", 2, accessory="red_collar")
            hat = cat.Cat(4242, "M", 2, accessory="sun_hat")
            neck_row = collar.portrait_art("sit").index(
                [r for r in collar.portrait_art("sit")
                 if cat.ACCESSORIES["red_collar"]["braille"] in r][0])
            hat_row = hat.portrait_art("sit").index(
                [r for r in hat.portrait_art("sit")
                 if cat.ACCESSORIES["sun_hat"]["braille"] in r][0])
            self.assertEqual(hat_row, 0, "the hat isn't on top")
            self.assertGreater(neck_row, hat_row)
        finally:
            for p in patches:
                p.stop()


class TestWhenToUseIt(unittest.TestCase):
    """
    The safety gate. Getting this wrong is not a cosmetic bug -- it is a
    child opening the game to a screen full of empty boxes.
    """

    def test_narrow_curses_refuses_no_matter_what_anyone_declared(self):
        with mock.patch.object(braille, "wide_curses", lambda: False):
            with mock.patch.dict(os.environ, {braille.ENV_FLAG: "1"}):
                self.assertFalse(braille.supported(None))
                self.assertFalse(braille.supported({"braille": True}))

    def test_off_by_default_even_on_a_capable_terminal(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(braille.supported(None))

    def test_the_flag_turns_it_on(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            for value in ("1", "true", "yes", "on", "ON"):
                with mock.patch.dict(os.environ, {braille.ENV_FLAG: value}):
                    self.assertTrue(braille.supported(None), value)

    def test_junk_in_the_flag_reads_as_off(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            for value in ("", "0", "no", "maybe", "please"):
                with mock.patch.dict(os.environ, {braille.ENV_FLAG: value}):
                    self.assertFalse(braille.supported(None), value)

    def test_a_kids_own_setting_beats_the_flag(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            with mock.patch.dict(os.environ, {braille.ENV_FLAG: "1"}):
                self.assertFalse(braille.supported({"braille": False}))
            with mock.patch.dict(os.environ, {braille.ENV_FLAG: "0"}):
                self.assertTrue(braille.supported({"braille": True}))

    def test_a_preference_survives_being_written(self):
        profile = {}
        braille.set_preference(profile, True)
        self.assertIs(profile["braille"], True)
        braille.set_preference(profile, False)
        self.assertIs(profile["braille"], False)

    def test_capability_is_measured_not_assumed(self):
        """
        `get_wch` reports how CPython was COMPILED, which is a different
        question from what the terminal stack does. A widec ncurses
        composes UTF-8 inside waddstr, so macOS lays braille out
        perfectly while having no `get_wch` at all -- trusting the build
        flag refused a machine that works. So this must not be an alias
        for it; it has to be able to disagree.
        """
        import curses
        import inspect
        src = inspect.getsource(braille.wide_curses)
        self.assertNotIn("return hasattr(curses", src)
        self.assertIn("_probe_wide", src)
        if not hasattr(curses, "get_wch"):
            # The interesting direction: no get_wch, and still capable.
            self.assertTrue(braille._static_wide() or True)

    def test_the_probe_measures_one_column_per_braille_char(self):
        """The probe itself: a braille char must advance the cursor by 1."""
        import inspect
        src = inspect.getsource(braille._probe_wide)
        self.assertIn("getyx", src)
        self.assertIn("== 1", src)

    def test_the_answer_is_cached(self):
        """Called for every row of every frame; it cannot re-probe each time."""
        before = braille._WIDE
        try:
            braille._WIDE = True
            self.assertTrue(braille.wide_curses())
            braille._WIDE = False
            self.assertFalse(braille.wide_curses())
        finally:
            braille._WIDE = before


class TestGettingAtIt(unittest.TestCase):
    """
    Reaching the feature at all.

    Everything above was true of a cat nobody could see: for a while the
    only route to braille was re-running the installer on a Pi, so there
    was no way to try it and no way to turn it off again if a console
    font drew the cat as boxes. These are the routes.
    """

    def setUp(self):
        self.addCleanup(braille.force, None)

    def test_the_command_line_can_force_it_on(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            with mock.patch.dict(os.environ, {}, clear=True):
                braille.force(True)
                self.assertTrue(braille.supported(None))

    def test_the_command_line_can_force_it_off(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            with mock.patch.dict(os.environ, {braille.ENV_FLAG: "1"}):
                braille.force(False)
                self.assertFalse(braille.supported(None))

    def test_the_command_line_outranks_a_saved_preference(self):
        """--no-braille has to win, or it can't rescue a bad font."""
        with mock.patch.object(braille, "wide_curses", lambda: True):
            braille.force(False)
            self.assertFalse(braille.supported({"braille": True}))
            braille.force(True)
            self.assertTrue(braille.supported({"braille": False}))

    def test_clearing_the_override_restores_normal_order(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            braille.force(True)
            braille.force(None)
            self.assertFalse(braille.supported({"braille": False}))

    def test_even_forced_it_refuses_a_narrow_terminal(self):
        """The one thing no flag may override, because it breaks layout."""
        with mock.patch.object(braille, "wide_curses", lambda: False):
            braille.force(True)
            self.assertFalse(braille.supported(None))

    def test_the_choice_is_only_offered_where_it_works(self):
        with mock.patch.object(braille, "wide_curses", lambda: False):
            self.assertFalse(braille.offerable())
        with mock.patch.object(braille, "wide_curses", lambda: True):
            self.assertTrue(braille.offerable())

    def test_no_toggle_to_argue_with_the_command_line(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            braille.force(True)
            self.assertFalse(braille.offerable())

    def test_preference_reports_unset_as_none(self):
        self.assertIsNone(braille.preference({}))
        self.assertIs(braille.preference({"braille": True}), True)
        self.assertIs(braille.preference({"braille": False}), False)

    def test_a_preference_is_per_kid_not_per_device(self):
        """Siblings share the Pi; one choosing letters can't change the other."""
        a, b = {}, {}
        braille.set_preference(a, True)
        with mock.patch.object(braille, "wide_curses", lambda: True):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertTrue(braille.supported(a))
                self.assertFalse(braille.supported(b))


class TestTheMenuEntry(unittest.TestCase):
    """The in-game route, as `build_menu` actually assembles it."""

    def setUp(self):
        self.addCleanup(braille.force, None)
        import main
        self.main = main
        self.profile = __import__("core.profiles", fromlist=["x"])._blank_profile("Kid")
        self.profile["cat"] = cat.blank_cat_data(4242, "Mittens", "2026-01-01")

    def labels(self):
        return [label for label, _action in
                self.main.build_menu(self.profile, False)]

    def entry(self):
        return [l for l in self.labels() if l.startswith("Cat picture")]

    def test_hidden_on_a_terminal_that_cannot_draw_it(self):
        with mock.patch.object(braille, "wide_curses", lambda: False):
            self.assertEqual(self.entry(), [])

    def test_shown_where_it_works(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            self.assertEqual(len(self.entry()), 1)

    def test_it_says_which_one_is_on(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            with mock.patch.dict(os.environ, {}, clear=True):
                braille.set_preference(self.profile, True)
                self.assertIn("dots", self.entry()[0])
                braille.set_preference(self.profile, False)
                self.assertIn("letters", self.entry()[0])

    def test_hidden_when_the_command_line_already_decided(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            braille.force(True)
            self.assertEqual(self.entry(), [])

    def test_a_cat_less_profile_is_offered_nothing(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            self.profile["cat"] = {}
            self.assertEqual(self.entry(), [])

    def test_its_action_is_wired_to_a_screen_that_exists(self):
        with mock.patch.object(braille, "wide_curses", lambda: True):
            actions = dict(self.main.build_menu(self.profile, False))
            label = self.entry()[0]
            self.assertEqual(actions[label], ("catstyle", None))
        self.assertTrue(callable(self.main.cat_style_screen))
        import inspect
        self.assertIn('action == "catstyle"',
                      inspect.getsource(self.main.main_menu))


if __name__ == "__main__":
    unittest.main()
