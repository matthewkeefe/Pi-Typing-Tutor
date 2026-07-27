"""
Alphabet Soup -- issue #25.

The rules this mode most needs protecting are negative ones: nothing is
penalised, and per-key capture stays off. Both are the kind of thing a
later well-intentioned edit adds back, so they're asserted directly.
"""

import os
import random
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, fx, profiles, wordlist  # noqa: E402
from modes import soup  # noqa: E402


class FakeWin:
    """A window that refuses to be written outside its bounds."""

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


def no_color():
    return (
        mock.patch.multiple("core.ui",
                            cp=mock.Mock(return_value=0),
                            cat_color=mock.Mock(return_value=0)),
        mock.patch.object(soup, "cp", mock.Mock(return_value=0)),
    )


def source():
    with open(soup.__file__, encoding="utf-8") as fh:
        return fh.read()


def body():
    """Source with the module docstring stripped, for rule assertions."""
    return source().split('"""', 2)[-1]


def a_profile(letters=None):
    p = profiles._blank_profile("Test")
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0}
    if letters:
        p["alphabet"] = letters
    return p


class TestNoUnlockGate(unittest.TestCase):
    """
    The bowl is the whole alphabet, so the mode is open from day one.

    It used to hide until twelve letters were unlocked, because a bowl
    built from the *unlocked* set is unsolvable early -- the starting six
    letters yield exactly two viable bowls in the entire word list.
    Sourcing the bowl from all twenty-six removed the reason for the gate
    rather than merely relaxing it.
    """

    def test_open_to_a_brand_new_kid(self):
        self.assertTrue(soup.available(a_profile()))

    def test_open_at_every_alphabet_size(self):
        for n in range(1, 27):
            self.assertTrue(soup.available(a_profile(adaptive.FREQ_ORDER[:n])), n)

    def test_the_bowl_ignores_what_the_kid_has_unlocked(self):
        """A six-letter kid and a full-alphabet kid draw from one pool."""
        self.assertEqual(sorted(soup.FULL_ALPHABET),
                         sorted(adaptive.FREQ_ORDER))
        self.assertEqual(len(soup.FULL_ALPHABET), 26)

    def test_it_no_longer_reads_the_profile_alphabet(self):
        """
        The bug this replaces would be silent: pass the unlocked set to
        make_bowl and an early kid gets "the soup pot is empty" instead
        of a game.
        """
        self.assertNotIn("adaptive.alphabet(", body())
        self.assertIn("make_bowl(FULL_ALPHABET", body())

    def test_the_check_is_cheap_enough_for_every_menu_draw(self):
        import time
        p = a_profile(adaptive.FREQ_ORDER)
        t = time.time()
        for _ in range(2000):
            soup.available(p)
        self.assertLess(time.time() - t, 0.5)

    def test_the_full_alphabet_gives_plenty_of_bowls(self):
        self.assertGreater(wordlist.viable(soup.FULL_ALPHABET), 30)

    def test_a_beginner_actually_gets_a_solvable_bowl(self):
        """The thing the gate existed to prevent, now simply not true."""
        import random
        made = wordlist.make_bowl(soup.FULL_ALPHABET, random.Random(7))
        self.assertIsNotNone(made)
        tiles, solutions = made
        self.assertGreaterEqual(len(solutions), 1)
        self.assertTrue(all(t.isalpha() for t in tiles))


