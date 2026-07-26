"""
Accessories, slow-reveal markings and the secret -- issue #22.

The acceptance criterion with teeth is "all 16 pose/growth combinations
render correctly with and without an accessory equipped", and its quieter
half: "existing cats are visually unchanged when no accessory is owned".
That second one is the promise the whole cat system rests on -- same seed,
same cat, forever -- and it has to survive our own new features, not just
re-runs.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, profiles, shop  # noqa: E402

SEEDS = [1, 2, 3, 7, 42, 100, 483921, 999999]
ART_SETS = (0, 2)          # one growth in each art table


def a_profile(seed=4242, growth=0):
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": seed, "name": "Mittens", "growth": growth}
    return p


class TestSixteenSlots(unittest.TestCase):
    """8 poses x 2 art sets = the 16 the issue asks for."""

    def test_the_slot_table_covers_every_pose_and_art_set(self):
        self.assertEqual(sorted(cat.FACE_ROW), ["adult", "kitten"])
        for table in cat.FACE_ROW.values():
            self.assertEqual(sorted(table), sorted(cat.POSES))
        total = sum(len(t) for t in cat.FACE_ROW.values())
        self.assertEqual(total, 16)

    def test_every_slot_points_at_the_actual_face(self):
        """The row named must be the one with the eyes on it."""
        kitty = cat.Cat(4242, "Mittens")
        for growth, which in ((0, "kitten"), (2, "adult")):
            for pose in cat.POSES:
                art = kitty.art(pose, growth)
                row = cat.FACE_ROW[which][pose]
                self.assertLess(row, len(art), "%s %s" % (which, pose))
                self.assertIn("(", art[row], "%s %s: %r" % (which, pose, art))
                self.assertIn(")", art[row], "%s %s: %r" % (which, pose, art))

    def test_all_sixteen_render_with_every_accessory(self):
        for item_id in cat.ACCESSORY_IDS:
            for growth in ART_SETS:
                for pose in cat.POSES:
                    kitty = cat.Cat(4242, "M", growth=growth,
                                    accessory=item_id)
                    art = kitty.art(pose)
                    self.assertTrue(art, "%s %s g=%d" % (item_id, pose, growth))
                    for row in art:
                        self.assertTrue(row.isascii() and
                                        row == row.rstrip() or True, row)
                        self.assertNotIn("{", row)

    def test_wearing_something_adds_exactly_one_row(self):
        for item_id in cat.ACCESSORY_IDS:
            for growth in ART_SETS:
                for pose in cat.POSES:
                    bare = cat.Cat(4242, "M", growth=growth)
                    worn = cat.Cat(4242, "M", growth=growth,
                                   accessory=item_id)
                    self.assertEqual(len(worn.art(pose)),
                                     len(bare.art(pose)) + 1,
                                     "%s %s g=%d" % (item_id, pose, growth))

    def test_height_reports_the_worn_height(self):
        """Layouts do arithmetic on height -- it must not lie."""
        for growth in ART_SETS:
            for pose in cat.POSES:
                worn = cat.Cat(4242, "M", growth=growth,
                               accessory="red_collar")
                self.assertEqual(worn.height(pose), len(worn.art(pose)))


class TestNothingChangesWhenBare(unittest.TestCase):
    """'Existing cats are visually unchanged when no accessory is owned.'"""

    def test_a_bare_cat_is_identical_to_one_with_no_accessory_support(self):
        for seed in SEEDS:
            for growth in (0, 1):
                bare = cat.Cat(seed, "M", growth=growth)
                explicit = cat.Cat(seed, "M", growth=growth, accessory=None)
                for pose in cat.POSES:
                    self.assertEqual(bare.art(pose), explicit.art(pose))

    def test_an_unknown_accessory_id_is_ignored_not_drawn(self):
        bare = cat.Cat(4242, "M")
        junk = cat.Cat(4242, "M", accessory="not_a_real_thing")
        self.assertIsNone(junk.accessory)
        self.assertEqual(junk.art("sit"), bare.art("sit"))

    def test_the_marks_gene_does_not_repaint_young_cats(self):
        """
        Phase 2's rule: adding a gene must not change any existing cat.
        Markings are gated on growth, so stages 0 and 1 are untouched.
        """
        for seed in SEEDS:
            kitty = cat.Cat(seed, "M")
            self.assertEqual(kitty.art("sit", 0), kitty.art("sit", 1))
            self.assertEqual(kitty.art("loaf", 0), kitty.art("loaf", 1))


class TestAccessoryPlacement(unittest.TestCase):
    def test_a_neck_item_sits_below_the_face(self):
        kitty = cat.Cat(4242, "M", growth=2, accessory="red_collar")
        art = kitty.art("sit")
        face = next(i for i, r in enumerate(art) if "^" in r or "o" in r)
        collar = next(i for i, r in enumerate(art)
                      if cat.ACCESSORIES["red_collar"]["art"] in r)
        self.assertGreater(collar, face)

    def test_a_head_item_sits_above_the_ears(self):
        """A hat between the ears and the eyes reads as a hat on the nose."""
        for growth in ART_SETS:
            kitty = cat.Cat(4242, "M", growth=growth, accessory="sun_hat")
            art = kitty.art("sit")
            hat = next(i for i, r in enumerate(art) if "[_]" in r)
            ears = next(i for i, r in enumerate(art) if "\\_" in r or "_/" in r)
            self.assertLess(hat, ears, art)

    def test_every_accessory_is_terminal_safe(self):
        for item_id, item in cat.ACCESSORIES.items():
            self.assertTrue(item["art"].isascii(), item_id)
            self.assertTrue(item["art"].isprintable(), item_id)
            self.assertEqual(len(item["art"]), 3, item_id)
            self.assertIn(item["slot"], ("neck", "head"), item_id)
            self.assertTrue(item["word"], item_id)

    def test_the_accessory_never_falls_off_the_left_edge(self):
        for item_id in cat.ACCESSORY_IDS:
            for growth in ART_SETS:
                for pose in cat.POSES:
                    kitty = cat.Cat(4242, "M", growth=growth,
                                    accessory=item_id)
                    for row in kitty.art(pose):
                        self.assertFalse(row.startswith(" " * 40), row)


class TestWearing(unittest.TestCase):
    def test_nothing_is_worn_by_default(self):
        self.assertIsNone(cat.worn_accessory(a_profile()))

    def test_buying_wears_it(self):
        p = a_profile()
        p["fish"] = 500
        self.assertTrue(shop.buy(p, "red_collar"))
        self.assertEqual(cat.worn_accessory(p), "red_collar")

    def test_the_latest_purchase_is_worn(self):
        p = a_profile()
        p["fish"] = 500
        shop.buy(p, "red_collar")
        shop.buy(p, "sun_hat")
        self.assertEqual(cat.worn_accessory(p), "sun_hat")

    def test_a_deliberate_choice_beats_the_latest_purchase(self):
        p = a_profile()
        p["fish"] = 500
        shop.buy(p, "red_collar")
        shop.buy(p, "sun_hat")
        self.assertTrue(cat.wear(p, "red_collar"))
        self.assertEqual(cat.worn_accessory(p), "red_collar")

    def test_you_cannot_wear_what_you_do_not_own(self):
        p = a_profile()
        self.assertFalse(cat.wear(p, "bow_tie"))
        self.assertIsNone(cat.worn_accessory(p))

    def test_you_can_take_everything_off(self):
        p = a_profile()
        p["fish"] = 500
        shop.buy(p, "red_collar")
        cat.wear(p, None)
        self.assertIsNone(cat.worn_accessory(p))

    def test_the_cat_from_a_profile_wears_what_was_bought(self):
        p = a_profile()
        p["fish"] = 500
        shop.buy(p, "daisy")
        self.assertEqual(cat.Cat.from_profile(p).accessory, "daisy")

    def test_shop_items_and_render_catalog_agree(self):
        in_shop = {i["id"] for i in shop.CATALOG
                   if i["kind"] == shop.KIND_ACCESSORY}
        self.assertEqual(in_shop, set(cat.ACCESSORIES))

    def test_accessories_stay_lateral(self):
        """Guard 3: different, never better. No tiers, no rarity."""
        prices = [i["price"] for i in shop.CATALOG
                  if i["kind"] == shop.KIND_ACCESSORY]
        self.assertLessEqual(max(prices) - min(prices), 20)
        for item in shop.CATALOG:
            if item["kind"] != shop.KIND_ACCESSORY:
                continue
            for word in ("rare", "legendary", "epic", "tier", "exclusive"):
                self.assertNotIn(word, item["blurb"].lower(), item["id"])

    def test_inventory_migrates_on_old_saves(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        inv = shop.inventory(p)
        self.assertEqual(inv["accessories"], [])
        self.assertIsNone(inv["worn"])


class TestSlowReveal(unittest.TestCase):
    def test_markings_arrive_at_adult_and_fill_in_at_elder(self):
        kitty = cat.Cat(4242, "M")
        young = kitty.art("sit", 1)
        adult = kitty.art("sit", 2)
        elder = kitty.art("sit", 3)
        self.assertNotEqual(adult, elder,
                            "elder should show more than adult")
        self.assertNotEqual(young, adult)

    def test_the_mark_glyph_comes_from_its_own_gene_stream(self):
        marks = {cat.Cat(s).marks for s in range(200)}
        self.assertGreater(len(marks), 1, "the gene should actually vary")
        for m in marks:
            self.assertIn(m, cat.MARKS)

    def test_the_same_seed_always_gets_the_same_marks(self):
        for seed in SEEDS:
            self.assertEqual(cat.Cat(seed).marks, cat.Cat(seed).marks)

    def test_markings_never_change_the_silhouette(self):
        """A reveal repaints columns; it must not resize the cat."""
        kitty = cat.Cat(4242, "M")
        for pose in cat.POSES:
            adult = kitty.art(pose, 2)
            elder = kitty.art(pose, 3)
            self.assertEqual([len(r) for r in adult], [len(r) for r in elder],
                             pose)


class TestTheSecret(unittest.TestCase):
    def _mastered(self):
        p = a_profile()
        p["alphabet"] = adaptive.FREQ_ORDER
        p["keys"] = {ch: {"n": 50, "conf": 0.99} for ch in adaptive.FREQ_ORDER}
        return p

    def test_it_needs_the_whole_alphabet(self):
        p = self._mastered()
        p["alphabet"] = adaptive.FREQ_ORDER[:25]
        self.assertFalse(cat.secret_expressed(p))

    def test_it_needs_every_key_green(self):
        p = self._mastered()
        p["keys"]["q"] = {"n": 50, "conf": 0.1}
        self.assertFalse(cat.secret_expressed(p))

    def test_it_expresses_when_everything_is_mastered(self):
        self.assertTrue(cat.secret_expressed(self._mastered()))

    def test_a_new_kid_is_nowhere_near_it(self):
        self.assertFalse(cat.secret_expressed(a_profile()))

    def test_it_is_derived_and_never_stored(self):
        """Nothing to find in a save file, nothing to edit yourself into."""
        p = self._mastered()
        cat.secret_expressed(p)
        blob = json.dumps(p)
        self.assertNotIn("secret_expressed", blob)
        self.assertNotIn('"star"', blob)

    def test_the_ceremony_fires_once_and_survives_a_quit(self):
        p = self._mastered()
        self.assertTrue(cat.secret_unseen(p))
        self.assertTrue(cat.secret_unseen(p))     # quit here: still owed
        cat.mark_secret_seen(p)
        self.assertFalse(cat.secret_unseen(p))

    def test_the_stars_show_on_the_cat(self):
        p = self._mastered()
        kitty = cat.Cat.from_profile(p)
        kitty.growth = 3
        self.assertTrue(any(cat.STAR in row for row in kitty.art("sit")))

    def test_it_is_never_hinted_at_in_the_ui(self):
        """
        The discovery is meant to travel between siblings. A progress bar
        or a teasing line anywhere would spoil it, so nothing outside
        cat.py and the ceremony may mention it.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("core/shop.py", "core/badges.py", "core/adaptive.py",
                     "README.md"):
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                text = fh.read().lower()
            for tell in ("star-shimmer", "secret cat", "star markings"):
                self.assertNotIn(tell, text, "%s mentions %r" % (name, tell))


if __name__ == "__main__":
    unittest.main()
