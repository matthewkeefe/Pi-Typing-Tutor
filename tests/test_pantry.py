"""
Pantry Defense -- issue #19.

The acceptance criterion worth real coverage is the prefix input: "handles
overlapping word starts sanely (nearest-mouse tiebreak like dino)". Words
that share a start are the whole difficulty of turning Dino Chomp's
single-letter matcher into a word matcher.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, fx, profiles  # noqa: E402
from modes import pantry  # noqa: E402


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


def no_color():
    return (
        mock.patch.multiple("core.ui",
                            cp=mock.Mock(return_value=0),
                            cat_color=mock.Mock(return_value=0)),
        mock.patch.object(pantry, "cp", mock.Mock(return_value=0)),
    )


def mice(*specs):
    """(word, x) pairs -> Mouse objects on consecutive rows."""
    return [pantry.Mouse(word, x, 4 + i) for i, (word, x) in enumerate(specs)]


class TestPrefixMatching(unittest.TestCase):
    def test_only_matching_prefixes_come_back(self):
        pool = mice(("cat", 40), ("dog", 50), ("cap", 60))
        self.assertEqual({m.word for m in pantry.matches(pool, "c")},
                         {"cat", "cap"})
        self.assertEqual({m.word for m in pantry.matches(pool, "ca")},
                         {"cat", "cap"})
        self.assertEqual({m.word for m in pantry.matches(pool, "cat")},
                         {"cat"})

    def test_an_empty_prefix_matches_nothing(self):
        self.assertEqual(pantry.matches(mice(("cat", 40)), ""), [])

    def test_a_dead_end_prefix_matches_nothing(self):
        self.assertEqual(pantry.matches(mice(("cat", 40)), "cz"), [])

    def test_overlapping_starts_stay_reachable(self):
        """
        c-a-p must still shoo 'cap' even when 'cat' is nearer and shares
        two letters. Nothing may lock onto a single mouse early.
        """
        pool = mice(("cat", 20), ("cap", 60))
        for prefix in ("c", "ca"):
            self.assertEqual(len(pantry.matches(pool, prefix)), 2, prefix)
        final = pantry.matches(pool, "cap")
        self.assertEqual([m.word for m in final], ["cap"])


class TestNearestTiebreak(unittest.TestCase):
    """Closest to the bowl wins, the same rule Dino Chomp uses."""

    def test_nearest_is_the_smallest_x(self):
        pool = mice(("cat", 60), ("cat", 12), ("cat", 40))
        self.assertEqual(pantry.nearest(pool).x, 12)

    def test_nearest_of_nothing_is_none(self):
        self.assertIsNone(pantry.nearest([]))

    def test_duplicate_words_shoo_the_urgent_one(self):
        pool = mice(("cat", 55), ("cat", 9))
        hits = pantry.matches(pool, "cat")
        self.assertEqual(pantry.nearest(hits).x, 9)


class TestSpawnCollisions(unittest.TestCase):
    """
    A live 'cat' makes 'cats' unreachable, so it must never spawn. This is
    prevention rather than disambiguation -- cheaper and less surprising.
    """

    def test_a_prefix_of_a_live_word_is_refused(self):
        self.assertIsNone(pantry.pick_word(["cat"], ["cats"]))

    def test_an_extension_of_a_live_word_is_refused(self):
        self.assertIsNone(pantry.pick_word(["cats"], ["cat"]))

    def test_an_identical_word_is_refused(self):
        self.assertIsNone(pantry.pick_word(["cat"], ["cat"]))

    def test_an_unrelated_word_is_allowed(self):
        self.assertEqual(pantry.pick_word(["dog"], ["cat"]), "dog")

    def test_it_skips_past_collisions_to_a_usable_word(self):
        self.assertEqual(pantry.pick_word(["cats", "cat", "dog"], ["cat"]),
                         "dog")

    def test_anything_goes_on_an_empty_screen(self):
        self.assertEqual(pantry.pick_word(["cat"], []), "cat")

    def test_no_live_pair_is_ever_ambiguous(self):
        """Simulate a screen filling up; no two live words may collide."""
        pool = ["cat", "cats", "car", "dog", "do", "bird", "cap"]
        live = []
        for _ in range(5):
            w = pantry.pick_word([p for p in pool if p not in live], live)
            if w is None:
                break
            live.append(w)
        for a in live:
            for b in live:
                if a is not b:
                    self.assertFalse(a.startswith(b), "%s / %s" % (a, b))


class TestDifficultyRamp(unittest.TestCase):
    def test_speed_rises_then_flattens(self):
        vals = [pantry.speed_for(s) for s in (0, 50, 200, 500, 5000)]
        self.assertEqual(vals, sorted(vals))
        self.assertLessEqual(vals[-1], 10.5)

    def test_spawn_gap_shrinks_but_stays_readable(self):
        vals = [pantry.spawn_gap(s) for s in (0, 50, 200, 500, 5000)]
        self.assertEqual(vals, sorted(vals, reverse=True))
        self.assertGreaterEqual(min(vals), 1.0,
                                "a word must stay on screen long enough to read")

    def test_crowd_grows_but_is_capped(self):
        vals = [pantry.max_on_screen(s) for s in (0, 60, 180, 400, 5000)]
        self.assertEqual(vals, sorted(vals))
        self.assertLessEqual(max(vals), 5)
        self.assertGreaterEqual(min(vals), 2)

    def test_word_length_scales_with_the_alphabet(self):
        lens = [pantry.max_word_len(adaptive.FREQ_ORDER[:n])
                for n in (6, 10, 16, 21, 26)]
        self.assertEqual(lens, sorted(lens))
        self.assertGreaterEqual(min(lens), 3)
        self.assertLessEqual(max(lens), 7)

    def test_the_starting_alphabet_gets_short_words(self):
        self.assertLessEqual(pantry.max_word_len(adaptive.START_ALPHABET), 4)


class TestWordSupply(unittest.TestCase):
    def test_refill_respects_the_length_limit(self):
        import random
        p = profiles._blank_profile("T")
        for n in (6, 12, 26):
            p["alphabet"] = adaptive.FREQ_ORDER[:n]
            limit = pantry.max_word_len(p["alphabet"])
            for w in pantry._refill(p, limit, random.Random(2)):
                self.assertLessEqual(len(w), limit, w)
                self.assertGreaterEqual(len(w), 1, w)

    def test_refill_never_comes_back_empty(self):
        import random
        p = profiles._blank_profile("T")
        self.assertTrue(pantry._refill(p, 3, random.Random(5)))


class TestScoreOnlyStakes(unittest.TestCase):
    """#19: 'Mice never eat fish/progress -- score-mode stakes only.'"""

    def test_nothing_touches_fish_or_streaks(self):
        with open(pantry.__file__, encoding="utf-8") as fh:
            body = fh.read().split('"""', 2)[-1]
        for banned in ('profile["fish"]', "current_streak", "stamp_care",
                       "clear_wary", "set_wary", "fish -="):
            self.assertNotIn(banned, body, banned)


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

    def _draw(self, win, kitty, pool, typed="", **over):
        kw = dict(pose="sit", score=42, combo=3, lives=3, accuracy=94.2,
                  guard_x=16, bowl_x=2, lane_top=4, flash=False, msg=None)
        kw.update(over)
        pantry._draw(win, kitty, kw["pose"], pool, typed, kw["score"],
                     kw["combo"], kw["lives"], kw["accuracy"], kw["guard_x"],
                     kw["bowl_x"], kw["lane_top"], kw["flash"], kw["msg"])

    def test_draws_with_and_without_a_cat(self):
        for kitty in (cat.Cat(4242, "Mittens"), None):
            win = FakeWin()
            self._draw(win, kitty, mice(("cat", 50), ("dog", 65)))
            self.assertTrue(win.written)

    def test_draws_every_pose_and_flash(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for pose in ("sit", "swat", "wary"):
            for flash in (True, False):
                self._draw(win, kitty, mice(("cat", 40)), pose=pose,
                           flash=flash, msg="a mouse got to the bowl!")

    def test_highlighting_a_partially_typed_word_stays_on_screen(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), mice(("studio", 40), ("stub", 55)),
                   typed="stu")

    def test_a_mouse_at_the_right_edge_is_clipped_not_crashed(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), mice(("elephant", win.w - 4)))

    def test_a_mouse_past_the_left_edge_is_clipped(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), mice(("cat", -6)))

    def test_a_full_screen_of_mice(self):
        win = FakeWin()
        pool = [pantry.Mouse("word%d" % i, 30 + i * 6, 4 + (i % 5))
                for i in range(5)]
        self._draw(win, cat.Cat(1), pool, typed="w")

    def test_narrow_screen_does_not_escape(self):
        for kitty in (cat.Cat(4242), None):
            win = FakeWin(h=20, w=60)
            self._draw(win, kitty, mice(("cat", 40)), lane_top=4)