class TestNothingIsPenalised(unittest.TestCase):
    """#25: 'No penalties for invalid attempts; ESC ends round keeping score.'"""

    def assertNotInBody(self, needle):
        """assertNotIn dumps the whole module on failure -- keep it readable."""
        self.assertFalse(needle in body(), "%r appears in modes/soup.py" % needle)

    def test_score_is_never_reduced(self):
        for banned in ("score -=", "score //=", "score *="):
            self.assertNotInBody(banned)

    def test_score_is_only_ever_zeroed_once_at_the_start(self):
        """One initialiser is fine; a second assignment would be a reset."""
        self.assertEqual(body().count("score = 0"), 1)

    def test_no_time_is_taken_away(self):
        """
        `ROUND_SECONDS - (now - started)` is the legitimate remaining-time
        read; what must not exist is anything that moves the goalposts.
        """
        for banned in ("started +=", "remaining -=", "ROUND_SECONDS -="):
            self.assertNotInBody(banned)

    def test_found_words_are_never_removed(self):
        for banned in ("found.remove", "found.pop", "found.clear"):
            self.assertNotInBody(banned)

    def test_rejections_have_variety_so_they_do_not_nag(self):
        self.assertGreaterEqual(len(soup.SLURPS), 3)
        self.assertEqual(len(set(soup.SLURPS)), len(soup.SLURPS))
        for line in soup.SLURPS:
            self.assertTrue(line.isascii(), line)
            lowered = line.lower()
            for scold in ("wrong", "no!", "bad", "fail"):
                self.assertNotIn(scold, lowered, line)


class TestCaptureStaysOff(unittest.TestCase):
    """
    Logged decision on #25: the kid picks every word here, so this must not
    feed the adaptive engine. `keystroke` is only ever called without `ch`.
    """

    def test_no_keystroke_call_passes_an_expected_character(self):
        self.assertNotIn("ch=", body())

    def test_the_profile_key_data_is_never_touched(self):
        for banned in ('profile["keys"]', "adaptive.merge", "adaptive.record"):
            self.assertNotIn(banned, body(), banned)

    def test_the_unlocked_alphabet_is_neither_read_nor_written(self):
        """
        It used to be read, to build the bowl. Now the bowl is all 26
        letters and the kid's unlocked set is none of this mode's
        business in either direction.
        """
        self.assertNotIn("adaptive.alphabet(", body())
        self.assertNotIn('profile["alphabet"] =', body())


class TestScoring(unittest.TestCase):
    def test_longer_words_are_worth_disproportionately_more(self):
        self.assertGreater(soup.score_for("studio") / 6,
                           soup.score_for("cat") / 3)

    def test_score_rises_with_length(self):
        vals = [soup.score_for("x" * n) for n in range(3, 9)]
        self.assertEqual(vals, sorted(vals))
        self.assertEqual(len(set(vals)), len(vals))


class TestBowlFrame(unittest.TestCase):
    """
    The frame and the letters are drawn separately and must agree. They
    once disagreed by a column, which rendered the last two tiles as a
    smear ("hh") and skewed the borders -- invisible to a bounds check,
    so it gets asserted on the geometry directly.
    """

    def test_all_rows_are_the_same_width(self):
        for n in wordlist.BOWL_SIZES:
            rows = soup._bowl_rows(list("abcdefg"[:n]))
            self.assertEqual(len({len(r) for r in rows}), 1, rows)

    def test_the_letter_channel_is_blank_in_the_frame(self):
        for n in wordlist.BOWL_SIZES:
            tiles = list("abcdefg"[:n])
            rows = soup._bowl_rows(tiles)
            text = soup.tile_text(tiles)
            channel = rows[1][soup.LETTER_X:soup.LETTER_X + len(text)]
            self.assertEqual(channel.strip(), "",
                             "frame writes into the letter channel: %r" % rows[1])

    def test_the_letters_land_inside_the_bowl(self):
        for n in wordlist.BOWL_SIZES:
            tiles = list("abcdefg"[:n])
            rows = soup._bowl_rows(tiles)
            text = soup.tile_text(tiles)
            self.assertLessEqual(soup.LETTER_X + len(text), len(rows[1]) - 1,
                                 "letters overflow the bowl wall")

    def test_tile_text_keeps_every_letter_separate(self):
        tiles = list("aetgrhh")
        text = soup.tile_text(tiles)
        self.assertEqual(text.split(), tiles)
        self.assertEqual(text.count("h"), 2)

    def test_real_bowls_have_a_well_formed_frame(self):
        for trial in range(20):
            tiles, _ = wordlist.make_bowl(adaptive.FREQ_ORDER,
                                          random.Random(trial))
            rows = soup._bowl_rows(tiles)
            self.assertEqual(len({len(r) for r in rows}), 1, tiles)
            text = soup.tile_text(tiles)
            channel = rows[1][soup.LETTER_X:soup.LETTER_X + len(text)]
            self.assertEqual(channel.strip(), "", tiles)


