"""
Graduation, stasis and the second kitten -- Phase 9 (#31-#34).

Two promises carry most of the weight:

**The first cat never goes anywhere.** Not replaced, not retired, not
traded. A kid who has spent a year with an animal that has their name on
it is not being asked to give it up for a newer one.

**A shelved cat is locked.** Status saved and not changed: it does not
get hungry, drift toward wary, or age. Switching back finds it exactly as
it was, however long it has been. That is what lets a second cat exist
without the daily loop doubling.
"""

import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (adaptive, cat, graduation, profiles,  # noqa: E402
                  stasis)

NOW = datetime(2026, 7, 26, 12, 0, 0)


def a_profile(**over):
    p = profiles._blank_profile("Test")
    p["cat"] = cat.blank_cat_data(4242, "Mittens", "2026-01-01", now=NOW)
    p.update(over)
    return p


def a_graduate():
    """Everything mastered and ten fast sessions behind them."""
    p = a_profile()
    p["alphabet"] = adaptive.FREQ_ORDER
    p["keys"] = {c: {"n": 99, "conf": 0.99, "ms": adaptive.MASTER_MS - 20}
                 for c in adaptive.FREQ_ORDER}
    p["history"] = [{"date": "2026-07-01", "mode": "dash", "wpm": 42.0,
                     "accuracy": 97.0, "words": 40, "seconds": 60}
                    for _ in range(graduation.GRADUATE_SESSIONS)]
    return p


class TestWinCondition(unittest.TestCase):
    def test_a_new_kid_has_not_graduated(self):
        self.assertFalse(graduation.qualifies(a_profile()))

    def test_both_conditions_are_required(self):
        fast_only = a_profile()
        fast_only["history"] = [{"wpm": 60.0, "words": 40}
                                for _ in range(graduation.GRADUATE_SESSIONS)]
        self.assertTrue(graduation.fast_enough(fast_only))
        self.assertFalse(graduation.qualifies(fast_only))

        mastered_only = a_graduate()
        mastered_only["history"] = []
        self.assertTrue(graduation.mastered_everything(mastered_only))
        self.assertFalse(graduation.qualifies(mastered_only))

    def test_a_full_graduate_qualifies(self):
        self.assertTrue(graduation.qualifies(a_graduate()))

    def test_one_brilliant_run_does_not_graduate_anybody(self):
        """
        best_wpm is a peak and is trivially gamed by one short burst.
        Graduation has to mean current, repeatable ability.
        """
        p = a_graduate()
        p["history"] = [{"wpm": 5.0, "words": 40}
                        for _ in range(graduation.GRADUATE_SESSIONS - 1)]
        p["history"].append({"wpm": 200.0, "words": 40})
        self.assertFalse(graduation.fast_enough(p))

    def test_one_bad_afternoon_does_not_undo_it(self):
        p = a_graduate()
        p["history"][-1] = {"wpm": 3.0, "words": 40}
        self.assertTrue(graduation.fast_enough(p), "median should absorb it")

    def test_short_sessions_are_not_evidence(self):
        p = a_graduate()
        p["history"] = [{"wpm": 99.0, "words": 1}
                        for _ in range(graduation.GRADUATE_SESSIONS * 2)]
        self.assertIsNone(graduation.recent_wpm(p))
        self.assertFalse(graduation.fast_enough(p))

    def test_a_thin_history_cannot_graduate(self):
        p = a_graduate()
        p["history"] = p["history"][:3]
        self.assertIsNone(graduation.recent_wpm(p))

    def test_the_goal_matches_the_engines_own_target(self):
        self.assertAlmostEqual(graduation.GRADUATE_WPM,
                               adaptive.MASTER_WPM, delta=0.01)

    def test_it_never_regresses_once_latched(self):
        p = a_graduate()
        self.assertTrue(graduation.mark_graduated(p))
        p["history"] = []
        p["keys"] = {}
        self.assertTrue(graduation.graduated(p))

    def test_it_latches_only_once(self):
        p = a_graduate()
        self.assertTrue(graduation.mark_graduated(p))
        self.assertFalse(graduation.mark_graduated(p))

    def test_check_stops_firing_after_it_is_marked(self):
        p = a_graduate()
        self.assertTrue(graduation.check(p))
        graduation.mark_graduated(p)
        self.assertFalse(graduation.check(p))

    def test_progress_is_hidden_until_it_is_near(self):
        """
        Before it's plausibly close it's noise -- and worse, it turns the
        whole game into a progress bar pointed at one number.
        """
        self.assertFalse(graduation.worth_showing(a_profile()))
        self.assertTrue(graduation.worth_showing(a_graduate()))


