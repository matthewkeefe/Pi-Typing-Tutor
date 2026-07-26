"""
Mystery Word -- issue #24.

The two rules with teeth: words must always be solvable from the letters
the kid has actually met, and a failed round must cost nothing at all.
"""

import os
import random
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, fx, profiles, wordlist  # noqa: E402
from modes import mystery  # noqa: E402


class FakeWin:
    def __init__(self, h=24, w=80):
        self.h, self.w = h, w
        self.written = []

    def getmaxyx(self):
        return (self.h, self.w)

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.h and 0 <= x < self.w):
            raise AssertionError("wrote off-screen at %r,%r" % (y, x))
        if x + len(text) > self.w:
            raise AssertionError("wrote past the right edge at %r,%r" % (y, x))
        self.written.append((y, x, text))

    def erase(self):
        self.written = []

    def refresh(self):
        pass

    def render(self):
        """
        Reconstruct the screen as rows of text.

        Needed because the leak this guards against was painted one
        character at a time at consecutive columns -- searching the raw
        write list finds nothing, and searching the concatenation of all
        writes finds false positives in ordinary UI copy ("type a letter
        to guess" contains "letter").
        """
        grid = [[" "] * self.w for _ in range(self.h)]
        for y, x, text in self.written:
            for i, ch in enumerate(text):
                if 0 <= y < self.h and 0 <= x + i < self.w:
                    grid[y][x + i] = ch
        return ["".join(row) for row in grid]


def no_color():
    return (
        mock.patch.multiple("core.ui",
                            cp=mock.Mock(return_value=0),
                            cat_color=mock.Mock(return_value=0)),
        mock.patch.object(mystery, "cp", mock.Mock(return_value=0)),
    )


def body():
    with open(mystery.__file__, encoding="utf-8") as fh:
        return fh.read().split('"""', 2)[-1]


class TestSolvability(unittest.TestCase):
    """#24: 'Words always solvable from the kid's unlocked letters.'"""

    def test_every_candidate_uses_only_unlocked_letters(self):
        for n in range(6, 27):
            alpha = set(adaptive.FREQ_ORDER[:n])
            for word in mystery.candidates("".join(alpha)):
                self.assertTrue(set(word) <= alpha,
                                "%s needs letters outside %s" % (word, alpha))

    def test_every_candidate_is_a_real_word(self):
        words = wordlist.load()
        for word in mystery.candidates(adaptive.FREQ_ORDER[:14]):
            self.assertIn(word, words)

    def test_the_starting_alphabet_still_has_something(self):
        pool = mystery.candidates(adaptive.START_ALPHABET)
        self.assertGreaterEqual(len(pool), 5, pool)

    def test_picked_words_come_from_the_pool_and_are_distinct(self):
        for n in (6, 10, 16, 26):
            alpha = adaptive.FREQ_ORDER[:n]
            pool = set(mystery.candidates(alpha))
            picked = mystery.pick_words(alpha, random.Random(1))
            self.assertEqual(len(picked), len(set(picked)))
            for w in picked:
                self.assertIn(w, pool)

    def test_an_empty_alphabet_yields_nothing_rather_than_raising(self):
        self.assertEqual(mystery.pick_words("q", random.Random(1)), [])


class TestWordLengths(unittest.TestCase):
    def test_length_ceiling_grows_with_the_alphabet(self):
        highs = [mystery.word_lengths(adaptive.FREQ_ORDER[:n])[1]
                 for n in (6, 10, 16, 21, 26)]
        self.assertEqual(highs, sorted(highs))
        self.assertLessEqual(max(highs), 8)

    def test_the_floor_never_moves(self):
        for n in range(6, 27):
            self.assertEqual(mystery.word_lengths(adaptive.FREQ_ORDER[:n])[0], 3)

    def test_candidates_respect_the_bounds(self):
        for n in (6, 12, 26):
            alpha = adaptive.FREQ_ORDER[:n]
            lo, hi = mystery.word_lengths(alpha)
            for w in mystery.candidates(alpha):
                self.assertTrue(lo <= len(w) <= hi, w)


