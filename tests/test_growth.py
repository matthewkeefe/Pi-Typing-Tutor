"""
Growth stages -- issue #22.

Two acceptance criteria: thresholds come from data the profile already
keeps (no new grind counters), and the ceremony fires exactly once per
stage while surviving a mid-ceremony quit.

The third rule isn't in the acceptance list but matters more than either:
growth must never run backwards. A cat that shrinks because a kid's
alphabet was recalculated would be the single most upsetting bug in this
codebase.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, profiles  # noqa: E402


def a_profile(days=0, letters=6, growth=0, seen=0, with_cat=True):
    p = profiles._blank_profile("Test")
    p["days_played"] = days
    p["alphabet"] = adaptive.FREQ_ORDER[:letters]
    if with_cat:
        p["cat"] = {"seed": 4242, "name": "Mittens", "growth": growth}
        if seen:
            p["cat"]["growth_seen"] = seen
    return p


class TestThresholds(unittest.TestCase):
    def test_stages_and_thresholds_line_up(self):
        self.assertEqual(len(cat.GROWTH_STAGES), len(cat.GROWTH_DAYS))
        self.assertEqual(len(cat.GROWTH_STAGES), len(cat.GROWTH_LETTERS))

    def test_thresholds_only_ever_rise(self):
        self.assertEqual(cat.GROWTH_DAYS, sorted(cat.GROWTH_DAYS))
        self.assertEqual(cat.GROWTH_LETTERS, sorted(cat.GROWTH_LETTERS))

    def test_a_new_cat_is_a_kitten(self):
        self.assertEqual(cat.earned_growth(a_profile()), 0)

    def test_both_thresholds_are_required(self):
        """Days alone rewards leaving the Pi on; letters alone is a score."""
        self.assertEqual(cat.earned_growth(a_profile(days=99, letters=6)), 0)
        self.assertEqual(cat.earned_growth(a_profile(days=0, letters=26)), 0)
        self.assertEqual(cat.earned_growth(a_profile(days=10, letters=12)), 1)

    def test_each_stage_arrives_exactly_at_its_thresholds(self):
        for stage in range(1, len(cat.GROWTH_STAGES)):
            d, l = cat.GROWTH_DAYS[stage], cat.GROWTH_LETTERS[stage]
            self.assertEqual(cat.earned_growth(a_profile(d, l)), stage)
            self.assertLess(cat.earned_growth(a_profile(d - 1, l)), stage)
            self.assertLess(cat.earned_growth(a_profile(d, l - 1)), stage)

    def test_stages_cannot_be_skipped(self):
        """A huge alphabet with few days still only reaches what it earned."""
        for days in range(0, 120, 3):
            for letters in range(6, 27):
                got = cat.earned_growth(a_profile(days, letters))
                for s in range(1, got + 1):
                    self.assertGreaterEqual(days, cat.GROWTH_DAYS[s])
                    self.assertGreaterEqual(letters, cat.GROWTH_LETTERS[s])

    def test_the_top_stage_is_reachable_and_final(self):
        top = len(cat.GROWTH_STAGES) - 1
        p = a_profile(days=999, letters=26)
        self.assertEqual(cat.earned_growth(p), top)

    def test_no_new_counters_were_invented(self):
        """Thresholds read days_played and the alphabet, both pre-existing."""
        blank = profiles._blank_profile("X")
        self.assertIn("days_played", blank)
        self.assertIn("alphabet", blank)


class TestAdvancing(unittest.TestCase):
    def test_advancing_records_the_stage(self):
        p = a_profile(days=10, letters=12)
        self.assertEqual(cat.advance_growth(p), 1)
        self.assertEqual(cat.growth(p), 1)

    def test_advancing_twice_is_a_no_op(self):
        p = a_profile(days=10, letters=12)
        cat.advance_growth(p)
        self.assertIsNone(cat.advance_growth(p))

    def test_growth_never_regresses(self):
        p = a_profile(days=99, letters=26, growth=3)
        p["days_played"] = 0
        p["alphabet"] = adaptive.START_ALPHABET
        self.assertIsNone(cat.advance_growth(p))
        self.assertEqual(cat.growth(p), 3)

    def test_a_profile_with_no_cat_never_grows(self):
        p = a_profile(days=99, letters=26, with_cat=False)
        self.assertIsNone(cat.advance_growth(p))
        self.assertEqual(cat.growth(p), 0)

    def test_it_can_jump_more_than_one_stage_at_once(self):
        """A kid returning after months shouldn't be walked up one at a time."""
        p = a_profile(days=80, letters=26)
        self.assertEqual(cat.advance_growth(p), 3)

    def test_growth_survives_a_json_round_trip(self):
        p = a_profile(days=30, letters=20)
        cat.advance_growth(p)
        back = json.loads(json.dumps(p))
        self.assertEqual(cat.growth(back), cat.growth(p))