class TestStasis(unittest.TestCase):
    """A shelved cat is locked: status saved and not changed."""

    def test_gauges_are_identical_after_a_long_shelving(self):
        p = a_profile()
        cat.stamp_care(p, "food", NOW)
        before = cat.gauges(p, NOW)

        p["shelf"] = [cat.blank_cat_data(77, "Smudge", "2026-06-01", now=NOW)]
        stasis.freeze(p["shelf"][0], NOW)
        stasis.switch_to(p, 0, NOW)                       # away we go
        later = NOW + timedelta(days=200)
        stasis.switch_to(p, 0, later)                     # and back

        self.assertEqual(p["cat"]["name"], "Mittens")
        self.assertEqual(cat.gauges(p, later), before)

    def test_a_shelved_cat_does_not_drift_toward_wary(self):
        p = a_profile()
        cat.stamp_care(p, "food", NOW)
        p["shelf"] = [cat.blank_cat_data(77, "Smudge", "2026-06-01", now=NOW)]
        stasis.switch_to(p, 0, NOW)
        later = NOW + timedelta(days=90)
        stasis.switch_to(p, 0, later)
        self.assertFalse(cat.is_wary(p, later))

    def test_a_shelved_cat_does_not_age(self):
        p = a_profile()
        p["cat"]["days_active"] = 5
        p["shelf"] = [cat.blank_cat_data(77, "Smudge", "2026-06-01", now=NOW)]
        stasis.switch_to(p, 0, NOW)
        for _ in range(50):
            stasis.touch_active_day(p)
        stasis.switch_to(p, 0, NOW + timedelta(days=50))
        self.assertEqual(p["cat"]["days_active"], 5)

    def test_growth_reads_the_live_cats_own_days(self):
        p = a_profile(days_played=99)
        p["cat"]["days_active"] = 2
        self.assertEqual(stasis.days_active(p), 2)

    def test_a_one_cat_profile_is_unchanged(self):
        """days_active absent -> fall back to days_played, so nothing moves."""
        p = a_profile(days_played=40)
        p["cat"].pop("days_active", None)
        self.assertEqual(stasis.days_active(p), 40)

    def test_a_clock_going_backwards_does_not_age_a_cat(self):
        p = a_profile()
        cat.stamp_care(p, "food", NOW)
        before = cat.gauges(p, NOW)
        p["shelf"] = [cat.blank_cat_data(77, "Smudge", "2026-06-01", now=NOW)]
        stasis.switch_to(p, 0, NOW)
        stasis.switch_to(p, 0, NOW - timedelta(days=30))
        self.assertEqual(cat.gauges(p, NOW), before)

    def test_a_woken_cat_with_no_care_history_is_not_called_neglected(self):
        """Same lesson as Phase 3: no timestamps is not evidence of absence."""
        p = a_profile()
        p["cat"]["care"] = {}
        p["shelf"] = [cat.blank_cat_data(77, "Smudge", "2026-06-01", now=NOW)]
        stasis.switch_to(p, 0, NOW)
        later = NOW + timedelta(days=400)
        stasis.switch_to(p, 0, later)
        self.assertFalse(cat.is_wary(p, later))

    def test_everything_survives_a_json_round_trip(self):
        p = a_profile()
        p["shelf"] = [cat.blank_cat_data(77, "Smudge", "2026-06-01", now=NOW)]
        stasis.switch_to(p, 0, NOW)
        back = json.loads(json.dumps(p))
        self.assertEqual(stasis.count(back), 2)
        self.assertEqual(back["cat"]["name"], "Smudge")


