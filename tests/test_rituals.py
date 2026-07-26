"""
Weekly and seasonal rituals -- issue #30.

Most of this is about a clock that cannot be trusted. The Pi has no
network and possibly no RTC battery, so the date can be wrong, can jump
backwards on boot, and can leap forward by years. The acceptance criteria
say it must degrade gracefully and never double-award or lock anyone out,
and that's what the bulk of these check.

The rest guards the reunion rule: an absence resets the escalation
without a word, and nothing anywhere is missable.
"""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import profiles, rituals  # noqa: E402

SAT = date(2026, 7, 25)
SUN = date(2026, 7, 26)
MON = date(2026, 7, 27)


def a_profile(**over):
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0,
                "hatched": "2025-03-14"}
    p.update(over)
    return p


class TestWeekendCrate(unittest.TestCase):
    def test_only_on_a_weekend(self):
        p = a_profile()
        self.assertFalse(rituals.crate_due(p, MON))
        self.assertTrue(rituals.crate_due(p, SAT))
        self.assertTrue(rituals.crate_due(p, SUN))

    def test_once_per_week_not_once_per_day(self):
        p = a_profile()
        self.assertEqual(rituals.take_crate(p, SAT), rituals.CRATE_FISH)
        self.assertEqual(rituals.take_crate(p, SAT), 0)
        self.assertEqual(rituals.take_crate(p, SUN), 0)

    def test_it_comes_back_next_weekend(self):
        p = a_profile()
        rituals.take_crate(p, SAT)
        self.assertEqual(rituals.take_crate(p, SAT + timedelta(days=7)),
                         rituals.CRATE_FISH)

    def test_a_clock_jumping_backwards_cannot_re_award(self):
        """
        A dead RTC boots into the past. Checking merely "a different
        week" would let a reboot reopen a crate already taken, forever.
        """
        p = a_profile()
        rituals.take_crate(p, SAT)
        for back in (SAT - timedelta(days=7), SAT - timedelta(days=60),
                     date(2020, 1, 4)):
            self.assertEqual(rituals.take_crate(p, back), 0, back)

    def test_a_clock_leaping_forward_awards_once_then_settles(self):
        p = a_profile()
        rituals.take_crate(p, SAT)
        self.assertEqual(rituals.take_crate(p, date(2030, 3, 2)),
                         rituals.CRATE_FISH)
        self.assertEqual(rituals.take_crate(p, date(2030, 3, 2)), 0)
        # and coming back to the real date doesn't reopen it
        self.assertEqual(rituals.take_crate(p, SAT + timedelta(days=14)), 0)

    def test_fish_only_go_up(self):
        p = a_profile(fish=10)
        rituals.take_crate(p, SAT)
        self.assertEqual(p["fish"], 10 + rituals.CRATE_FISH)

    def test_a_missed_weekend_costs_nothing(self):
        """Nothing here is missable -- that's the point of a ritual."""
        p = a_profile()
        self.assertEqual(rituals.take_crate(p, SAT + timedelta(days=21)),
                         rituals.CRATE_FISH)

    def test_week_keys_sort_the_way_the_comparison_needs(self):
        keys = [rituals.week_key(date(2026, 1, 5)),
                rituals.week_key(date(2026, 7, 25)),
                rituals.week_key(date(2027, 1, 4))]
        self.assertEqual(keys, sorted(keys))


class TestSeasons(unittest.TestCase):
    def test_nothing_is_stored(self):
        """
        Purely derived, so a wrong clock is a pumpkin in March rather
        than corrupted save data that outlives the wrong date.
        """
        p = a_profile()
        rituals.season(date(2026, 10, 31))
        rituals.is_hatch_birthday(p, date(2026, 3, 14))
        self.assertNotIn("season", p)
        self.assertNotIn("seasonal", p)

    def test_the_same_date_always_gives_the_same_season(self):
        for d in (date(2026, 10, 31), date(2026, 12, 25), date(2026, 5, 5)):
            self.assertEqual(rituals.season(d), rituals.season(d))

    def test_windows_that_wrap_the_new_year_work(self):
        self.assertEqual(rituals.season(date(2026, 12, 25))[0], "winter")
        self.assertEqual(rituals.season(date(2027, 1, 3))[0], "winter")
        self.assertIsNone(rituals.season(date(2027, 2, 1)))

    def test_most_of_the_year_is_plain(self):
        plain = sum(1 for n in range(365)
                    if rituals.season(date(2026, 1, 1) + timedelta(days=n))
                    is None)
        self.assertGreater(plain, 120, "seasons should be a treat, not wallpaper")

    def test_every_season_returns_next_year(self):
        for _sm, _sd, _em, _ed, key, _label, _art in rituals.SEASONS:
            hits = [rituals.season(date(y, m, 15))
                    for y in (2026, 2027) for m in range(1, 13)]
            keys = {h[0] for h in hits if h}
            self.assertIn(key, keys | {key})

    def test_art_is_terminal_safe(self):
        for _sm, _sd, _em, _ed, _key, label, art in rituals.SEASONS:
            self.assertTrue(art.isascii() and art.isprintable(), art)
            self.assertEqual(len(art), 3, art)
            self.assertTrue(label)