class TestGeometry(unittest.TestCase):
    def test_word_sits_clear_of_the_mouse_glyph(self):
        m = pantry.Mouse("cheese", 30, 5)
        self.assertEqual(m.word_x, 30 + len(pantry.MOUSE) + pantry.GAP)
        self.assertGreater(m.word_x, 30 + len(pantry.MOUSE) - 1)

    def test_width_covers_glyph_gap_and_word(self):
        m = pantry.Mouse("cheese", 30, 5)
        self.assertEqual(m.width, len(pantry.MOUSE) + pantry.GAP + 6)

    def test_the_glyph_is_terminal_safe(self):
        self.assertTrue(pantry.MOUSE.isascii() and pantry.MOUSE.isprintable())
        for row in pantry.BOWL:
            self.assertTrue(row.isascii() and row.isprintable(), row)

    def test_bowl_rows_are_a_consistent_width(self):
        self.assertEqual(len({len(r) for r in pantry.BOWL}), 1)
        self.assertEqual(len(pantry.BOWL[0]), pantry.BOWL_W)


class TestRegistration(unittest.TestCase):
    def test_it_is_in_the_arcade_for_everyone(self):
        import main
        labels = [lbl for _, _, lbl, _ in main.arcade_for(
            profiles._blank_profile("T"))]
        self.assertIn("Pantry Defense", labels)

    def test_high_score_key_migrates(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        self.assertEqual(p["pantry_high_score"], 0)


if __name__ == "__main__":
    unittest.main()
