"""
Tests for the shared word list (issue #25, and #24 will lean on it too).

The load-time behaviour matters as much as the lookups: this runs on a Pi
where re-reading a 2000-line file per keystroke would be felt, and a fresh
checkout with no words.txt must degrade to "mode hides itself" rather than
"menu crashes".
"""

import os
import random
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, wordlist  # noqa: E402

GATE = 12   # modes/soup.GATE_LETTERS, duplicated to keep this test standalone


class TestLoading(unittest.TestCase):
    def test_the_real_file_is_there_and_sane(self):
        words = wordlist.load()
        self.assertGreater(len(words), 1500)
        for w in words:
            self.assertTrue(w.isalpha() and w.isascii() and w.islower(), w)
            self.assertGreaterEqual(len(w), wordlist.MIN_LEN, w)

    def test_it_is_a_set_for_o1_lookup(self):
        self.assertIsInstance(wordlist.load(), frozenset)

    def test_loading_twice_returns_the_same_object(self):
        self.assertIs(wordlist.load(), wordlist.load())

    def test_comments_and_blanks_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# a header\n\n  \ncat\ndog\n# trailing\nBIRD\n")
            wordlist.reset_cache()
            got = wordlist.load(p)
            self.assertEqual(got, frozenset({"cat", "dog", "bird"}))
        wordlist.reset_cache()

    def test_a_missing_file_is_empty_not_an_explosion(self):
        wordlist.reset_cache()
        self.assertEqual(wordlist.load("/nope/does/not/exist.txt"), frozenset())
        wordlist.reset_cache()

    def test_is_word_is_case_and_space_insensitive(self):
        self.assertTrue(wordlist.is_word("  CAT "))
        self.assertFalse(wordlist.is_word("zzzzq"))


class TestAlphabetFilter(unittest.TestCase):
    def test_only_returns_words_inside_the_alphabet(self):
        for n in (6, 10, 14, 26):
            alpha = set(adaptive.FREQ_ORDER[:n])
            for w in wordlist.for_alphabet("".join(alpha)):
                self.assertTrue(set(w) <= alpha, w)

    def test_bigger_alphabets_never_lose_words(self):
        prev = 0
        for n in range(6, 27):
            got = len(wordlist.for_alphabet(adaptive.FREQ_ORDER[:n]))
            self.assertGreaterEqual(got, prev)
            prev = got

    def test_length_bounds_are_respected(self):
        got = wordlist.for_alphabet(adaptive.FREQ_ORDER, min_len=5, max_len=6)
        self.assertTrue(got)
        for w in got:
            self.assertIn(len(w), (5, 6), w)


class TestFormable(unittest.TestCase):
    """Tiles are consumed -- this is what makes a bowl a bowl."""

    def test_repeated_letters_need_repeated_tiles(self):
        one_t = Counter("letra")
        self.assertFalse(wordlist.formable(one_t, "letter"))
        two_t = Counter("lettera")
        self.assertTrue(wordlist.formable(two_t, "letter"))

    def test_a_word_is_formable_from_its_own_letters(self):
        for w in ("cat", "studio", "banana", "letter"):
            self.assertTrue(wordlist.formable(Counter(w), w), w)

    def test_missing_letters_are_rejected(self):
        self.assertFalse(wordlist.formable(Counter("abc"), "cab" + "z"))

    def test_solutions_are_all_actually_formable(self):
        tiles = "studio"
        for w in wordlist.solutions(tiles):
            self.assertTrue(wordlist.formable(Counter(tiles), w), w)
            self.assertIn(w, wordlist.load())


class TestBowlGeneration(unittest.TestCase):
    """
    #25's acceptance criterion: "Letter sets always yield >= 5 findable
    words (verify at generation time)". Roughly one seed in five fails that
    bar on its own, so the generator has to be doing the filtering.
    """

    def test_gated_alphabets_always_clear_the_bar(self):
        for n in range(GATE, 27):
            alpha = adaptive.FREQ_ORDER[:n]
            for trial in range(25):
                made = wordlist.make_bowl(alpha, random.Random(trial))
                self.assertIsNotNone(made, "n=%d trial=%d" % (n, trial))
                tiles, sols = made
                self.assertGreaterEqual(
                    len(sols), wordlist.MIN_SOLUTIONS,
                    "n=%d trial=%d tiles=%s sols=%s" % (n, trial, tiles, sols))

    def test_bowls_are_the_right_size(self):
        for trial in range(30):
            tiles, _ = wordlist.make_bowl(adaptive.FREQ_ORDER,
                                          random.Random(trial))
            self.assertIn(len(tiles), wordlist.BOWL_SIZES)

    def test_tiles_stay_inside_the_alphabet(self):
        for n in (GATE, 16, 20):
            alpha = set(adaptive.FREQ_ORDER[:n])
            for trial in range(15):
                tiles, _ = wordlist.make_bowl("".join(alpha),
                                              random.Random(trial))
                self.assertTrue(set(tiles) <= alpha, tiles)

    def test_every_solution_is_buildable_from_the_bowl(self):
        for trial in range(25):
            tiles, sols = wordlist.make_bowl(adaptive.FREQ_ORDER,
                                             random.Random(trial))
            counts = Counter(tiles)
            for w in sols:
                self.assertTrue(wordlist.formable(counts, w),
                                "%s not in %s" % (w, tiles))

    def test_the_seed_word_itself_is_always_solvable(self):
        """The bowl is a real word's letters, so it must contain one."""
        for trial in range(25):
            tiles, sols = wordlist.make_bowl(adaptive.FREQ_ORDER,
                                             random.Random(trial))
            longest = max(len(w) for w in sols)
            self.assertEqual(longest, len(tiles))

    def test_it_is_deterministic_for_a_given_rng(self):
        a = wordlist.make_bowl(adaptive.FREQ_ORDER, random.Random(99))
        b = wordlist.make_bowl(adaptive.FREQ_ORDER, random.Random(99))
        self.assertEqual(a, b)

    def test_an_impossible_alphabet_returns_none(self):
        self.assertIsNone(wordlist.make_bowl("q", random.Random(1)))


class TestViability(unittest.TestCase):
    def test_the_starting_alphabet_is_too_thin_to_play(self):
        """
        The finding behind the gate: `enitrl` has almost nothing in it.
        If this ever rises materially, the gate can be reconsidered.
        """
        self.assertLess(wordlist.viable(adaptive.START_ALPHABET), 5)

    def test_the_gate_point_is_comfortably_playable(self):
        self.assertGreater(wordlist.viable(adaptive.FREQ_ORDER[:GATE]), 30)

    def test_viability_grows_with_the_alphabet(self):
        small = wordlist.viable(adaptive.FREQ_ORDER[:GATE])
        big = wordlist.viable(adaptive.FREQ_ORDER[:18])
        self.assertGreater(big, small)


if __name__ == "__main__":
    unittest.main()
