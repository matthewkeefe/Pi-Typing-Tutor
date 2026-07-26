"""
The Scrapbook -- issue #27.

Most of this guards one property: **nothing here can ever be lost**. It's
the additive-only principle (guard 2) at its most literal, and a
collection is exactly the kind of screen where a later feature quietly
adds a "spend" or a "reset".

The other half is that derived pages read their source of truth instead
of copying it. A duplicated list is one that eventually disagrees, and
the album would be the last place anyone thought to look.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, profiles, scrapbook, shop  # noqa: E402


def a_profile():
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0, "tricks": []}
    return p


class TestFishSpecies(unittest.TestCase):
    def test_there_is_one_species_per_letter(self):
        self.assertEqual(len(scrapbook.FISH_NAMES), 26)
        self.assertEqual(sorted(scrapbook.FISH_NAMES),
                         sorted(adaptive.FREQ_ORDER))

    def test_names_are_unique_and_terminal_safe(self):
        names = list(scrapbook.FISH_NAMES.values())
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertTrue(n.isascii() and n.isprintable(), n)

    def test_rarity_follows_unlock_order(self):
        """
        The nice property: rarity is English, not a dice table. The Q-fish
        is a legend because `q` is the last letter a kid unlocks and turns
        up in almost nothing.
        """
        self.assertEqual(scrapbook.fish_tier("e"), "common")
        self.assertEqual(scrapbook.fish_tier("q"), "legendary")
        self.assertEqual(scrapbook.fish_tier("j"), "legendary")
        for ch in adaptive.START_ALPHABET:
            self.assertEqual(scrapbook.fish_tier(ch), "common", ch)

    def test_tiers_only_get_rarer_down_the_order(self):
        rank = {"common": 0, "uncommon": 1, "rare": 2, "legendary": 3}
        seen = [rank[scrapbook.fish_tier(c)] for c in scrapbook.fish_letters()]
        self.assertEqual(seen, sorted(seen))

    def test_every_letter_is_reachable(self):
        for ch in adaptive.FREQ_ORDER:
            self.assertTrue(scrapbook.fish_name(ch))


class TestCatching(unittest.TestCase):
    def test_typing_a_word_hooks_its_letters(self):
        p = a_profile()
        got = dict(scrapbook.catch_from_word(p, "quiet"))
        self.assertIn("q", got)
        self.assertEqual(got["q"], "queen angel")

    def test_a_species_is_only_caught_once(self):
        p = a_profile()
        self.assertTrue(scrapbook.catch_from_word(p, "quiet"))
        self.assertEqual(scrapbook.catch_from_word(p, "quiet"), [])

    def test_catching_is_deterministic_not_a_roll(self):
        """
        No RNG anywhere in the path. A random drop table here would be a
        loot box pointed at a seven-year-old.
        """
        a, b = a_profile(), a_profile()
        for _ in range(5):
            scrapbook.catch_from_word(a, "zebra")
            scrapbook.catch_from_word(b, "zebra")
        self.assertEqual(scrapbook.caught(a), scrapbook.caught(b))

    def test_non_letters_catch_nothing(self):
        p = a_profile()
        self.assertEqual(scrapbook.catch_from_word(p, "123 ,."), [])

    def test_empty_input_is_survivable(self):
        p = a_profile()
        self.assertEqual(scrapbook.catch_from_word(p, ""), [])
        self.assertEqual(scrapbook.catch_from_word(p, None), [])
        self.assertIsNone(scrapbook.catch(p, None))

    def test_case_does_not_matter(self):
        p = a_profile()
        scrapbook.catch_from_word(p, "QUIET")
        self.assertIn("q", scrapbook.caught(p))


class TestNothingIsEverLost(unittest.TestCase):
    """Guard 2, in its purest form. There is no remove path, by design."""

    def test_the_module_has_no_way_to_remove_anything(self):
        """
        assertNotIn dumps the whole module on failure, so this reports the
        needle instead. `rows = []` in the album builders is a local
        initialiser, not a removal -- the patterns here are the ones that
        would actually take something off a kid.
        """
        with open(scrapbook.__file__, encoding="utf-8") as fh:
            body = fh.read().split('"""', 2)[-1]
        banned = [".remove(", ".pop(", ".clear(", "del "]
        banned += ['["%s"] = ' % k for k in ("fish", "gifts", "ribbons")]
        for needle in banned:
            self.assertFalse(needle in body,
                             "%r appears in core/scrapbook.py" % needle)

    def test_collections_only_grow(self):
        p = a_profile()
        sizes = []
        for word in ("eel", "quiet", "jazz", "box", "vex"):
            scrapbook.catch_from_word(p, word)
            sizes.append(len(scrapbook.caught(p)))
        self.assertEqual(sizes, sorted(sizes))

    def test_gifts_and_ribbons_are_append_only(self):
        p = a_profile()
        scrapbook.find_gift(p, "feather")
        self.assertIsNone(scrapbook.find_gift(p, "feather"))
        self.assertEqual(scrapbook.found_gifts(p), ["feather"])
        scrapbook.award_ribbon(p, "Beginner Cup")
        self.assertIsNone(scrapbook.award_ribbon(p, "Beginner Cup"))
        self.assertEqual(scrapbook.ribbons(p), ["Beginner Cup"])

    def test_an_unknown_gift_is_refused_not_stored(self):
        p = a_profile()
        self.assertIsNone(scrapbook.find_gift(p, "moon_rock"))
        self.assertEqual(scrapbook.found_gifts(p), [])

    def test_everything_survives_a_json_round_trip(self):
        p = a_profile()
        scrapbook.catch_from_word(p, "quiet")
        scrapbook.find_gift(p, "feather")
        back = json.loads(json.dumps(p))
        self.assertEqual(scrapbook.caught(back), scrapbook.caught(p))
        self.assertEqual(scrapbook.found_gifts(back), scrapbook.found_gifts(p))

    def test_old_saves_migrate(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        self.assertEqual(scrapbook.caught(p), [])
        self.assertEqual(scrapbook.found_gifts(p), [])


class TestDerivedPages(unittest.TestCase):
    """Derived collections must read source of truth, never copy it."""

    def test_toys_track_the_inventory(self):
        p = a_profile()
        p["fish"] = 999
        before = dict((n, f) for n, f, _ in scrapbook._album_toys(p))
        self.assertFalse(any(before.values()))
        shop.buy(p, "yarn_ball")
        after = dict((n, f) for n, f, _ in scrapbook._album_toys(p))
        self.assertTrue(after[shop.BY_ID["yarn_ball"]["name"]])

    def test_outfits_track_the_inventory(self):
        p = a_profile()
        p["fish"] = 999
        shop.buy(p, "red_collar")
        rows = dict((n, f) for n, f, _ in scrapbook._album_outfits(p))
        self.assertTrue(rows[shop.BY_ID["red_collar"]["name"]])

    def test_tricks_track_the_cat(self):
        p = a_profile()
        rows = dict((n, f) for n, f, _ in scrapbook._album_tricks(p))
        self.assertFalse(any(rows.values()))
        cat.learn_trick(p, "e")
        rows = dict((n, f) for n, f, _ in scrapbook._album_tricks(p))
        self.assertTrue(any(rows.values()))

    def test_derived_pages_are_not_duplicated_into_storage(self):
        p = a_profile()
        p["fish"] = 999
        shop.buy(p, "yarn_ball")
        cat.learn_trick(p, "e")
        stored = scrapbook.book(p)
        self.assertEqual(sorted(stored), ["fish", "gifts", "ribbons"])

    def test_every_page_covers_its_whole_catalog(self):
        p = a_profile()
        pages = dict(scrapbook.albums(p))
        self.assertEqual(len(pages["Fish"]), 26)
        self.assertEqual(len(pages["Gifts"]), len(scrapbook.GIFTS))
        self.assertEqual(len(pages["Tricks"]), len(cat.TRICKS))


class TestAlbums(unittest.TestCase):
    def test_a_brand_new_book_still_has_pages(self):
        """'Album renders fine with zero items (all silhouettes).'"""
        pages = scrapbook.albums(a_profile())
        self.assertTrue(pages)
        for _title, rows in pages:
            self.assertTrue(rows)

    def test_empty_pages_are_dropped(self):
        titles = [t for t, _ in scrapbook.albums(a_profile())]
        self.assertNotIn("Ribbons", titles, "no ribbons yet, so no page")

    def test_a_ribbon_creates_its_page(self):
        p = a_profile()
        scrapbook.award_ribbon(p, "Beginner Cup")
        self.assertIn("Ribbons", [t for t, _ in scrapbook.albums(p)])

    def test_progress_counts_add_up(self):
        p = a_profile()
        scrapbook.catch_from_word(p, "eel")
        pages = dict(scrapbook.albums(p))
        found, total = scrapbook.page_progress(pages["Fish"])
        self.assertEqual(total, 26)
        self.assertEqual(found, len(set("eel")))

    def test_completion_runs_zero_to_a_hundred(self):
        p = a_profile()
        self.assertEqual(scrapbook.completion(p), 0.0)
        for ch in adaptive.FREQ_ORDER:
            scrapbook.catch(p, ch)
        self.assertGreater(scrapbook.completion(p), 0.0)
        self.assertLessEqual(scrapbook.completion(p), 100.0)

    def test_completion_only_rises(self):
        p = a_profile()
        seen = [scrapbook.completion(p)]
        for word in ("eel", "quiet", "jazz"):
            scrapbook.catch_from_word(p, word)
            seen.append(scrapbook.completion(p))
        self.assertEqual(seen, sorted(seen))

    def test_labels_are_terminal_safe(self):
        p = a_profile()
        for _title, rows in scrapbook.albums(p):
            for label, _found, note in rows:
                self.assertTrue(label.isascii() and label.isprintable(), label)
                self.assertTrue(note.isascii(), note)


class TestShowUpGifts(unittest.TestCase):
    def test_gift_ids_and_names_line_up(self):
        self.assertEqual(len(scrapbook.GIFT_IDS), len(scrapbook.GIFTS))
        for gid in scrapbook.GIFT_IDS:
            self.assertIn(gid, scrapbook.GIFT_NAMES)

    def test_gifts_are_ordinary_things_not_prizes(self):
        """
        For showing up, not for performing. Nothing here should read as a
        payout -- the point is that it accumulates.
        """
        for _gid, name in scrapbook.GIFTS:
            for grand in ("gold", "trophy", "jewel", "treasure", "rare"):
                self.assertNotIn(grand, name.lower(), name)

    def test_the_collection_is_finite_and_completable(self):
        p = a_profile()
        for gid in scrapbook.GIFT_IDS:
            scrapbook.find_gift(p, gid)
        remaining = [g for g in scrapbook.GIFT_IDS
                     if g not in scrapbook.found_gifts(p)]
        self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