class TestSteamGauge(unittest.TestCase):
    def test_it_never_reads_as_failure(self):
        for frac in (1.0, 0.5, 0.2, 0.0):
            text, _ = soup._steam(frac * soup.ROUND_SECONDS, soup.ROUND_SECONDS)
            lowered = text.lower()
            for scold in ("fail", "lose", "lost", "over", "dead"):
                self.assertNotIn(scold, lowered, text)

    def test_it_is_a_stable_width(self):
        widths = {len(soup._steam(r, soup.ROUND_SECONDS)[0].split("]")[0])
                  for r in (90, 60, 30, 5, 0)}
        self.assertEqual(len(widths), 1)

    def test_it_clamps_outside_the_round(self):
        for r in (-50.0, 0.0, soup.ROUND_SECONDS * 3):
            text, _ = soup._steam(r, soup.ROUND_SECONDS)
            bar = text.split("[")[1].split("]")[0]
            self.assertEqual(len(bar), 12)


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
        kw = dict(pose="sit", tiles=list("studio"), typed="stu",
                  found=["dot", "its"], score=18,
                  remaining=45.0, msg="nice!", msg_ok=True)
        kw.update(over)
        soup._draw(win, kitty, kw.pop("pose"), kw.pop("tiles"),
                   kw.pop("typed"), kw.pop("found"), kw.pop("score"),
                   kw.pop("remaining"), kw.pop("msg"), kw.pop("msg_ok"))

    def test_draws_with_and_without_a_cat(self):
        for kitty in (cat.Cat(4242, "Mittens"), None):
            win = FakeWin()
            self._draw(win, kitty)
            self.assertTrue(win.written)

    def test_draws_every_pose_and_gauge_state(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for pose in ("sit", "overjoyed", "wary"):
            for remaining in (90.0, 60.0, 20.0, 0.0):
                self._draw(win, kitty, pose=pose, remaining=remaining)

    def test_a_full_board_of_found_words_stays_on_screen(self):
        win = FakeWin()
        found = wordlist.for_alphabet(adaptive.FREQ_ORDER, min_len=3,
                                      max_len=8)[:120]
        self._draw(win, cat.Cat(1), found=found, score=9999)

    def test_seven_tile_bowls_fit(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), tiles=list("bathtub"))

    def test_long_message_and_long_typing_fit(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), typed="w" * 12, msg="x" * 78,
                   msg_ok=False)

    def test_real_generated_bowls_all_render(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for trial in range(20):
            tiles, sols = wordlist.make_bowl(adaptive.FREQ_ORDER,
                                             random.Random(trial))
            self._draw(win, kitty, tiles=tiles, found=sols[:8])

    def test_narrow_screen_does_not_escape(self):
        for kitty in (cat.Cat(4242), None):
            win = FakeWin(h=20, w=60)
            self._draw(win, kitty)


class TestRegistration(unittest.TestCase):
    def test_it_is_in_the_arcade_and_gated_there(self):
        import main
        labels = [lbl for _, _, lbl, _ in main.ARCADE]
        self.assertIn("Alphabet Soup", labels)

        # No longer gated: on the menu for a brand-new kid too.
        new_kid = a_profile()
        self.assertIn("Alphabet Soup",
                      [lbl for _, _, lbl, _ in main.arcade_for(new_kid)])

        older = a_profile(adaptive.FREQ_ORDER)
        self.assertIn("Alphabet Soup",
                      [lbl for _, _, lbl, _ in main.arcade_for(older)])

    def test_modes_without_the_hook_are_always_available(self):
        import main
        from modes import dino
        self.assertIsNone(getattr(dino, "available", None))
        self.assertIn("Dino Chomp",
                      [lbl for _, _, lbl, _ in main.arcade_for(a_profile())])

    def test_profile_defaults_migrate_on_old_saves(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        for key in ("soup_words_found", "soup_best_score", "soup_most_words"):
            self.assertEqual(p[key], 0, key)


if __name__ == "__main__":
    unittest.main()
