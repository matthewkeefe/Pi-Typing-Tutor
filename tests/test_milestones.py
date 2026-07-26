"""
Milestone unlocks -- issue #29.

The acceptance criteria are all about a promise to kids who were already
playing: **retroactive credit**. Every track reads data the profile
already kept, so a kid three months in gets everything they've already
earned the first time this runs rather than starting from zero. Starting
them at zero for a feature they never saw would be guard 2 inverted.

The other half is that fish can never reach these. The moment one is
buyable, the second progression bar collapses back into the first.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, milestones, profiles, scrapbook, shop  # noqa


def a_profile(**over):
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0, "tricks": []}
    p.update(over)
    return p


def a_veteran():
    """Someone who has been playing since long before this feature."""
    p = a_profile(total_words=12000, days_played=120)
    p["alphabet"] = adaptive.FREQ_ORDER
    p["keys"] = {c: {"n": 99, "conf": 0.99, "ms": adaptive.MASTER_MS - 20}
                 for c in adaptive.FREQ_ORDER}
    return p


class TestTracks(unittest.TestCase):
    def test_every_track_reads_existing_profile_data(self):
        """'No new grind counters' -- the acceptance bar."""
        blank = profiles._blank_profile("X")
        for key in ("total_words", "days_played", "keys", "alphabet"):
            self.assertIn(key, blank)

    def test_a_blank_profile_reads_zero_everywhere(self):
        p = a_profile()
        for track, _label, _fn in milestones.TRACKS:
            self.assertEqual(milestones.value(p, track), 0, track)

    def test_tracks_and_labels_line_up(self):
        for track, label, _fn in milestones.TRACKS:
            self.assertTrue(label)
            self.assertIn(track, milestones.TRACK_READERS)
            self.assertEqual(milestones.TRACK_LABELS[track], label)

    def test_letters_mastered_counts_only_green(self):
        p = a_profile()
        p["keys"] = {"e": {"n": 99, "conf": 0.99, "ms": 200.0},
                     "n": {"n": 99, "conf": 0.2, "ms": 2000.0}}
        self.assertEqual(milestones.value(p, "letters"), 1)

    def test_album_track_follows_the_scrapbook(self):
        p = a_profile()
        before = milestones.value(p, "album")
        for ch in adaptive.FREQ_ORDER:
            scrapbook.catch(p, ch)
        self.assertGreater(milestones.value(p, "album"), before)

    def test_an_unknown_track_reads_zero(self):
        self.assertEqual(milestones.value(a_profile(), "nope"), 0)


class TestLadder(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [milestones.milestone_id(t, n) for t, n, _i, _b in milestones.LADDER]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_reward_is_a_real_catalogue_item(self):
        for _t, _n, item_id, _b in milestones.LADDER:
            self.assertIn(item_id, shop.BY_ID, item_id)

    def test_every_reward_is_flagged_unbuyable(self):
        for _t, _n, item_id, _b in milestones.LADDER:
            self.assertTrue(shop.BY_ID[item_id].get("milestone"), item_id)

    def test_thresholds_rise_within_each_track(self):
        seen = {}
        for track, threshold, _i, _b in milestones.LADDER:
            if track in seen:
                self.assertGreater(threshold, seen[track], track)
            seen[track] = threshold

    def test_the_first_rung_of_each_track_is_reachable_early(self):
        """
        A reward track nobody reaches the first rung of is decoration.
        The opening thresholds should land in a kid's first week or two.
        """
        firsts = {}
        for track, threshold, _i, _b in milestones.LADDER:
            firsts.setdefault(track, threshold)
        self.assertLessEqual(firsts["words"], 1000)
        self.assertLessEqual(firsts["days"], 7)
        self.assertLessEqual(firsts["letters"], 1)

    def test_every_track_has_rungs(self):
        tracked = {t for t, _n, _i, _b in milestones.LADDER}
        for track, _label, _fn in milestones.TRACKS:
            self.assertIn(track, tracked, track)

    def test_blurbs_describe_accumulation_not_performance(self):
        """Guard 4: these are totals reached, never scores beaten."""
        for _t, _n, _i, blurb in milestones.LADDER:
            for perf in ("fast", "wpm", "accuracy", "perfect", "beat", "score"):
                self.assertNotIn(perf, blurb.lower(), blurb)


class TestAwarding(unittest.TestCase):
    def test_a_new_kid_earns_nothing_yet(self):
        self.assertEqual(milestones.check_new(a_profile()), [])

    def test_a_veteran_gets_full_retroactive_credit(self):
        p = a_veteran()
        fresh = milestones.check_new(p)
        self.assertGreater(len(fresh), 4, "months of play should credit a lot")

    def test_nothing_is_awarded_twice(self):
        p = a_veteran()
        milestones.check_new(p)
        self.assertEqual(milestones.check_new(p), [])

    def test_awards_land_in_the_inventory(self):
        p = a_veteran()
        milestones.check_new(p)
        inv = shop.inventory(p)
        owned = set(inv["accessories"]) | set(inv["decor"]) | set(inv["toys"])
        self.assertIn("star_charm", owned)

    def test_claims_survive_a_json_round_trip(self):
        p = a_veteran()
        milestones.check_new(p)
        back = json.loads(json.dumps(p))
        self.assertEqual(milestones.check_new(back), [])

    def test_claims_are_append_only(self):
        p = a_veteran()
        milestones.check_new(p)
        n = len(milestones.claimed(p))
        p["total_words"] = 0          # a track going backwards is possible
        milestones.check_new(p)
        self.assertEqual(len(milestones.claimed(p)), n)

    def test_nothing_is_ever_taken_back(self):
        """Guard 2: earned progress never decays, even if a total drops."""
        p = a_veteran()
        milestones.check_new(p)
        before = set(shop.inventory(p)["accessories"])
        p["total_words"] = 0
        p["days_played"] = 0
        milestones.check_new(p)
        self.assertTrue(before <= set(shop.inventory(p)["accessories"]))

    def test_granting_an_unknown_item_is_survivable(self):
        self.assertFalse(milestones.grant(a_profile(), "not_a_thing"))


class TestUnbuyable(unittest.TestCase):
    """The whole point of a second currency is that the first can't reach it."""

    def test_fish_cannot_buy_a_milestone_item(self):
        p = a_profile(fish=10 ** 6)
        for _t, _n, item_id, _b in milestones.LADDER:
            ok, reason = shop.can_buy(p, item_id)
            self.assertFalse(ok, item_id)
            self.assertTrue(reason)

    def test_buy_refuses_even_when_called_directly(self):
        p = a_profile(fish=10 ** 6)
        self.assertFalse(shop.buy(p, "star_charm"))
        self.assertNotIn("star_charm", shop.inventory(p)["accessories"])

    def test_they_never_appear_in_the_weekly_rotation(self):
        rotatable = {i["id"] for i in shop._rotatable()}
        for _t, _n, item_id, _b in milestones.LADDER:
            self.assertNotIn(item_id, rotatable, item_id)

    def test_they_never_appear_on_the_shelf(self):
        p = a_profile(fish=10 ** 6)
        shelf = {i["id"] for i in shop.shelf(p)}
        for _t, _n, item_id, _b in milestones.LADDER:
            self.assertNotIn(item_id, shelf, item_id)

    def test_refusing_is_kind_not_a_tease(self):
        p = a_profile(fish=10 ** 6)
        _ok, reason = shop.can_buy(p, "star_charm")
        for nasty in ("can't afford", "not enough", "denied", "locked"):
            self.assertNotIn(nasty, reason.lower(), reason)