class TestRevealLogic(unittest.TestCase):
    def test_target_is_based_on_distinct_letters(self):
        self.assertEqual(mystery.reveal_target("letter"), 2)   # l e t r -> 4
        self.assertEqual(mystery.reveal_target("aaa"), 1)

    def test_target_is_always_reachable(self):
        for word in mystery.candidates(adaptive.FREQ_ORDER[:16]):
            self.assertLessEqual(mystery.reveal_target(word), len(set(word)))
            self.assertGreaterEqual(mystery.reveal_target(word), 1)

    def test_masked_hides_what_has_not_been_guessed(self):
        self.assertEqual(mystery.masked("cat", set()), "_ _ _")
        self.assertEqual(mystery.masked("cat", {"a"}), "_ a _")
        self.assertEqual(mystery.masked("letter", {"e", "t"}), "_ e t t e _")

    def test_masked_reveals_every_instance_of_a_letter(self):
        self.assertEqual(mystery.masked("letter", {"t"}).count("t"), 2)

    def test_is_solved_needs_every_distinct_letter(self):
        self.assertFalse(mystery.is_solved("cat", {"c", "a"}))
        self.assertTrue(mystery.is_solved("cat", {"c", "a", "t"}))
        self.assertTrue(mystery.is_solved("letter", set("letr")))


class TestWhiskerMeter(unittest.TestCase):
    def test_it_is_a_constant_width(self):
        widths = {len(mystery._whiskers(n))
                  for n in range(0, mystery.MAX_WRONG + 1)}
        self.assertEqual(widths, {mystery.MAX_WRONG})

    def test_it_droops_monotonically(self):
        droops = [mystery._whiskers(n).count(".")
                  for n in range(0, mystery.MAX_WRONG + 1)]
        self.assertEqual(droops, sorted(droops))
        self.assertEqual(droops[-1], mystery.MAX_WRONG)

    def test_it_is_terminal_safe(self):
        for n in range(0, mystery.MAX_WRONG + 1):
            w = mystery._whiskers(n)
            self.assertTrue(w.isascii() and w.isprintable(), w)


class TestNothingIsLost(unittest.TestCase):
    """#24: 'Soft-fail only: no lives, no streak/fish loss on a failed round.'"""

    def test_nothing_touches_fish_streaks_or_care(self):
        for banned in ('profile["fish"]', "fish -=", "current_streak",
                       "stamp_care", "set_wary", "lives"):
            self.assertFalse(banned in body(),
                             "%r appears in modes/mystery.py" % banned)

    def test_the_failure_message_carries_no_blame(self):
        src = body()
        self.assertIn("Maybe tomorrow", src)
        for scold in ("you failed", "you lose", "too bad", "wrong again"):
            self.assertNotIn(scold, src.lower(), scold)


class TestCaptureOnFinalWordOnly(unittest.TestCase):
    """
    #24: 'Per-key capture on final-word typing only (guesses are
    production, not drill data).' Letter guessing is deduction; only the
    spelling phase reports keystrokes.
    """

    def test_keystroke_is_only_called_in_the_spelling_branch(self):
        src = body()
        guess_part = src.split("# --- guessing phase ---", 1)[1]
        self.assertNotIn("sess.keystroke", guess_part)

    def test_the_spelling_branch_does_capture_with_an_expected_char(self):
        self.assertIn("sess.keystroke(True, ch=expected)", body())
        self.assertIn("sess.keystroke(False, ch=expected)", body())


