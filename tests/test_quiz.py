"""
Whisker Quiz -- issue #26.

The acceptance criteria are almost entirely about tolerance: malformed
lines must not crash, an empty file must hide the mode, and answer
matching must forgive case and whitespace. All three are things a parent
editing quiz.txt by hand will hit on their first try.
"""

import os
import random
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, fx, profiles  # noqa: E402
from modes import quiz  # noqa: E402


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


def no_color():
    return (
        mock.patch.multiple("core.ui",
                            cp=mock.Mock(return_value=0),
                            cat_color=mock.Mock(return_value=0)),
        mock.patch.object(quiz, "cp", mock.Mock(return_value=0)),
    )


def write_quiz(d, text):
    p = os.path.join(d, "q.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


class TestLoading(unittest.TestCase):
    def tearDown(self):
        quiz.reset_cache()

    def test_the_shipped_file_loads(self):
        self.assertGreaterEqual(len(quiz.load()), 40)

    def test_entries_are_question_and_answer_list(self):
        for q, answers in quiz.load():
            self.assertTrue(q)
            self.assertTrue(answers)
            for a in answers:
                self.assertEqual(a, quiz.normalize(a))

    def test_loading_is_cached(self):
        self.assertIs(quiz.load(), quiz.load())

    def test_malformed_lines_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_quiz(d, "\n".join([
                "no pipe at all",
                "|missing question",
                "missing answer|",
                "  |  ",
                "# a comment|not a question",
                "",
                "good one|yes",
                "spaced | ANSWER ",
            ]))
            quiz.reset_cache()
            got = quiz.load(p)
            self.assertEqual(got, [("good one", ["yes"]),
                                   ("spaced", ["answer"])])

    def test_an_empty_file_yields_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_quiz(d, "# only comments\n\n")
            quiz.reset_cache()
            self.assertEqual(quiz.load(p), [])

    def test_a_missing_file_yields_nothing(self):
        quiz.reset_cache()
        self.assertEqual(quiz.load("/nope/not/here.txt"), [])

    def test_alternates_split_on_semicolons(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_quiz(d, "How many?|8;eight; EIGHT \n")
            quiz.reset_cache()
            self.assertEqual(quiz.load(p), [("How many?", ["8", "eight", "eight"])])


class TestAvailability(unittest.TestCase):
    """'Empty file hides the mode gracefully.'"""

    def tearDown(self):
        quiz.reset_cache()

    def test_available_with_the_shipped_questions(self):
        self.assertTrue(quiz.available(profiles._blank_profile("T")))

    def test_hidden_when_there_are_no_questions(self):
        with mock.patch.object(quiz, "load", return_value=[]):
            self.assertFalse(quiz.available(profiles._blank_profile("T")))

    def test_the_arcade_drops_it_when_hidden(self):
        import main
        p = profiles._blank_profile("T")
        with mock.patch.object(quiz, "load", return_value=[]):
            labels = [lbl for _, _, lbl, _ in main.arcade_for(p)]
            self.assertNotIn("Whisker Quiz", labels)
        labels = [lbl for _, _, lbl, _ in main.arcade_for(p)]
        self.assertIn("Whisker Quiz", labels)


class TestForgivingMatching(unittest.TestCase):
    def test_case_is_ignored(self):
        self.assertTrue(quiz.is_correct("PARIS", ["paris"]))
        self.assertTrue(quiz.is_correct("Paris", ["paris"]))

    def test_surrounding_whitespace_is_ignored(self):
        self.assertTrue(quiz.is_correct("   paris  ", ["paris"]))
        self.assertTrue(quiz.is_correct("\tparis\n", ["paris"]))

    def test_internal_runs_of_space_collapse(self):
        self.assertTrue(quiz.is_correct("ice    cream", ["ice cream"]))
        self.assertTrue(quiz.is_correct(" ice  cream ", ["ice cream"]))

    def test_any_listed_alternate_is_accepted(self):
        for given in ("8", "eight", "EIGHT", " Eight "):
            self.assertTrue(quiz.is_correct(given, ["8", "eight"]), given)

    def test_a_genuinely_wrong_answer_is_still_wrong(self):
        self.assertFalse(quiz.is_correct("nine", ["8", "eight"]))
        self.assertFalse(quiz.is_correct("", ["8"]))

    def test_normalize_is_idempotent(self):
        for s in ("  A  B  ", "x", "ICE  CREAM"):
            once = quiz.normalize(s)
            self.assertEqual(once, quiz.normalize(once))

    def test_every_shipped_answer_matches_itself(self):
        """A question nobody can answer correctly is a broken question."""
        for q, answers in quiz.load():
            for a in answers:
                self.assertTrue(quiz.is_correct(a, answers), q)
                self.assertTrue(quiz.is_correct(a.upper(), answers), q)
                self.assertTrue(quiz.is_correct("  %s " % a, answers), q)


class TestRoundBuilding(unittest.TestCase):
    def test_a_round_is_the_configured_length(self):
        self.assertEqual(len(quiz.pick_round(quiz.load(), random.Random(1))),
                         quiz.ROUND)

    def test_a_round_has_no_repeats(self):
        picked = quiz.pick_round(quiz.load(), random.Random(2))
        self.assertEqual(len({q for q, _ in picked}), len(picked))

    def test_a_short_pool_gives_a_short_round(self):
        small = [("a", ["1"]), ("b", ["2"])]
        self.assertEqual(len(quiz.pick_round(small, random.Random(1))), 2)

    def test_round_is_within_the_spec_range(self):
        """#26 asks for 8-10 questions."""
        self.assertGreaterEqual(quiz.ROUND, 8)
        self.assertLessEqual(quiz.ROUND, 10)


class TestKindness(unittest.TestCase):
    """No lives, and a missed question comes back exactly once."""

    def _body(self):
        with open(quiz.__file__, encoding="utf-8") as fh:
            return fh.read().split('"""', 2)[-1]

    def test_there_are_no_lives(self):
        body = self._body()
        for banned in ("lives", "game over", "fish -=", "current_streak"):
            self.assertNotIn(banned, body.lower(), banned)

    def test_a_question_returns_only_once(self):
        self.assertEqual(quiz.RETRY_LIMIT, 1)

    def test_the_wrong_answer_message_shows_the_right_one(self):
        self.assertIn("it's '%s'", self._body())


class TestWrapping(unittest.TestCase):
    def test_long_questions_wrap_within_width(self):
        q = "What is the name of the very large grey animal with a long trunk?"
        for width in (20, 30, 52):
            for line in quiz._wrap(q, width):
                self.assertLessEqual(len(line), width, line)

    def test_wrapping_keeps_every_word(self):
        q = "one two three four five six seven eight nine ten"
        self.assertEqual(" ".join(quiz._wrap(q, 12)).split(), q.split())

    def test_a_word_longer_than_the_width_still_comes_back(self):
        self.assertTrue(quiz._wrap("supercalifragilistic", 8))

    def test_empty_text_is_survivable(self):
        self.assertEqual(quiz._wrap("", 20), [""])

    def test_every_shipped_question_wraps_into_the_bubble(self):
        for q, _ in quiz.load():
            for line in quiz._wrap(q, 52):
                self.assertLessEqual(len(line), 52, q)


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
        kw = dict(pose="sit", question="How many legs does a cat have?",
                  typed="4", index=2, total=8, right=1,
                  msg="Yes! That's right.", msg_ok=True)
        kw.update(over)
        quiz._draw(win, kitty, kw["pose"], kw["question"], kw["typed"],
                   kw["index"], kw["total"], kw["right"], kw["msg"],
                   kw["msg_ok"])

    def test_draws_with_and_without_a_cat(self):
        for kitty in (cat.Cat(4242, "Mittens"), None):
            win = FakeWin()
            self._draw(win, kitty)
            self.assertTrue(win.written)

    def test_draws_every_pose(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for pose in ("sit", "overjoyed", "wary"):
            self._draw(win, kitty, pose=pose, msg_ok=(pose != "wary"))

    def test_every_shipped_question_renders(self):
        win = FakeWin()
        kitty = cat.Cat(4242, "Mittens")
        for q, answers in quiz.load():
            self._draw(win, kitty, question=q,
                       msg="Not quite -- it's '%s'. We'll come back to it."
                           % answers[0], msg_ok=False)

    def test_a_full_answer_box_fits(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), typed="x" * quiz.MAX_ANSWER)

    def test_a_very_long_question_fits(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), question="word " * 24)

    def test_narrow_screen_does_not_escape(self):
        for kitty in (cat.Cat(4242), None):
            win = FakeWin(h=20, w=60)
            self._draw(win, kitty)

    def test_an_adult_cat_fits(self):
        win = FakeWin()
        self._draw(win, cat.Cat(4242, "Mittens", growth=3))


class TestRegistration(unittest.TestCase):
    def test_it_is_in_the_arcade(self):
        import main
        labels = [lbl for _, _, lbl, _ in main.arcade_for(
            profiles._blank_profile("T"))]
        self.assertIn("Whisker Quiz", labels)

    def test_counter_migrates_on_old_saves(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        self.assertEqual(p["quiz_right"], 0)


if __name__ == "__main__":
    unittest.main()