class TestCeremonyBookkeeping(unittest.TestCase):
    """'Ceremony fires exactly once per stage, survives mid-ceremony quit.'"""

    def test_a_fresh_stage_owes_a_ceremony(self):
        p = a_profile(days=10, letters=12)
        cat.advance_growth(p)
        self.assertEqual(cat.growth_unseen(p), 1)

    def test_marking_it_seen_clears_the_debt(self):
        p = a_profile(days=10, letters=12)
        cat.advance_growth(p)
        cat.mark_growth_seen(p, 1)
        self.assertIsNone(cat.growth_unseen(p))

    def test_an_interrupted_ceremony_is_still_owed(self):
        """Quitting halfway leaves 'seen' unwritten, so it replays."""
        p = a_profile(days=10, letters=12)
        cat.advance_growth(p)
        self.assertEqual(cat.growth_unseen(p), 1)   # quit here
        self.assertEqual(cat.growth_unseen(p), 1)   # ...still owed later

    def test_the_stage_is_kept_even_if_the_ceremony_never_runs(self):
        p = a_profile(days=10, letters=12)
        cat.advance_growth(p)
        self.assertEqual(cat.growth(p), 1)

    def test_seen_never_goes_backwards(self):
        p = a_profile(days=75, letters=26, growth=3, seen=3)
        cat.mark_growth_seen(p, 1)
        self.assertEqual(p["cat"]["growth_seen"], 3)

    def test_a_two_stage_jump_owes_only_the_stage_reached(self):
        p = a_profile(days=80, letters=26)
        cat.advance_growth(p)
        self.assertEqual(cat.growth_unseen(p), 3)
        cat.mark_growth_seen(p, 3)
        self.assertIsNone(cat.growth_unseen(p))

    def test_a_cat_less_profile_owes_nothing(self):
        self.assertIsNone(cat.growth_unseen(a_profile(with_cat=False)))

    def test_old_saves_without_the_seen_key_still_work(self):
        p = a_profile(days=10, letters=12, growth=1)
        self.assertEqual(cat.growth_unseen(p), 1)


class TestProgressReadout(unittest.TestCase):
    def test_it_reports_what_the_next_stage_needs(self):
        p = a_profile(days=4, letters=8)
        days, need_days, letters, need_letters = cat.growth_progress(p)
        self.assertEqual((days, letters), (4, 8))
        self.assertEqual((need_days, need_letters),
                         (cat.GROWTH_DAYS[1], cat.GROWTH_LETTERS[1]))

    def test_a_fully_grown_cat_has_nothing_pending(self):
        p = a_profile(days=999, letters=26, growth=3)
        self.assertIsNone(cat.growth_progress(p))

    def test_it_tracks_the_stored_stage_not_the_earned_one(self):
        p = a_profile(days=999, letters=26, growth=1)
        self.assertIsNotNone(cat.growth_progress(p))
        self.assertEqual(cat.growth_progress(p)[1], cat.GROWTH_DAYS[2])


class TestRenderingAcrossStages(unittest.TestCase):
    def test_every_stage_renders_every_pose(self):
        kitty = cat.Cat(4242, "Mittens")
        for stage in range(len(cat.GROWTH_STAGES)):
            for pose in cat.POSES:
                art = kitty.art(pose, stage)
                self.assertTrue(art, "%s g=%d" % (pose, stage))
                for row in art:
                    self.assertTrue(row.isascii(), row)

    def test_the_body_grows_at_the_adult_threshold(self):
        kitty = cat.Cat(4242, "Mittens")
        self.assertTrue(kitty.is_kitten(0))
        self.assertTrue(kitty.is_kitten(1))
        self.assertFalse(kitty.is_kitten(2))
        self.assertFalse(kitty.is_kitten(3))

    def test_a_grown_cat_is_bigger_than_a_kitten(self):
        kitty = cat.Cat(4242, "Mittens")
        self.assertGreater(kitty.height("sit", 2), kitty.height("sit", 0))

    def test_kid_facing_words_avoid_calling_a_cat_old(self):
        """Nothing in this game dies, and nothing should hint that it might."""
        for word in cat.GROWTH_WORDS.values():
            for bad in ("old", "elder", "ancient", "dying", "senior"):
                self.assertNotIn(bad, word.lower(), word)

    def test_every_stage_has_a_kid_facing_word(self):
        for stage in cat.GROWTH_STAGES:
            self.assertIn(stage, cat.GROWTH_WORDS)
            self.assertTrue(cat.GROWTH_WORDS[stage])


if __name__ == "__main__":
    unittest.main()
