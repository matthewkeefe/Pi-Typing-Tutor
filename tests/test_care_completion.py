"""
A care task is only done when it's actually done.

THE BUG, found by a six-year-old in about fifteen seconds:

    press ESC part-way through a care activity and it counted as
    complete. It just ended early.

Every typed task stamped on a truthy COUNT -- `if caught:`, `if done:` --
which reads as "did anything happen at all". One fish and ESC ticked Feed
off for the day. Five tasks, five escapes, and the whole board was done
without a child meaning to cheat, or noticing they had.

The tell was sitting right there in the code: the wrap-up screen already
branched on `done >= total` and would cheerfully say "got 1 fish, good
enough for now!" on the same screen that marked the chore finished.

734 tests missed it because not one of them ran a care activity's key
loop. These do -- they drive the real `_run_units` and the real
`feed.play` with a scripted keyboard, ESC and all.

What must NOT change while fixing it: stopping early is still free. The
typing still counts toward the adaptive engine, nothing is taken away,
and there is no scolding. The only thing ESC no longer does is claim the
chore was finished.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, profiles  # noqa: E402
from modes import care, feed  # noqa: E402

ESC = 27


class Keyboard:
    """A scripted keyboard: types the given text, then presses ESC."""

    def __init__(self, keys):
        self.keys = list(keys)
        self.exhausted = 0

    def next(self):
        if self.keys:
            return self.keys.pop(0)
        # Never hang a test: once the script runs out, keep quitting.
        self.exhausted += 1
        if self.exhausted > 5000:
            raise AssertionError("mode never exited")
        return ESC


class FakeWin:
    def __init__(self, keyboard, h=24, w=80):
        self.kb = keyboard
        self.h, self.w = h, w

    def getmaxyx(self):
        return (self.h, self.w)

    def getch(self):
        return self.kb.next()

    def addstr(self, *a, **k):
        pass

    def erase(self):
        pass

    def refresh(self):
        pass

    def nodelay(self, *a):
        pass

    def keypad(self, *a):
        pass


def quiet():
    """Silence curses and the between-screens messages."""
    zero = mock.Mock(return_value=0)
    return (
        mock.patch.multiple("core.ui", cp=zero, cat_color=zero,
                            message=mock.Mock(), celebrate=mock.Mock(),
                            safe_addstr=mock.Mock(), center=mock.Mock(),
                            draw_typing_line=mock.Mock()),
        mock.patch.object(care, "cp", zero),
        mock.patch.object(care, "safe_addstr", mock.Mock()),
        mock.patch.object(care, "center", mock.Mock()),
        mock.patch.object(feed, "cp", zero),
        mock.patch.object(feed, "safe_addstr", mock.Mock()),
        mock.patch.object(feed, "center", mock.Mock()),
        mock.patch("curses.curs_set", mock.Mock()),
        mock.patch("curses.napms", mock.Mock()),
    )


class Harness:
    def setUp(self):
        self._p = quiet()
        for p in self._p:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._p:
            p.stop()

    def a_profile(self):
        p = profiles._blank_profile("Kid")
        p["cat"] = cat.blank_cat_data(4242, "Mochi", "2026-07-01")
        p["cat"]["care"] = {}
        return p

    def run_task(self, task, profile, text):
        """Play `task`, typing `text`, then ESC. Returns the profile."""
        win = FakeWin(Keyboard([ord(c) for c in text]))
        if task == "food":
            feed.play(win, profile)
        else:
            care.TASK_RUNNERS[task](win, profile)
        return profile

    def stamped(self, profile, task):
        return task in (profile.get("cat", {}).get("care") or {})


class TestEscapeDoesNotComplete(Harness, unittest.TestCase):
    """The reported bug, one test per task."""

    def test_escaping_immediately_completes_nothing(self):
        for task in ("food", "water", "pets", "clean"):
            p = self.a_profile()
            self.run_task(task, p, "")          # straight to ESC
            self.assertFalse(self.stamped(p, task),
                             "%s stamped on an instant ESC" % task)

    def test_escaping_after_a_little_typing_completes_nothing(self):
        """
        The exact shape of the bug: real progress, then ESC. This is what
        `if done:` treated as a finished chore.
        """
        for task in ("food", "water", "pets", "clean"):
            p = self.a_profile()
            self.run_task(task, p, "the cat sat")
            self.assertFalse(self.stamped(p, task),
                             "%s stamped after a partial run" % task)

    def test_the_whole_board_cannot_be_escaped_through(self):
        """
        Five tasks, five escapes. The reported consequence: a board that
        looks fully done without anything being done.
        """
        p = self.a_profile()
        for task in ("food", "water", "pets", "clean"):
            self.run_task(task, p, "cat")
        self.assertEqual(p["cat"]["care"], {})
        self.assertFalse(cat.care_done_today(p))


class TestFinishingStillWorks(Harness, unittest.TestCase):
    """
    The other half. A fix that stops ESC from completing a task is no
    good if it also stops finishing from completing it.
    """

    def _type_all(self, units):
        return "".join(units)

    def test_typing_every_unit_stamps_the_task(self):
        p = self.a_profile()
        with mock.patch.object(care, "_clean_units",
                               lambda *a, **k: ["12,"]):
            self.run_task("clean", p, "12,")
        self.assertTrue(self.stamped(p, "clean"))

    def test_pets_stamps_when_the_phrase_is_finished(self):
        # Narrow the phrase list rather than the RNG: patching
        # random.Random reaches the cat's own gene draws and hands them a
        # purr phrase where a fur pattern should be.
        phrase = care.PURR_PHRASES[0]
        p = self.a_profile()
        with mock.patch.object(care, "PURR_PHRASES", [phrase]):
            self.run_task("pets", p, phrase * care.PURR_REPEATS)
        self.assertTrue(self.stamped(p, "pets"))


class TestStoppingEarlyStaysFree(Harness, unittest.TestCase):
    """
    The invariant the fix must not break. Stopping early costs nothing --
    it just doesn't tick the box.
    """

    def test_no_fish_are_taken_for_stopping(self):
        p = self.a_profile()
        p["fish"] = 120
        self.run_task("water", p, "a")
        self.assertGreaterEqual(p["fish"], 120)

    def test_the_cat_is_not_made_wary_by_stopping(self):
        p = self.a_profile()
        self.run_task("food", p, "a")
        self.assertFalse(p["cat"].get("wary"))

    def test_an_already_stamped_task_is_not_un_stamped(self):
        """Quitting a task done earlier today must not undo it."""
        p = self.a_profile()
        cat.stamp_care(p, "water")
        before = p["cat"]["care"]["water"]
        self.run_task("water", p, "")
        self.assertEqual(p["cat"]["care"]["water"], before)


class TestTheContract(unittest.TestCase):
    """
    Pin the shape, so `if done:` can't quietly come back.

    `_run_units` returns a COUNT. Every caller has to compare it against
    the number of units rather than test it for truthiness.
    """

    def source(self, mod):
        with open(mod.__file__, encoding="utf-8") as fh:
            return fh.read()

    def test_care_stamps_only_on_a_full_count(self):
        src = self.source(care)
        self.assertNotIn("    if done:\n", src)
        self.assertEqual(src.count("if done >= len(units):"), 3)

    def test_feed_stamps_only_on_a_full_bowl(self):
        src = self.source(feed)
        self.assertNotIn("    if caught:\n        cat.stamp_care", src)
        self.assertIn("if caught >= WORDS:\n        cat.stamp_care", src)

    def test_every_stamp_site_is_guarded(self):
        """No care stamp anywhere may sit under a bare truthiness test."""
        for mod in (care, feed):
            lines = self.source(mod).splitlines()
            for i, line in enumerate(lines):
                if "cat.stamp_care" not in line:
                    continue
                guard = lines[i - 1].strip()
                if not guard.startswith("if "):
                    continue
                self.assertTrue(
                    ">=" in guard or "summary" in guard,
                    "%s:%d stamps under a bare truthiness test: %r"
                    % (os.path.basename(mod.__file__), i + 1, guard))


if __name__ == "__main__":
    unittest.main()