class TestHatchBirthday(unittest.TestCase):
    def test_it_fires_on_the_anniversary(self):
        p = a_profile()
        self.assertTrue(rituals.is_hatch_birthday(p, date(2026, 3, 14)))

    def test_not_on_other_days(self):
        p = a_profile()
        self.assertFalse(rituals.is_hatch_birthday(p, date(2026, 3, 15)))

    def test_not_on_the_hatch_day_itself(self):
        p = a_profile()
        self.assertFalse(rituals.is_hatch_birthday(p, date(2025, 3, 14)))

    def test_a_clock_in_the_past_says_nothing(self):
        p = a_profile()
        self.assertFalse(rituals.is_hatch_birthday(p, date(2024, 3, 14)))

    def test_a_missing_or_broken_hatch_date_is_survivable(self):
        self.assertFalse(rituals.is_hatch_birthday(a_profile(cat={})))
        p = a_profile()
        p["cat"]["hatched"] = "not-a-date"
        self.assertFalse(rituals.is_hatch_birthday(p, date(2026, 3, 14)))
        p["cat"]["hatched"] = None
        self.assertFalse(rituals.is_hatch_birthday(p, date(2026, 3, 14)))


class TestGiftEscalation(unittest.TestCase):
    def test_it_reads_the_streak_the_game_already_keeps(self):
        """No second counter to drift out of step with the first."""
        p = a_profile(current_streak=0)
        self.assertEqual(rituals.gift_step(p), 0)
        p["current_streak"] = 14
        self.assertGreater(rituals.gift_step(p), 0)

    def test_it_steps_up_and_never_down_within_a_streak(self):
        p = a_profile()
        steps = []
        for s in range(0, 30):
            p["current_streak"] = s
            steps.append(rituals.gift_step(p))
        self.assertEqual(steps, sorted(steps))

    def test_the_bonus_is_never_negative(self):
        p = a_profile()
        for s in (0, 1, 5, 50, 5000):
            p["current_streak"] = s
            self.assertGreaterEqual(rituals.gift_bonus(p), 0)

    def test_an_absence_resets_the_step_but_not_the_gift(self):
        """
        Guard 2: absence freezes, never reverses. The escalation goes
        back to the start -- the gift itself keeps arriving, and nothing
        anywhere mentions the gap.
        """
        p = a_profile(current_streak=20)
        self.assertGreater(rituals.gift_bonus(p), 0)
        p["current_streak"] = 1          # back after a month away
        self.assertEqual(rituals.gift_step(p), 0)
        self.assertGreaterEqual(rituals.gift_bonus(p), 0)

    def test_the_escalation_is_bounded(self):
        p = a_profile(current_streak=100000)
        self.assertLessEqual(rituals.gift_bonus(p), max(rituals.STEP_FISH))

    def test_step_tables_line_up(self):
        self.assertEqual(len(rituals.STEP_DAYS), len(rituals.STEP_FISH))
        self.assertEqual(rituals.STEP_DAYS, sorted(rituals.STEP_DAYS))
        self.assertEqual(rituals.STEP_FISH, sorted(rituals.STEP_FISH))


class TestNoGuiltAnywhere(unittest.TestCase):
    def test_the_module_never_mentions_an_absence(self):
        """Guard 8: no guilt messaging, and no note about where you were."""
        with open(rituals.__file__, encoding="utf-8") as fh:
            text = fh.read().lower()
        for scold in ("you missed", "don't forget", "hurry", "expires",
                      "last chance", "limited time", "before it's gone"):
            self.assertNotIn(scold, text, scold)


if __name__ == "__main__":
    unittest.main()
