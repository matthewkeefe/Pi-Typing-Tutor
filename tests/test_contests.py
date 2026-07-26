"""
The contest ladder -- issue #28.

The fairness constraint is the reason this module is shaped the way it
is: **ranks measure a kid against the game's bars, never against a
sibling.** Several tests exist purely to make sure no future edit
smuggles a comparison in, because that is the one thing this feature
could do that the rest of the design has spent seven phases avoiding.

The rest: bars generous at the bottom, an entry throttle that survives
restarts and a wrong clock, and ranks that only ever rise.
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import contests, profiles, scrapbook  # noqa: E402
from modes import contest, dash  # noqa: E402

TODAY = date(2026, 7, 26)


def a_profile(**over):
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0}
    p.update(over)
    return p


class TestLadderShape(unittest.TestCase):
    def test_five_cups_named_as_specced(self):
        names = [n for _k, n, _w, _a, _e in contests.CUPS]
        self.assertEqual(len(names), 5)
        for expect in ("Beginner", "Junior", "Expert", "Master", "Champion"):
            self.assertTrue(any(expect in n for n in names), expect)

    def test_every_bar_rises_up_the_ladder(self):
        for idx in (2, 3, 4):
            values = [row[idx] for row in contests.CUPS]
            self.assertEqual(values, sorted(values), idx)

    def test_the_first_rung_is_genuinely_generous(self):
        """
        A ladder whose bottom rung is out of reach isn't a ladder. The
        Beginner Cup should be winnable by a kid barely off the ground.
        """
        _k, _n, wpm, acc, endurance = contests.CUPS[0]
        self.assertLessEqual(wpm, 10.0)
        self.assertLessEqual(acc, 85.0)
        self.assertLessEqual(endurance, 12)

    def test_the_top_rung_matches_the_games_goal(self):
        """Champion should be the 40 wpm the whole engine is tuned for."""
        _k, _n, wpm, _a, _e = contests.CUPS[-1]
        self.assertAlmostEqual(wpm, 40.0, delta=1.0)

    def test_prizes_scale_and_are_never_negative(self):
        prizes = [contests.prize_fish(i) for i in range(len(contests.CUPS))]
        self.assertEqual(prizes, sorted(prizes))
        self.assertGreater(min(prizes), 0)


class TestJudging(unittest.TestCase):
    def test_all_three_trials_are_required(self):
        row = contests.CUPS[0]
        self.assertTrue(contests.passed(contests.judge(row, 9, 85, 12)))
        self.assertFalse(contests.passed(contests.judge(row, 5, 85, 12)))
        self.assertFalse(contests.passed(contests.judge(row, 9, 50, 12)))
        self.assertFalse(contests.passed(contests.judge(row, 9, 85, 2)))

    def test_exactly_on_the_bar_passes(self):
        _k, _n, wpm, acc, endurance = contests.CUPS[1]
        row = contests.CUPS[1]
        self.assertTrue(contests.passed(contests.judge(row, wpm, acc,
                                                       endurance)))

    def test_judging_needs_no_terminal(self):
        """Bars want arguing about and tuning, so they live away from UI."""
        self.assertTrue(contests.judge(contests.CUPS[0], 1, 1, 1))

    def test_the_tip_names_the_trial_never_the_kid(self):
        row = contests.CUPS[2]
        for results in (contests.judge(row, 1, 99, 99),
                        contests.judge(row, 99, 1, 99),
                        contests.judge(row, 99, 99, 1)):
            tip = contests.tip_for(row, results).lower()
            self.assertTrue(tip)
            for blame in ("you failed", "too slow", "bad", "poor", "worse"):
                self.assertNotIn(blame, tip, tip)


class TestRanksOnlyRise(unittest.TestCase):
    def test_winning_advances_the_rank(self):
        p = a_profile()
        self.assertEqual(contests.rank(p), 0)
        self.assertTrue(contests.award(p, 0))
        self.assertEqual(contests.rank(p), 1)

    def test_a_cup_cannot_be_won_twice(self):
        p = a_profile()
        contests.award(p, 0)
        self.assertIsNone(contests.award(p, 0))
        self.assertEqual(contests.rank(p), 1)

    def test_cups_are_climbed_in_order(self):
        p = a_profile()
        self.assertIsNone(contests.award(p, 3))
        self.assertEqual(contests.rank(p), 0)

    def test_a_rank_is_never_lost(self):
        p = a_profile()
        for i in range(len(contests.CUPS)):
            contests.award(p, i)
        top = contests.rank(p)
        for i in range(len(contests.CUPS)):
            contests.award(p, i)
        self.assertEqual(contests.rank(p), top)

    def test_the_ladder_ends_cleanly(self):
        p = a_profile()
        for i in range(len(contests.CUPS)):
            contests.award(p, i)
        self.assertIsNone(contests.next_cup(p))
        self.assertEqual(len(contests.won_cups(p)), len(contests.CUPS))

    def test_rank_survives_a_json_round_trip(self):
        p = a_profile()
        contests.award(p, 0)
        back = json.loads(json.dumps(p))
        self.assertEqual(contests.rank(back), 1)


class TestEntryThrottle(unittest.TestCase):
    def test_a_few_goes_a_day(self):
        p = a_profile()
        self.assertEqual(contests.entries_left(p, TODAY),
                         contests.MAX_ENTRIES_PER_DAY)
        for _ in range(contests.MAX_ENTRIES_PER_DAY):
            self.assertTrue(contests.take_entry(p, TODAY))
        self.assertFalse(contests.take_entry(p, TODAY))
        self.assertEqual(contests.entries_left(p, TODAY), 0)

    def test_the_throttle_is_in_the_specced_range(self):
        self.assertGreaterEqual(contests.MAX_ENTRIES_PER_DAY, 2)
        self.assertLessEqual(contests.MAX_ENTRIES_PER_DAY, 3)

    def test_it_resets_tomorrow(self):
        p = a_profile()
        for _ in range(contests.MAX_ENTRIES_PER_DAY):
            contests.take_entry(p, TODAY)
        self.assertTrue(contests.take_entry(p, TODAY + timedelta(days=1)))

    def test_it_survives_a_restart(self):
        p = a_profile()
        contests.take_entry(p, TODAY)
        back = json.loads(json.dumps(p))
        self.assertEqual(contests.entries_left(back, TODAY),
                         contests.MAX_ENTRIES_PER_DAY - 1)

    def test_a_wrong_clock_hands_entries_back_rather_than_locking_out(self):
        """
        Generous toward the kid on purpose. The throttle keeps this a
        highlight; it isn't there to police anyone, so a Pi with a bad
        RTC should never leave a kid unable to play.
        """
        p = a_profile()
        for _ in range(contests.MAX_ENTRIES_PER_DAY):
            contests.take_entry(p, TODAY)
        self.assertEqual(contests.entries_left(p, TODAY - timedelta(days=30)),
                         contests.MAX_ENTRIES_PER_DAY)

    def test_old_saves_migrate(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        self.assertEqual(contests.rank(p), 0)
        self.assertEqual(contests.entries_left(p, TODAY),
                         contests.MAX_ENTRIES_PER_DAY)


class TestNoSiblingComparison(unittest.TestCase):
    """
    The fairness invariant. A rank is a statement about a kid and the
    game's bar; it must never become a statement about them and their
    sister. Same rule that governs ghost racing.
    """

    def _sources(self):
        out = []
        for mod in (contests, contest, dash):
            with open(mod.__file__, encoding="utf-8") as fh:
                out.append((mod.__name__, fh.read().split('"""', 2)[-1]))
        return out

    def test_nothing_loads_another_profile(self):
        for name, body in self._sources():
            for banned in ("load_all", "all_profiles", "other_profile"):
                self.assertNotIn(banned, body, "%s: %s" % (name, banned))

    def test_no_leaderboard_or_ranking_language(self):
        for name, body in self._sources():
            for banned in ("leaderboard", "versus", "faster than",
                           "beat everyone", "top player"):
                self.assertNotIn(banned, body.lower(), "%s: %s" % (name, banned))

    def test_losing_costs_nothing_but_the_entry(self):
        for name, body in self._sources():
            for banned in ("fish -=", "rank -=", "current_streak",
                           "rank\"] = rank - "):
                self.assertNotIn(banned, body, "%s: %s" % (name, banned))