class TestRendering(unittest.TestCase):
    def setUp(self):
        fx.clear()
        self._patches = no_color()
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def _draw(self, win, kitty, **over):
        kw = dict(pose="swat", word="letter", found={"e", "t"}, wrong=2,
                  dish=1, total=3, spelling=False, typed="", msg="Yes!",
                  msg_ok=True, opened=False)
        kw.update(over)
        mystery._draw(win, kitty, kw["pose"], kw["word"], kw["found"],
                      kw["wrong"], kw["dish"], kw["total"], kw["spelling"],
                      kw["typed"], kw["msg"], kw["msg_ok"], kw["opened"])

    def test_draws_with_and_without_a_cat(self):
        for kitty in (cat.Cat(4242, "Mittens"), None):
            win = FakeWin()
            self._draw(win, kitty)
            self.assertTrue(win.written)

    def test_draws_every_phase(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for spelling in (False, True):
            for opened in (False, True):
                for wrong in range(0, mystery.MAX_WRONG + 1):
                    self._draw(win, kitty, spelling=spelling, opened=opened,
                               wrong=wrong, typed="let" if spelling else "")

    def test_the_longest_possible_word_fits(self):
        win = FakeWin()
        longest = max(mystery.candidates(adaptive.FREQ_ORDER), key=len)
        self._draw(win, cat.Cat(1), word=longest, found=set(longest[:2]),
                   spelling=True, typed=longest[:3])

    def test_a_full_alphabet_of_guesses_fits(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), found=set("abcdefghijklmnopqrstuvwxyz"))

    def test_real_words_all_render(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        pool = mystery.candidates(adaptive.FREQ_ORDER)
        for word in pool[::97]:
            self._draw(win, kitty, word=word, found=set(word[:1]))

    def test_narrow_screen_does_not_escape(self):
        for kitty in (cat.Cat(4242), None):
            win = FakeWin(h=20, w=60)
            self._draw(win, kitty)

    def test_the_answer_is_never_painted_while_it_is_still_hidden(self):
        """
        The whole mode is producing a word you cannot see. `draw_typing_line`
        renders the *target*, which is right everywhere else and would hand
        the kid the answer here -- it once did exactly that.

        Checked against the reconstructed screen with spaces squeezed out,
        so a letter-spaced "l e t t e r" counts as a leak too.
        """
        for word in ("letter", "studio", "cat", "hazelnut"):
            for typed in ("", word[:1], word[:len(word) - 1]):
                win = FakeWin()
                self._draw(win, cat.Cat(1), word=word, found=set(word[:1]),
                           spelling=True, typed=typed, msg="", opened=False)
                for y, row in enumerate(win.render()):
                    squeezed = row.replace(" ", "")
                    self.assertNotIn(word, squeezed,
                                     "%r leaked on row %d with typed=%r: %r"
                                     % (word, y, typed, row.strip()))

    def test_the_mask_never_leaks_unguessed_letters(self):
        for word in ("letter", "studio", "hazelnut"):
            self.assertNotIn(word, mystery.masked(word, set()).replace(" ", ""))
            partial = mystery.masked(word, {word[0]}).replace(" ", "")
            self.assertNotIn(word, partial)

    def test_progress_is_still_visible_while_spelling(self):
        """Hiding the answer must not mean hiding the kid's own typing."""
        win = FakeWin()
        self._draw(win, cat.Cat(1), word="letter", found={"e"},
                   spelling=True, typed="let", msg="")
        squeezed = [r.replace(" ", "") for r in win.render()]
        self.assertTrue(any("let__" in r for r in squeezed),
                        "the kid's own typing should be on screen")

    def test_lid_art_is_well_formed(self):
        for art in (mystery.LID, mystery.LID_OPEN):
            self.assertEqual(len({len(r) for r in art}), 1, art)
            for row in art:
                self.assertTrue(row.isascii() and row.isprintable(), row)


class TestRegistration(unittest.TestCase):
    def test_it_is_in_the_arcade(self):
        import main
        labels = [lbl for _, _, lbl, _ in main.arcade_for(
            profiles._blank_profile("T"))]
        self.assertIn("Mystery Word", labels)

    def test_counter_migrates_on_old_saves(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        self.assertEqual(p["mystery_opened"], 0)


if __name__ == "__main__":
    unittest.main()
