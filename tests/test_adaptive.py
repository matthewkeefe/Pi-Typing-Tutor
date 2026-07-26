"""
Tests for the adaptive engine. Stdlib unittest, no curses -- run with

    python3 -m unittest discover -s tests

from the project root (or just `python3 tests/test_adaptive.py`).
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, engine  # noqa: E402


def session_keys(chars, n, err_rate=0.0, ms=200.0):
    """Hand-built `summary["keys"]` for a make-believe session."""
    errs = int(round(n * err_rate))
    hits = n - errs
    return {
        ch: {"n": n, "err": errs, "ms_sum": ms * hits, "ms_n": hits}
        for ch in chars
    }


def blank_profile():
    return {"name": "test"}


class TestConfidence(unittest.TestCase):
    def test_fast_and_accurate_is_green(self):
        conf = adaptive.confidence({"ms": 160.0, "err": 0.0})
        self.assertGreaterEqual(conf, adaptive.GREEN)

    def test_slow_is_not_green(self):
        """
        TARGET_MS is the *start* of the journey (5 wpm), not a mid-point:
        scoring zero on speed now means typing as slowly as a beginner
        on day one, which is the whole span the heatmap has to show.
        """
        conf = adaptive.confidence({"ms": adaptive.TARGET_MS, "err": 0.0})
        self.assertLess(conf, adaptive.GREEN)
        self.assertAlmostEqual(conf, adaptive.ACC_WEIGHT)

    def test_a_beginners_pace_still_scores_something(self):
        """A kid at 10 wpm should see the heatmap move, not a flat wall."""
        conf = adaptive.confidence({"ms": 1200.0, "err": 0.0})
        self.assertGreater(conf, adaptive.ACC_WEIGHT)
        self.assertLess(conf, adaptive.GREEN)

    def test_error_rate_drags_it_down(self):
        clean = adaptive.confidence({"ms": 160.0, "err": 0.0})
        sloppy = adaptive.confidence({"ms": 160.0, "err": 0.25})
        self.assertLess(sloppy, clean)

    def test_never_typed_scores_zero_on_speed(self):
        self.assertAlmostEqual(
            adaptive.confidence({"ms": None, "err": 0.0}), adaptive.ACC_WEIGHT
        )

    def test_bounded(self):
        for entry in ({"ms": 0.0, "err": 0.0}, {"ms": 9999.0, "err": 5.0}):
            conf = adaptive.confidence(entry)
            self.assertGreaterEqual(conf, 0.0)
            self.assertLessEqual(conf, 1.0)

    def test_green_needs_evidence(self):
        entry = {"n": adaptive.MIN_SAMPLES - 1, "conf": 0.99,
                 "ms": adaptive.MASTER_MS - 20}
        self.assertFalse(adaptive.is_green(entry))
        entry["n"] = adaptive.MIN_SAMPLES
        self.assertTrue(adaptive.is_green(entry))

    def test_green_needs_the_goal_speed_not_just_a_good_score(self):
        """
        Mastery means 40 wpm. A weighted score can be dragged over the
        line by accuracy alone, so the speed gate is explicit -- without
        it the win condition would be reachable at half the target.
        """
        entry = {"n": 99, "conf": 0.99, "ms": adaptive.MASTER_MS + 60}
        self.assertFalse(adaptive.is_green(entry))
        entry["ms"] = adaptive.MASTER_MS - 1
        self.assertTrue(adaptive.is_green(entry))

    def test_a_key_never_typed_is_never_green(self):
        self.assertFalse(adaptive.is_green({"n": 99, "conf": 0.99, "ms": None}))


class TestMerge(unittest.TestCase):
    def test_migrates_a_profile_with_no_adaptive_keys(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("en", 30))
        self.assertEqual(p["alphabet"], adaptive.START_ALPHABET)
        self.assertIn("e", p["keys"])
        self.assertEqual(p["keys"]["e"]["n"], 30)

    def test_no_session_data_is_a_no_op(self):
        p = blank_profile()
        out = adaptive.merge_keys(p, None)
        self.assertEqual(out, {"green": [], "unlocked": []})
        self.assertEqual(p["keys"], {})

    def test_fast_accurate_typing_turns_keys_green(self):
        p = blank_profile()
        out = adaptive.merge_keys(p, session_keys("e", 40, err_rate=0.0, ms=170.0))
        self.assertEqual(out["green"], ["e"])
        self.assertTrue(adaptive.is_green(p["keys"]["e"]))

    def test_slow_sloppy_typing_does_not(self):
        p = blank_profile()
        out = adaptive.merge_keys(p, session_keys("e", 40, err_rate=0.3, ms=800.0))
        self.assertEqual(out["green"], [])
        self.assertFalse(adaptive.is_green(p["keys"]["e"]))

    def test_counts_accumulate_and_averages_are_recent_weighted(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("e", 20, ms=500.0))
        adaptive.merge_keys(p, session_keys("e", 20, ms=200.0))
        self.assertEqual(p["keys"]["e"]["n"], 40)
        # EMA: pulled toward the new session but not all the way there
        self.assertLess(p["keys"]["e"]["ms"], 500.0)
        self.assertGreater(p["keys"]["e"]["ms"], 200.0)

    def test_a_strong_session_unlocks_a_burst(self):
        """
        Ability is the only throttle. A kid holding their alphabet
        accurately AND at the goal speed is handed the maximum; nothing
        else -- not the calendar, not a per-session cap of one -- gets a
        say in how fast they progress.
        """
        p = blank_profile()
        out = adaptive.merge_keys(
            p, session_keys(adaptive.START_ALPHABET, 40, ms=170.0)
        )
        self.assertEqual(len(out["unlocked"]), adaptive.BURST_MAX)
        self.assertEqual(out["unlocked"][0], "s")
        self.assertEqual(p["alphabet"],
                         adaptive.START_ALPHABET + "".join(out["unlocked"]))

    def test_a_scrappy_session_unlocks_exactly_one(self):
        """Over the accuracy bar but not comfortably: progress, not a burst."""
        p = blank_profile()
        out = adaptive.merge_keys(
            p, session_keys(adaptive.START_ALPHABET, 60, err_rate=0.12,
                            ms=1500.0))
        self.assertEqual(out["unlocked"], ["s"])

    def test_the_burst_scales_with_performance(self):
        sizes = []
        for err, ms in ((0.12, 1500.0), (0.02, 1500.0), (0.01, 200.0)):
            p = blank_profile()
            out = adaptive.merge_keys(
                p, session_keys(adaptive.START_ALPHABET, 60, err_rate=err,
                                ms=ms))
            sizes.append(len(out["unlocked"]))
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(sizes[0], 1)
        self.assertEqual(sizes[-1], adaptive.BURST_MAX)

    def test_the_burst_is_capped(self):
        """Nobody is handed the whole deep end at once."""
        p = blank_profile()
        out = adaptive.merge_keys(
            p, session_keys(adaptive.START_ALPHABET, 500, ms=100.0))
        self.assertLessEqual(len(out["unlocked"]), adaptive.BURST_MAX)

    def test_one_weak_letter_blocks_the_unlock(self):
        """
        Unlocking is gated on accuracy now, not speed, so "weak" here
        means a key the kid keeps getting wrong -- being slow on it is
        no longer a reason to withhold the rest of the alphabet.
        """
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("enitr", 60, ms=170.0))
        out = adaptive.merge_keys(p, session_keys("l", 60, err_rate=0.5))
        self.assertEqual(out["unlocked"], [])
        self.assertEqual(p["alphabet"], adaptive.START_ALPHABET)

    def test_being_slow_does_not_block_the_unlock(self):
        """
        The fix this whole tuning pass exists for. A 5 wpm hunt-and-peck
        beginner types correctly, just slowly; withholding the alphabet
        until they get fast stalled every persona in tools/simulate.py
        for a simulated year.
        """
        p = blank_profile()
        slow = 12000.0 / 6.0        # about 6 wpm
        out = adaptive.merge_keys(
            p, session_keys(adaptive.START_ALPHABET, 60, ms=slow))
        self.assertTrue(out["unlocked"], "a slow but accurate kid must progress")
        self.assertEqual(out["unlocked"][0], "s")
        self.assertEqual(out["green"], [], "slow keys must not be mastered")

    def test_green_is_only_reported_on_the_way_up(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("e", 40, ms=170.0))
        out = adaptive.merge_keys(p, session_keys("e", 40, ms=170.0))
        self.assertEqual(out["green"], [])

    def test_unlocking_never_runs_past_the_alphabet(self):
        p = blank_profile()
        p["alphabet"] = adaptive.FREQ_ORDER
        out = adaptive.merge_keys(p, session_keys(adaptive.FREQ_ORDER, 40, ms=170.0))
        self.assertEqual(out["unlocked"], [])
        self.assertEqual(p["alphabet"], adaptive.FREQ_ORDER)

    def test_non_letters_are_tracked_but_never_unlock_anything(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("7,", 40, ms=170.0))
        self.assertIn("7", p["keys"])
        self.assertEqual(p["alphabet"], adaptive.START_ALPHABET)


class TestFocusAndWeighting(unittest.TestCase):
    def test_focus_is_the_weakest_unlocked_letter(self):
        """
        The weak letter has to be *inaccurate* to keep the alphabet
        still: a merely slow one no longer blocks an unlock, and a
        freshly unlocked letter takes the focus for itself.
        """
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("enitr", 40, ms=170.0))
        adaptive.merge_keys(p, session_keys("l", 40, err_rate=0.5))
        self.assertEqual(p["alphabet"], adaptive.START_ALPHABET)
        self.assertEqual(adaptive.focus_letter(p), "l")

    def test_a_freshly_unlocked_letter_takes_the_focus(self):
        p = blank_profile()
        out = adaptive.merge_keys(
            p, session_keys(adaptive.START_ALPHABET, 60, ms=170.0))
        self.assertTrue(out["unlocked"])
        self.assertIn(adaptive.focus_letter(p), out["unlocked"])

    def test_untyped_letters_sort_first(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("enitr", 40, ms=400.0))
        self.assertEqual(adaptive.focus_letter(p), "l")

    def test_weighted_char_favors_weak_keys(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("enitr", 60, ms=155.0))
        adaptive.merge_keys(p, session_keys("l", 60, ms=1500.0))
        rng = random.Random(11)
        draws = [adaptive.weighted_char(p, rng) for _ in range(3000)]
        weak = draws.count("l")
        strong = draws.count("e")
        self.assertGreater(weak, strong * 2)
        self.assertGreater(strong, 0)  # mastered keys stay in rotation

    def test_weighted_char_only_returns_unlocked_letters(self):
        p = blank_profile()
        adaptive.ensure(p)
        rng = random.Random(3)
        for _ in range(200):
            self.assertIn(adaptive.weighted_char(p, rng), p["alphabet"])


class TestKeyState(unittest.TestCase):
    def test_states(self):
        p = blank_profile()
        adaptive.merge_keys(p, session_keys("e", 40, ms=170.0))
        self.assertEqual(adaptive.key_state(p, "e"), "green")
        self.assertEqual(adaptive.key_state(p, "n"), "learning")
        self.assertEqual(adaptive.key_state(p, "z"), "locked")


class TestWordGeneration(unittest.TestCase):
    ALPHABETS = [
        adaptive.START_ALPHABET,
        "enitrlsauo",
        "enitrlsauodychgmpb",
        adaptive.FREQ_ORDER,
    ]

    def test_words_respect_alphabet_and_focus(self):
        rng = random.Random(42)
        for letters in self.ALPHABETS:
            for focus in letters:
                for _ in range(20):
                    w = adaptive.generate_word(letters, focus, rng)
                    self.assertTrue(w, "empty word for %r/%r" % (letters, focus))
                    self.assertIn(focus, w)
                    self.assertTrue(set(w) <= set(letters), w)

    def test_length_bounds(self):
        rng = random.Random(5)
        for _ in range(300):
            w = adaptive.generate_word("enitrlsauo", "a", rng)
            self.assertGreaterEqual(len(w), adaptive.MIN_WORD)
            # injection can push one past max_len; one over is the ceiling
            self.assertLessEqual(len(w), adaptive.MAX_WORD + 1)

    def test_deterministic_under_a_seed(self):
        a = [adaptive.generate_word("enitrl", "t", random.Random(9))
             for _ in range(5)]
        b = [adaptive.generate_word("enitrl", "t", random.Random(9))
             for _ in range(5)]
        self.assertEqual(a, b)

    def test_six_letter_alphabet_still_varies(self):
        rng = random.Random(1)
        words = {adaptive.generate_word("enitrl", "l", rng) for _ in range(60)}
        self.assertGreater(len(words), 20)

    def test_words_are_pronounceable_ish(self):
        """
        No keyboard mash: never three consonants in a row, and the vast
        majority of words survive the full onset/coda check even when the
        focus letter had to be injected.
        """
        rng = random.Random(77)
        for letters in self.ALPHABETS:
            speakable = total = 0
            for focus in letters:
                for _ in range(20):
                    w = adaptive.generate_word(letters, focus, rng)
                    self.assertNotRegex(w, r"[^aeiouy]{3}", w)
                    total += 1
                    speakable += adaptive._speakable(w)
            self.assertGreater(speakable, 0.9 * total,
                               "%s: %d/%d speakable" % (letters, speakable, total))

    def test_focus_outside_the_alphabet_still_appears(self):
        rng = random.Random(2)
        w = adaptive.generate_word("enitrl", "q", rng)
        self.assertIn("q", w)


class TestLesson(unittest.TestCase):
    def test_shape(self):
        p = blank_profile()
        adaptive.ensure(p)
        words = adaptive.generate_lesson(p, 12, random.Random(4))
        self.assertEqual(len(words), 12)
        for w in words:
            self.assertTrue(set(w) <= set(p["alphabet"]), w)

    def test_real_words_get_mixed_in_once_the_alphabet_is_wide(self):
        p = blank_profile()
        p["alphabet"] = adaptive.FREQ_ORDER
        p["keys"] = {}
        words = adaptive.generate_lesson(p, 20, random.Random(6))
        from core import lessons
        real = {w for lvl in lessons.LEVELS for w in lvl["words"]}
        self.assertTrue(real & set(words))

    def test_deterministic_under_a_seed(self):
        p = blank_profile()
        adaptive.ensure(p)
        a = adaptive.generate_lesson(p, 10, random.Random(8))
        b = adaptive.generate_lesson(p, 10, random.Random(8))
        self.assertEqual(a, b)


class TestSessionCapture(unittest.TestCase):
    def test_modes_that_ignore_ch_are_unchanged(self):
        s = engine.Session()
        for _ in range(10):
            s.keystroke(True)
        s.keystroke(False)
        self.assertNotIn("keys", s.summary())
        self.assertEqual(s.correct_chars, 10)
        self.assertEqual(s.wrong_chars, 1)

    def test_per_key_capture(self):
        s = engine.Session()
        s.keystroke(True, ch="e")
        s.keystroke(False, ch="e")
        s.keystroke(True, ch="n")
        keys = s.summary()["keys"]
        self.assertEqual(keys["e"]["n"], 2)
        self.assertEqual(keys["e"]["err"], 1)
        self.assertEqual(keys["n"]["n"], 1)
        # first keystroke has no predecessor, and the wrong one isn't timed
        self.assertEqual(keys["e"]["ms_n"], 0)
        self.assertEqual(keys["n"]["ms_n"], 1)

    def test_space_is_not_a_key(self):
        s = engine.Session()
        s.keystroke(True, ch=" ")
        self.assertNotIn("keys", s.summary())
        self.assertEqual(s.correct_chars, 1)

    def test_capture_feeds_the_merge(self):
        s = engine.Session()
        for _ in range(adaptive.MIN_SAMPLES + 5):
            s.keystroke(True, ch="e")
        p = blank_profile()
        adaptive.merge_keys(p, s.summary()["keys"])
        self.assertEqual(p["keys"]["e"]["n"], adaptive.MIN_SAMPLES + 5)


if __name__ == "__main__":
    unittest.main()
