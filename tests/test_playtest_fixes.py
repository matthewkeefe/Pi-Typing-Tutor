"""
Two things a child found by playing, that the suite could not see.

1. PANTRY DEFENSE mice slid a fraction of a column every frame. Smooth,
   and at the speeds this ramps to, unreadable -- the word is a moving
   target the whole time and the kid is trying to READ it. They now hop
   `HOP` columns at a time, covering the same ground at the same average
   speed, with the word stationary in between.

2. PLATFORM JUMPER kept the finished word on screen for the whole
   half-second jump animation, because the animation drew with the old
   index and only advanced afterwards. A kid typing fast sees no change,
   types the word again, and those keys land against the word that had
   silently moved on. A slip they did not make, in the one mode whose
   entire premise is "type it perfectly".

Both are timing and rendering faults, which is the class this project
keeps shipping: 745 tests green, and a six-year-old finds them in one
sitting. The tests here drive the real loops rather than the pure
functions around them.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, profiles  # noqa: E402
from modes import pantry, platformer  # noqa: E402

ESC = 27


class TestMiceHop(unittest.TestCase):
    """Discrete jumps, same average speed."""

    def test_a_mouse_holds_still_between_hops(self):
        m = pantry.Mouse("cat", 40, 3, next_hop=1.0)
        speed = pantry.speed_for(0)
        moved = []
        now = 0.0
        while now < 3.0:
            if now >= m.next_hop:
                m.x -= pantry.HOP
                m.next_hop = now + pantry.HOP / speed
                moved.append(round(now, 2))
            now += 1 / 30.0
        gaps = [b - a for a, b in zip(moved, moved[1:])]
        self.assertTrue(gaps, "the mouse never moved")
        for g in gaps:
            self.assertGreater(g, 0.5, "hops too close together to read")

    def test_it_covers_the_same_ground_as_the_old_slide(self):
        """Readability must not have quietly changed the difficulty."""
        for score in (0, 100, 250, 400):
            speed = pantry.speed_for(score)
            m = pantry.Mouse("cat", 200, 1, next_hop=0.0)
            now, dt, elapsed = 0.0, 1 / 30.0, 10.0
            while now < elapsed:
                if now >= m.next_hop:
                    m.x -= pantry.HOP
                    m.next_hop = now + pantry.HOP / speed
                now += dt
            travelled = 200 - m.x
            expected = speed * elapsed
            self.assertAlmostEqual(travelled / expected, 1.0, delta=0.12,
                                   msg="score %d drifted from the old pace" % score)

    def test_hop_is_a_few_columns_not_a_teleport(self):
        self.assertGreaterEqual(pantry.HOP, 2)
        self.assertLessEqual(pantry.HOP, 4)

    def test_even_at_top_speed_there_is_a_beat_to_read_in(self):
        fastest = pantry.speed_for(100000)
        self.assertGreaterEqual(pantry.HOP / fastest, 0.25)

    def test_movement_is_no_longer_per_frame(self):
        with open(pantry.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("m.x -= speed * dt", src)
        self.assertIn("m.x -= HOP", src)


class Keys:
    def __init__(self, script):
        self.q = list(script)
        self.spins = 0

    def get(self, blocking=True):
        if self.q:
            return self.q.pop(0)
        if not blocking:
            return -1
        self.spins += 1
        if self.spins > 4000:
            raise AssertionError("mode never exited")
        return ESC

    def push(self, key):
        self.q.insert(0, key)


class Win:
    def __init__(self, keys, h=24, w=80):
        self.keys, self.h, self.w = keys, h, w
        self._blocking = True

    def getmaxyx(self):
        return (self.h, self.w)

    def nodelay(self, on):
        self._blocking = not on

    def getch(self):
        return self.keys.get(self._blocking)

    def addstr(self, *a, **k):
        pass

    def erase(self):
        pass

    def refresh(self):
        pass

    def keypad(self, *a):
        pass


class TestPlatformerWordTiming(unittest.TestCase):
    """
    The reported bug: the finished word stays up through the jump.
    """

    def setUp(self):
        self.seen = []          # `current` index at each world draw
        self.words = ["cat", "dog", "sun", "hat", "pen", "bug", "map", "fox"]
        zero = mock.Mock(return_value=0)
        self.patches = [
            mock.patch.object(platformer.lessons, "random_word",
                              side_effect=lambda lvl: self.words[
                                  len(self.seen) % len(self.words)]),
            mock.patch.object(platformer, "_draw_world", self._spy),
            mock.patch.object(platformer, "cp", zero),
            mock.patch("curses.curs_set", mock.Mock()),
            mock.patch("curses.napms", mock.Mock()),
            mock.patch.multiple("core.ui", cp=zero, message=mock.Mock(),
                                celebrate=mock.Mock()),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self.patches:
            p.stop()

    def _spy(self, stdscr, words, current, *a, **k):
        self.seen.append(current)

    def a_profile(self):
        p = profiles._blank_profile("Kid")
        p["cat"] = cat.blank_cat_data(4242, "Mochi", "2026-07-01")
        return p

    def _run(self, script):
        keys = Keys(script)
        win = Win(keys)
        with mock.patch("curses.ungetch", keys.push):
            platformer.play(win, self.a_profile())
        return keys

    def _draws_of_word_zero(self):
        """Run one word, and count how many frames still showed it."""
        with mock.patch.object(platformer.lessons, "random_word",
                               lambda lvl: "cat"):
            keys = Keys([ord(c) for c in "cat"])
            win = Win(keys)
            self.seen = []
            with mock.patch("curses.ungetch", keys.push):
                platformer.play(win, self.a_profile())
        return self.seen.count(0)

    def test_the_finished_word_is_not_held_on_screen(self):
        """
        Counting frames, because that is what the bug was made of.

        Typing "cat" draws word 0 about four times -- once on entry and
        once per keystroke. The jump animation is eighteen more frames,
        and it used to draw them all with the finished word still up. So
        a handful of frames is right and twenty is the bug.

        An earlier version of this test asserted "index 0 never appears
        after index 1", which passed with the bug in place: the stale
        frames come BEFORE the advance, not after it. It proved nothing.
        """
        self.assertLessEqual(
            self._draws_of_word_zero(), 8,
            "the finished word stayed on screen for an animation's worth "
            "of frames -- this is the reported bug")

    def test_the_word_does_advance(self):
        """Guard for the test above: it must not pass by never advancing."""
        with mock.patch.object(platformer.lessons, "random_word",
                               lambda lvl: "cat"):
            keys = Keys([ord(c) for c in "cat"])
            win = Win(keys)
            self.seen = []
            with mock.patch("curses.ungetch", keys.push):
                platformer.play(win, self.a_profile())
        self.assertIn(0, self.seen)
        self.assertIn(1, self.seen, "never moved to the second word")

    def test_typing_straight_through_two_words_records_no_errors(self):
        """
        A regression guard rather than a reproduction.

        The false errors the kid hit are a HUMAN consequence -- the stale
        word makes them type the wrong thing -- so no test can feel them.
        What a test can do is hold the floor: keys fed straight through
        two words, no pause, must never be scored as mistakes.
        """
        with mock.patch.object(platformer.lessons, "random_word",
                               lambda lvl: "cat"):
            keys = Keys([ord(c) for c in "catcat"])
            win = Win(keys)
            captured = {}
            real = platformer.engine.Session

            class Spy(real):
                def __init__(s, *a, **k):
                    super().__init__(*a, **k)
                    captured["sess"] = s

            with mock.patch.object(platformer.engine, "Session", Spy), \
                 mock.patch("curses.ungetch", keys.push):
                platformer.play(win, self.a_profile())
            self.assertEqual(captured["sess"].wrong_chars, 0,
                             "typing correctly produced errors")

    def test_a_key_that_interrupts_the_jump_is_not_swallowed(self):
        """
        Cutting the animation short must push the keystroke back, or the
        first letter of every word would vanish for a fast typist.
        """
        import inspect
        src = inspect.getsource(platformer._impatient)
        self.assertIn("ungetch", src)
        self.assertIn("nodelay", src)

    def test_the_animation_draws_the_index_it_was_given(self):
        with open(platformer.__file__, encoding="utf-8") as fh:
            src = fh.read()
        # The advance must happen before the animation call, not after.
        body = src[src.index("if typed == target:"):]
        advance = body.index("current = nxt")
        animate = body.index("_animate_jump(")
        self.assertLess(advance, animate,
                        "still animating before advancing the word")


if __name__ == "__main__":
    unittest.main()