class TestStatsReadout(unittest.TestCase):
    def test_every_track_reports_a_line(self):
        rows = milestones.summary(a_profile())
        self.assertEqual(len(rows), len(milestones.TRACKS))

    def test_lines_fit_the_existing_layout(self):
        for label, current, threshold in milestones.summary(a_veteran()):
            text = ("%d" % current if threshold is None
                    else "%d  (next at %d)" % (current, threshold))
            self.assertLessEqual(len(label), 22, label)
            self.assertLessEqual(len(text), 26, text)

    def test_a_finished_track_reports_no_next(self):
        p = a_veteran()
        p["keys"] = {c: {"n": 99, "conf": 0.99, "ms": adaptive.MASTER_MS - 20}
                     for c in adaptive.FREQ_ORDER}
        self.assertIsNone(milestones.next_up(p, "letters"))

    def test_next_up_points_at_the_nearest_unreached_rung(self):
        p = a_profile(total_words=600)
        current, threshold, _blurb = milestones.next_up(p, "words")
        self.assertEqual(current, 600)
        self.assertEqual(threshold, 2500)


class TestRenderable(unittest.TestCase):
    def test_every_earned_accessory_can_be_drawn(self):
        for _t, _n, item_id, _b in milestones.LADDER:
            if shop.BY_ID[item_id]["kind"] != shop.KIND_ACCESSORY:
                continue
            self.assertIn(item_id, cat.ACCESSORIES, item_id)
            kitty = cat.Cat(4242, "M", growth=2, accessory=item_id)
            self.assertTrue(kitty.art("sit"))

    def test_earned_accessory_art_is_distinct(self):
        arts = [v["art"] for v in cat.ACCESSORIES.values()]
        self.assertEqual(len(arts), len(set(arts)))


if __name__ == "__main__":
    unittest.main()
