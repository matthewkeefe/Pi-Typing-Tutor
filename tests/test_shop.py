"""
Tests for the shop, treat effects, litter insurance and the wary state.

Several of these exist to hold design guards rather than to catch
regressions in logic: that fish never go negative, that no item makes
typing easier, that a swat costs nothing but time.
"""

import os
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, profiles, shop  # noqa: E402

MONDAY = date(2026, 7, 27)


def fresh(fish=0, **extra):
    p = profiles._blank_profile("Kid")
    p["fish"] = fish
    p["cat"] = cat.blank_cat_data(42, "Mochi", "2026-07-01")
    p.update(extra)
    return p


class TestCatalog(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [i["id"] for i in shop.CATALOG]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_item_is_displayable(self):
        for item in shop.CATALOG:
            for field in ("id", "kind", "name", "price", "blurb", "says"):
                self.assertIn(field, item, item["id"])
            self.assertTrue(item["name"].isascii())
            self.assertTrue(item["says"].isascii())
            self.assertGreater(item["price"], 0)

    def test_decor_art_fits_the_menu_corner(self):
        for item in shop.CATALOG:
            for row in item.get("art", []):
                self.assertLessEqual(len(row), 8, item["id"])
                self.assertTrue(all(32 <= ord(c) < 127 for c in row))

    def test_everyday_prices_are_days_not_weeks(self):
        """A full care day is roughly 50 fish; nothing routine may exceed that much."""
        for item in shop.CATALOG:
            if item.get("dream"):
                continue
            self.assertLessEqual(item["price"], 90, item["id"])

    def test_the_dream_item_is_worth_saving_for(self):
        self.assertGreater(shop.DREAM_ITEM["price"], 500)

    def test_treats_are_buffers_not_shortcuts(self):
        """No effect may complete practice or type anything for a kid."""
        allowed = {shop.EFFECT_SHIELD, shop.EFFECT_COMBO_SAVER, shop.EFFECT_BONUS}
        for item in shop.CATALOG:
            if item["kind"] == shop.KIND_TREAT:
                self.assertIn(item["effect"], allowed, item["id"])


class TestRotation(unittest.TestCase):
    def test_same_week_same_shelf(self):
        p = fresh()
        first = [i["id"] for i in shop.available_this_week(p, MONDAY)]
        for offset in range(0, 7):
            day = MONDAY + timedelta(days=offset)
            self.assertEqual([i["id"] for i in shop.available_this_week(p, day)], first)

    def test_rotation_survives_a_fresh_interpreter(self):
        """
        The hash() trap again: string hashing is randomised per process,
        so a hash-keyed rotation would reshuffle the shop on every launch.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        code = ("import sys; sys.path.insert(0, %r)\n"
                "from datetime import date\n"
                "from core import shop, profiles\n"
                "p = profiles._blank_profile('K')\n"
                "print([i['id'] for i in shop.available_this_week(p, date(2026,7,27))])\n"
                "print(shop.featured_today(p, date(2026,7,27))['id'])" % root)
        runs = [subprocess.run([sys.executable, "-c", code], capture_output=True,
                               text=True, env=dict(os.environ, PYTHONHASHSEED=str(s)))
                for s in (0, 1, 9999)]
        for r in runs:
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(runs[0].stdout, runs[1].stdout)
        self.assertEqual(runs[0].stdout, runs[2].stdout)

    def test_different_weeks_differ(self):
        p = fresh()
        weeks = {tuple(i["id"] for i in shop.available_this_week(p, MONDAY + timedelta(weeks=n)))
                 for n in range(8)}
        self.assertGreater(len(weeks), 1)

    def test_owned_permanents_never_reappear(self):
        p = fresh(fish=10000)
        for _ in range(30):
            offered = shop.available_this_week(p, MONDAY)
            perm = [i for i in offered if i["kind"] in (shop.KIND_TOY, shop.KIND_DECOR)]
            if not perm:
                break
            shop.buy(p, perm[0]["id"])
            self.assertNotIn(perm[0]["id"],
                             [i["id"] for i in shop.available_this_week(p, MONDAY)])

    def test_treats_can_come_back(self):
        p = fresh(fish=10000)
        treat = next(i for i in shop.CATALOG if i["kind"] == shop.KIND_TREAT)
        shop.buy(p, treat["id"])
        self.assertFalse(shop.owns(p, treat["id"]))  # consumables are never "owned"

    def test_featured_is_not_a_duplicate_of_the_week(self):
        p = fresh()
        weekly = {i["id"] for i in shop.available_this_week(p, MONDAY)}
        feature = shop.featured_today(p, MONDAY)
        self.assertNotIn(feature["id"], weekly)

    def test_featured_changes_day_to_day(self):
        p = fresh()
        picks = {shop.featured_today(p, MONDAY + timedelta(days=n))["id"]
                 for n in range(7)}
        self.assertGreater(len(picks), 1)

    def test_the_dream_item_is_always_on_the_shelf(self):
        p = fresh()
        for n in range(14):
            ids = [i["id"] for i in shop.shelf(p, MONDAY + timedelta(days=n))]
            self.assertIn(shop.DREAM_ITEM["id"], ids)


class TestBuying(unittest.TestCase):
    def test_a_purchase_you_can_afford(self):
        p = fresh(fish=100)
        self.assertTrue(shop.buy(p, "yarn_ball"))
        self.assertEqual(p["fish"], 100 - shop.BY_ID["yarn_ball"]["price"])
        self.assertIn("yarn_ball", p["inventory"]["toys"])

    def test_fish_can_never_go_negative(self):
        p = fresh(fish=5)
        for item in shop.CATALOG:
            shop.buy(p, item["id"])
            self.assertGreaterEqual(p["fish"], 0)
        self.assertEqual(p["fish"], 5)   # nothing was affordable, nothing changed

    def test_refusal_is_kind_and_specific(self):
        p = fresh(fish=5)
        ok, reason = shop.can_buy(p, "yarn_ball")
        self.assertFalse(ok)
        self.assertIn("20 more fish", reason)
        for word in ("can't", "cannot", "afford", "poor", "not enough"):
            self.assertNotIn(word, reason.lower())

    def test_buying_twice_is_refused(self):
        p = fresh(fish=500)
        self.assertTrue(shop.buy(p, "rug"))
        self.assertFalse(shop.buy(p, "rug"))
        self.assertEqual(p["inventory"]["decor"].count("rug"), 1)

    def test_unknown_item_is_refused_not_fatal(self):
        p = fresh(fish=500)
        self.assertFalse(shop.buy(p, "moon_on_a_stick"))
        self.assertEqual(p["fish"], 500)

    def test_litter_upgrades_never_downgrade(self):
        p = fresh(fish=500)
        self.assertTrue(shop.buy(p, "deluxe"))
        self.assertEqual(shop.litter_coverage(p), 2)
        self.assertFalse(shop.buy(p, "clumping"))   # already covered
        self.assertEqual(shop.litter_coverage(p), 2)

    def test_treats_stack_up(self):
        p = fresh(fish=500)
        shop.buy(p, "tuna_flake")
        shop.buy(p, "tuna_flake")
        self.assertEqual(shop.treat_count(p, "tuna_flake"), 2)


class TestEffects(unittest.TestCase):
    def test_activate_consumes_a_treat_and_arms_an_effect(self):
        p = fresh(fish=500)
        shop.buy(p, "tuna_flake")
        self.assertEqual(shop.activate(p, "tuna_flake"), shop.EFFECT_SHIELD)
        self.assertEqual(shop.treat_count(p, "tuna_flake"), 0)
        self.assertTrue(shop.has_effect(p, shop.EFFECT_SHIELD))

    def test_effects_never_stack(self):
        p = fresh(fish=500)
        shop.buy(p, "tuna_flake")
        shop.buy(p, "tuna_flake")
        shop.activate(p, "tuna_flake")
        self.assertIsNone(shop.activate(p, "tuna_flake"))
        self.assertEqual(shop.treat_count(p, "tuna_flake"), 1)  # not wasted

    def test_activating_without_the_treat_does_nothing(self):
        p = fresh()
        self.assertIsNone(shop.activate(p, "tuna_flake"))
        self.assertFalse(shop.armed(p))

    def test_take_effect_consumes_exactly_once(self):
        p = fresh(fish=500)
        shop.buy(p, "catnip_cookie")
        shop.activate(p, "catnip_cookie")
        self.assertTrue(shop.take_effect(p, shop.EFFECT_COMBO_SAVER))
        self.assertFalse(shop.take_effect(p, shop.EFFECT_COMBO_SAVER))

    def test_an_armed_effect_survives_a_restart(self):
        p = fresh(fish=500)
        shop.buy(p, "birthday_feast")
        shop.activate(p, "birthday_feast")
        import copy
        reloaded = copy.deepcopy(p)     # what a save/load round-trip gives
        self.assertTrue(shop.has_effect(reloaded, shop.EFFECT_BONUS))

    def test_taking_an_effect_you_dont_have_is_harmless(self):
        p = fresh()
        self.assertFalse(shop.take_effect(p, shop.EFFECT_SHIELD))


class TestFavourites(unittest.TestCase):
    def test_stable_per_cat(self):
        for seed in (1, 42, 483921):
            self.assertEqual(shop.favourite_treat(seed), shop.favourite_treat(seed))
            self.assertIn(shop.favourite_treat(seed), shop.BY_ID)

    def test_cats_differ(self):
        picks = {shop.favourite_treat(s) for s in range(200)}
        self.assertGreater(len(picks), 1)

    def test_reachable_from_the_cat(self):
        c = cat.Cat(42, "Mochi")
        self.assertEqual(shop.BY_ID[c.favourite_treat]["kind"], shop.KIND_TREAT)
        self.assertEqual(shop.BY_ID[c.favourite_toy]["kind"], shop.KIND_TOY)


class TestLitterInsurance(unittest.TestCase):
    def play_after_gap(self, gap_days, litter="basic", streak=5):
        p = fresh()
        p["inventory"]["litter"] = litter
        p["current_streak"] = streak
        p["longest_streak"] = streak
        p["last_played"] = (date.today() - timedelta(days=gap_days)).isoformat()
        profiles.touch_day(p)
        return p

    def test_consecutive_days_are_unchanged(self):
        p = self.play_after_gap(1)
        self.assertEqual(p["current_streak"], 6)
        self.assertFalse(profiles.streak_was_rescued(p))

    def test_basic_litter_covers_nothing(self):
        self.assertEqual(self.play_after_gap(2, "basic")["current_streak"], 1)
        self.assertEqual(self.play_after_gap(3, "basic")["current_streak"], 1)

    def test_clumping_covers_one_missed_day(self):
        p = self.play_after_gap(2, "clumping")
        self.assertEqual(p["current_streak"], 6)
        self.assertTrue(profiles.streak_was_rescued(p))
        self.assertEqual(self.play_after_gap(3, "clumping")["current_streak"], 1)

    def test_deluxe_covers_two(self):
        self.assertEqual(self.play_after_gap(2, "deluxe")["current_streak"], 6)
        self.assertEqual(self.play_after_gap(3, "deluxe")["current_streak"], 6)
        self.assertEqual(self.play_after_gap(4, "deluxe")["current_streak"], 1)

    def test_insurance_only_ever_preserves(self):
        """It can add to a streak; there is no path where it subtracts."""
        for gap in range(1, 8):
            for litter in shop.LITTER_TIERS:
                p = self.play_after_gap(gap, litter, streak=9)
                self.assertGreaterEqual(p["current_streak"], 1)
                self.assertLessEqual(p["current_streak"], 10)

    def test_same_day_login_still_returns_false(self):
        p = fresh()
        p["last_played"] = date.today().isoformat()
        self.assertFalse(profiles.touch_day(p))

    def test_first_ever_play_is_unchanged(self):
        p = fresh()
        self.assertTrue(profiles.touch_day(p))
        self.assertEqual(p["current_streak"], 1)


class TestWaryState(unittest.TestCase):
    def test_latching_and_clearing(self):
        p = fresh()
        self.assertFalse(cat.wary_active(p))
        cat.set_wary(p, True)
        self.assertTrue(cat.wary_active(p))
        self.assertTrue(cat.needs_win_back(p))
        cat.clear_wary(p)
        self.assertFalse(cat.wary_active(p))
        self.assertFalse(cat.needs_win_back(p))

    def test_the_beat_runs_at_most_once_a_day(self):
        p = fresh()
        cat.set_wary(p, True)
        now = datetime(2026, 7, 26, 10, 0)
        cat.mark_wary_won(p, now)
        self.assertFalse(cat.needs_win_back(p, now.date()))
        self.assertTrue(cat.wary_active(p))   # still wary, just not re-tested
        self.assertTrue(cat.needs_win_back(p, now.date() + timedelta(days=1)))

    def test_five_days_alone_makes_a_cat_wary(self):
        p = fresh()
        now = datetime(2026, 7, 26, 12, 0)
        for task in cat.CARE_TASKS:
            cat.stamp_care(p, task, now - timedelta(days=5))
        self.assertTrue(cat.is_wary(p, now))

    def test_a_wary_pose_exists_and_renders(self):
        self.assertIn("wary", cat.POSES)
        for seed in (1, 42, 483921):
            c = cat.Cat(seed)
            for growth in (0, 3):
                rows = c.art("wary", growth)
                self.assertTrue(rows)
                self.assertLessEqual(max(len(r) for r in rows), 12)
                for r in rows:
                    self.assertNotIn("{", r)


class TestWaryCostsNothing(unittest.TestCase):
    """
    The hard limit from the design: a swat costs seconds and nothing else.
    This is asserted against the source, because it's the kind of rule
    that gets broken by a well-meaning edit six months from now.
    """

    def source(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "modes", "care.py")) as f:
            text = f.read()
        start = text.index("def win_it_back")
        end = text.index("# --- the board")
        return text[start:end]

    def test_the_beat_writes_no_counters(self):
        body = self.source()
        for forbidden in ('profile["fish"]', 'profile["current_streak"]',
                          'profile["badges"]', "stamp_care", "record_session",
                          "lives", "score -=", "clear_wary"):
            self.assertNotIn(forbidden, body,
                             "win_it_back must not touch %s" % forbidden)

    def test_the_beat_only_writes_the_wary_flag(self):
        body = self.source()
        writes = [l for l in body.splitlines()
                  if "profile" in l and ("=" in l or "cat." in l)]
        for line in writes:
            self.assertTrue(
                "mark_wary_won" in line or "from_profile" in line
                or "def " in line, "unexpected profile write: %r" % line)

    def test_the_distance_is_hard_capped(self):
        from modes import care
        self.assertLessEqual(care.WARY_MAX_DISTANCE, 8)
        self.assertGreater(care.WARY_MAX_DISTANCE, care.WARY_START_DISTANCE)

    def test_the_bar_always_drops_to_winnable(self):
        """
        However badly it's going, the steadiness needed reaches zero, so
        the cat can always be won back. Guaranteed, not hoped for.
        """
        from modes import care
        needed = [max(0.0, care.WARY_BASE_EVENNESS - n * care.WARY_MERCY)
                  for n in range(40)]
        self.assertEqual(needed[-1], 0.0)
        attempts_to_free = next(n for n, v in enumerate(needed) if v == 0.0)
        self.assertLess(attempts_to_free, 12)


if __name__ == "__main__":
    unittest.main()
