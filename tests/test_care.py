"""
Tests for the care gauges, moods and tricks.

The gauges are pure date math with no stored state, which is exactly why
they're testable here without a terminal -- and why a week away can't
corrupt anything.
"""

import copy
import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, engine  # noqa: E402

NOW = datetime(2026, 7, 26, 18, 0, 0)


def profile_with(care=None, **extra):
    p = {"name": "Kid", "cat": cat.blank_cat_data(42, "Mochi", "2026-07-01")}
    p["cat"]["care"] = dict(care or {})
    p.update(extra)
    return p


def hours_ago(h):
    return (NOW - timedelta(hours=h)).isoformat(timespec="seconds")


def all_cared(hours=1):
    return {t: hours_ago(hours) for t in cat.CARE_TASKS}


class TestGauges(unittest.TestCase):
    def test_never_done_is_empty(self):
        p = profile_with()
        for task in cat.CARE_TASKS:
            self.assertEqual(cat.gauge(p, task, NOW), 0.0)

    def test_just_done_is_full(self):
        p = profile_with(all_cared(0))
        self.assertEqual(cat.gauges(p, NOW), {t: 1.0 for t in cat.CARE_TASKS})

    def test_stays_full_through_the_grace_window(self):
        p = profile_with({"food": hours_ago(cat.GAUGE_FULL_HOURS - 0.1)})
        self.assertEqual(cat.gauge(p, "food", NOW), 1.0)

    def test_drifts_down_then_bottoms_out(self):
        midpoint = (cat.GAUGE_FULL_HOURS + cat.GAUGE_EMPTY_HOURS) / 2
        p = profile_with({"food": hours_ago(midpoint)})
        self.assertAlmostEqual(cat.gauge(p, "food", NOW), 0.5, places=2)
        p = profile_with({"food": hours_ago(cat.GAUGE_EMPTY_HOURS + 100)})
        self.assertEqual(cat.gauge(p, "food", NOW), 0.0)

    def test_never_goes_below_empty(self):
        """The floor is 'wants attention'. There is nothing under it."""
        p = profile_with({"food": hours_ago(24 * 365)})
        self.assertEqual(cat.gauge(p, "food", NOW), 0.0)

    def test_a_backwards_clock_does_not_neglect_the_cat(self):
        """
        The Pi has no network time and may have no RTC battery. A clock
        that jumped backwards must not make a cared-for cat look starved.
        """
        future = (NOW + timedelta(days=3)).isoformat(timespec="seconds")
        p = profile_with({t: future for t in cat.CARE_TASKS})
        self.assertEqual(cat.gauges(p, NOW), {t: 1.0 for t in cat.CARE_TASKS})

    def test_bare_dates_still_parse(self):
        p = profile_with({"food": "2026-07-26"})
        self.assertGreater(cat.gauge(p, "food", NOW), 0.0)
        self.assertTrue(cat.done_today(p, "food", date(2026, 7, 26)))

    def test_garbage_stamps_are_shrugged_off(self):
        for junk in ("", None, "not a date", 12345, "2026-13-45"):
            p = profile_with({"food": junk})
            self.assertEqual(cat.gauge(p, "food", NOW), 0.0)
            self.assertFalse(cat.done_today(p, "food", NOW.date()))

    def test_needs_lists_only_unfilled(self):
        p = profile_with({"food": hours_ago(0), "water": hours_ago(0)})
        self.assertEqual(cat.needs(p, NOW), ["pets", "play", "clean"])

    def test_bars_render_at_both_ends(self):
        self.assertEqual(cat.gauge_bar(1.0), "[##########]")
        self.assertEqual(cat.gauge_bar(0.0), "[----------]")
        self.assertEqual(len(cat.gauge_bar(0.37)), 12)


class TestDailyCare(unittest.TestCase):
    def test_done_today_is_calendar_based(self):
        p = profile_with({"food": hours_ago(1)})
        self.assertTrue(cat.done_today(p, "food", NOW.date()))
        self.assertFalse(cat.done_today(p, "food", NOW.date() + timedelta(days=1)))

    def test_all_five_opens_the_gate(self):
        p = profile_with(all_cared(1))
        self.assertTrue(cat.care_done_today(p, NOW.date()))
        self.assertEqual(cat.tasks_left_today(p, NOW.date()), [])

    def test_one_missing_keeps_it_shut(self):
        care = all_cared(1)
        del care["clean"]
        p = profile_with(care)
        self.assertFalse(cat.care_done_today(p, NOW.date()))
        self.assertEqual(cat.tasks_left_today(p, NOW.date()), ["clean"])

    def test_stamping_marks_it_done(self):
        p = profile_with()
        cat.stamp_care(p, "food", NOW)
        self.assertTrue(cat.done_today(p, "food", NOW.date()))
        self.assertEqual(cat.gauge(p, "food", NOW), 1.0)

    def test_stamping_works_on_a_profile_with_no_cat_block(self):
        p = {"name": "Kid"}
        cat.stamp_care(p, "food", NOW)
        self.assertIn("food", p["cat"]["care"])