class TestFirstCatNeverGoesAnywhere(unittest.TestCase):
    """The non-negotiable of the whole second-cat design."""

    def test_adding_a_cat_shelves_the_old_one(self):
        p = a_profile()
        first = p["cat"]["seed"]
        stasis.add_cat(p, cat.blank_cat_data(77, "Kit", "2026-07-26", now=NOW),
                       NOW)
        self.assertEqual(p["cat"]["seed"], 77)
        self.assertIn(first, [c["seed"] for c in stasis.shelf(p)])

    def test_the_original_keeps_its_name_growth_and_tricks(self):
        p = a_profile()
        p["cat"]["growth"] = 3
        p["cat"]["tricks"] = ["pounce", "spin"]
        stasis.add_cat(p, cat.blank_cat_data(77, "Kit", "2026-07-26", now=NOW),
                       NOW)
        shelved = stasis.shelf(p)[0]
        self.assertEqual(shelved["name"], "Mittens")
        self.assertEqual(shelved["growth"], 3)
        self.assertEqual(shelved["tricks"], ["pounce", "spin"])

    def test_switching_never_loses_a_cat(self):
        p = a_profile()
        stasis.add_cat(p, cat.blank_cat_data(77, "Kit", "2026-07-26", now=NOW),
                       NOW)
        seeds = {c["seed"] for _i, c, _a in stasis.all_cats(p)}
        for _ in range(6):
            stasis.switch_to(p, 0, NOW)
            self.assertEqual({c["seed"] for _i, c, _a in stasis.all_cats(p)},
                             seeds)

    def test_there_is_never_a_duplicate_of_a_cat(self):
        p = a_profile()
        stasis.add_cat(p, cat.blank_cat_data(77, "Kit", "2026-07-26", now=NOW),
                       NOW)
        for _ in range(4):
            stasis.switch_to(p, 0, NOW)
            seeds = [c["seed"] for _i, c, _a in stasis.all_cats(p)]
            self.assertEqual(len(seeds), len(set(seeds)))

    def test_no_code_path_removes_a_cat(self):
        with open(stasis.__file__, encoding="utf-8") as fh:
            body = fh.read().split('"""', 2)[-1]
        for banned in ("shelf(profile).remove", "del profile", "cats.clear"):
            self.assertNotIn(banned, body, banned)

    def test_a_bad_index_changes_nothing(self):
        p = a_profile()
        before = p["cat"]["seed"]
        self.assertIsNone(stasis.switch_to(p, 5, NOW))
        self.assertEqual(p["cat"]["seed"], before)


class TestInheritance(unittest.TestCase):
    def test_a_kitten_shares_its_parents_coat_and_colour(self):
        parent = cat.Cat(4242, "Mittens")
        kit = cat.Cat(77, "Kit", parent=4242)
        self.assertEqual(kit.fur, parent.fur)
        self.assertEqual(kit.colors, parent.colors)

    def test_but_is_its_own_cat_otherwise(self):
        """A kitten that inherited everything is a copy with a new name."""
        differs = 0
        for seed in range(2, 60):
            kit = cat.Cat(seed, "Kit", parent=4242)
            solo = cat.Cat(seed, "Kit")
            if (kit.personality, kit.ears, kit.build, kit.tail) == \
               (solo.personality, solo.ears, solo.build, solo.tail):
                differs += 1
        self.assertGreater(differs, 40,
                           "temperament and shape should come from own seed")

    def test_inheritance_survives_reconstruction_from_the_save(self):
        p = a_profile()
        data = cat.blank_cat_data(77, "Kit", "2026-07-26", now=NOW,
                                  parent=4242)
        stasis.add_cat(p, data, NOW)
        back = json.loads(json.dumps(p))
        self.assertEqual(cat.Cat.from_profile(back).fur,
                         cat.Cat(4242, "Mittens").fur)

    def test_a_parentless_cat_is_completely_unchanged(self):
        """Existing cats must not shift a pixel because this exists."""
        for seed in (1, 42, 4242, 999999):
            a = cat.Cat(seed, "X")
            b = cat.Cat(seed, "X", parent=None)
            self.assertEqual(a.art("sit"), b.art("sit"))
            self.assertEqual((a.fur, a.colors, a.personality),
                             (b.fur, b.colors, b.personality))

    def test_kitten_genes_stay_lateral(self):
        """No pool the first cat couldn't have drawn from (guard 3)."""
        kit = cat.Cat(77, "Kit", parent=4242)
        self.assertIn(kit.fur, cat.FUR_NAMES)
        self.assertIn(kit.personality, cat.PERSONALITIES)
        self.assertIn(kit.colors, cat.COLOR_COMBOS)


if __name__ == "__main__":
    unittest.main()