class TestRewards(unittest.TestCase):
    def test_a_win_stamps_a_ribbon_into_the_scrapbook(self):
        p = a_profile()
        ribbon = contests.award(p, 0)
        scrapbook.award_ribbon(p, ribbon)
        self.assertIn(ribbon, scrapbook.ribbons(p))

    def test_the_ribbons_page_appears_once_one_is_won(self):
        p = a_profile()
        self.assertNotIn("Ribbons", [t for t, _ in scrapbook.albums(p)])
        scrapbook.award_ribbon(p, contests.award(p, 0))
        self.assertIn("Ribbons", [t for t, _ in scrapbook.albums(p)])

    def test_ribbon_names_are_distinct_per_cup(self):
        names = set()
        p = a_profile()
        for i in range(len(contests.CUPS)):
            names.add(contests.award(p, i))
        self.assertEqual(len(names), len(contests.CUPS))


class TestDailyDash(unittest.TestCase):
    def test_it_is_hidden_until_a_cup_is_won(self):
        p = a_profile()
        self.assertFalse(dash.available(p))
        contests.award(p, 0)
        self.assertTrue(dash.available(p))

    def test_it_appears_in_the_arcade_once_unlocked(self):
        import main
        p = a_profile()
        self.assertNotIn("Daily Dash",
                         [l for _m, _k, l, _b in main.arcade_for(p)])
        contests.award(p, 0)
        self.assertIn("Daily Dash",
                      [l for _m, _k, l, _b in main.arcade_for(p)])

    def test_it_reuses_the_contest_burst(self):
        """#28: the trial round should double as a free-play mode."""
        self.assertIs(dash.daily_dash, contest.daily_dash)

    def test_contests_are_always_available(self):
        self.assertTrue(contest.available(a_profile()))


if __name__ == "__main__":
    unittest.main()