class TestMood(unittest.TestCase):
    def test_full_care_is_thriving(self):
        self.assertEqual(cat.mood(profile_with(all_cared(0)), NOW), "thriving")

    def test_no_care_is_missing_you(self):
        self.assertEqual(cat.mood(profile_with(), NOW), "missing")

    def test_mood_drives_a_real_pose(self):
        for name in cat.MOODS:
            self.assertIn(cat.mood_pose(name), cat.POSES)

    def test_a_week_away_costs_nothing_but_gauges(self):
        """
        The whole point of freeze-don't-reverse: come back after a week
        and the cat is asleep and pleased to see you, not damaged, and
        every earned thing is exactly where it was left.
        """
        before = profile_with(all_cared(1), fish=120,
                              current_streak=9, badges=["b1", "b2"])
        before["cat"]["tricks"] = ["pounce", "spin"]
        before["cat"]["growth"] = 2
        after = copy.deepcopy(before)

        later = NOW + timedelta(days=7)
        self.assertEqual(cat.mood(after, later), "missing")
        self.assertEqual(cat.mood_pose(cat.mood(after, later)), "sleep")
        # nothing was consumed by the absence -- the save is untouched
        self.assertEqual(after, before)

    def test_wary_only_after_days_of_nobody(self):
        self.assertFalse(cat.is_wary(profile_with(all_cared(1)), NOW))
        self.assertFalse(
            cat.is_wary(profile_with({"food": hours_ago(24 * 2)}), NOW))
        self.assertTrue(
            cat.is_wary(profile_with({"food": hours_ago(24 * 5)}), NOW))

    def test_a_just_hatched_kitten_is_neither_wary_nor_missing_you(self):
        """
        With no care stamps at all the gauges are empty, but the cat was
        born a minute ago. Empty gauges are not the same as absence, and
        a brand-new kitten must not greet its kid looking abandoned.
        """
        fresh = profile_with()
        fresh["cat"]["hatched"] = NOW.date().isoformat()
        self.assertFalse(cat.is_wary(fresh, NOW))
        self.assertEqual(cat.mood(fresh, NOW), "hopeful")
        self.assertEqual(cat.mood_pose(cat.mood(fresh, NOW)), "sit")

    def test_an_old_cat_nobody_fed_is_wary(self):
        stale = profile_with()  # hatched 2026-07-01, never cared for
        self.assertTrue(cat.is_wary(stale, NOW))
        cat.stamp_care(stale, "pets", NOW)
        self.assertFalse(cat.is_wary(stale, NOW))


class TestTricks(unittest.TestCase):
    def test_a_letter_always_earns_the_same_trick(self):
        self.assertEqual(cat.trick_for_letter("r"), cat.trick_for_letter("r"))
        self.assertIsNone(cat.trick_for_letter("!"))

    def test_every_letter_maps_to_a_trick(self):
        for ch in "abcdefghijklmnopqrstuvwxyz":
            self.assertIn(cat.trick_for_letter(ch), cat.TRICKS)

    def test_learning_is_additive_and_idempotent(self):
        p = profile_with()
        first = cat.learn_trick(p, "e")
        self.assertIsNotNone(first)
        self.assertEqual(p["cat"]["tricks"], [first])
        self.assertIsNone(cat.learn_trick(p, "e"))
        self.assertEqual(p["cat"]["tricks"], [first])

    def test_tricks_are_distinct_across_the_alphabet(self):
        learned = {cat.trick_for_letter(c) for c in "abcdefghijklmnopqrstuvwxyz"}
        self.assertEqual(len(learned), 26)


class TestEvenness(unittest.TestCase):
    def test_metronome_scores_high(self):
        self.assertGreater(engine.evenness([200.0] * 20), 0.95)

    def test_lurching_scores_low(self):
        self.assertLess(engine.evenness([50, 900, 60, 1200, 40, 800] * 3), 0.5)

    def test_too_little_data_is_zero_not_a_crash(self):
        self.assertEqual(engine.evenness([]), 0.0)
        self.assertEqual(engine.evenness([100.0]), 0.0)

    def test_bounded(self):
        for sample in ([1e-9] * 10, [1e6] * 10, [1, 1000] * 10):
            self.assertGreaterEqual(engine.evenness(sample), 0.0)
            self.assertLessEqual(engine.evenness(sample), 1.0)

    def test_session_records_intervals(self):
        s = engine.Session()
        for _ in range(5):
            s.keystroke(True, ch="e")
        self.assertEqual(len(s.intervals), 4)


if __name__ == "__main__":
    unittest.main()
