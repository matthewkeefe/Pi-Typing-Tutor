"""
Tests for the particle system.

Spawning and ticking are deliberately curses-free, so the physics can be
tested without a terminal. `draw` is exercised against a fake window that
fails loudly if anything is written outside the screen.
"""

import math
import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import fx  # noqa: E402


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


class TestTrig(unittest.TestCase):
    def test_approximations_are_close_enough(self):
        for i in range(0, 700):
            a = i * 0.01
            self.assertAlmostEqual(fx._sin(a), math.sin(a), delta=0.002)
            self.assertAlmostEqual(fx._cos(a), math.cos(a), delta=0.002)


class TestSpawn(unittest.TestCase):
    def field(self, seed=1):
        return fx.Field(rng=random.Random(seed))

    def test_every_preset_spawns(self):
        for kind in fx.PRESETS:
            f = self.field()
            f.spawn(kind, 10, 40)
            self.assertGreater(len(f), 0, kind)
            for p in f.particles:
                self.assertEqual((p.y, p.x), (10.0, 40.0))
                self.assertTrue(p.ttl > 0)
                self.assertEqual(len(p.ch), 1)
                self.assertTrue(p.ch.isascii())

    def test_unknown_kind_is_ignored_not_fatal(self):
        """A typo in a draw loop should cost a sparkle, not the session."""
        f = self.field()
        f.spawn("nonsense", 1, 1)
        self.assertEqual(len(f), 0)

    def test_hard_cap_drops_the_oldest(self):
        f = self.field()
        for _ in range(60):
            f.spawn("confetti", 5, 5)
        self.assertLessEqual(len(f), f.cap)
        self.assertEqual(len(f), f.cap)

    def test_purr_drifts_upward(self):
        f = self.field()
        for _ in range(20):
            f.spawn("purr", 10, 40)
        self.assertTrue(all(p.vy <= 0 for p in f.particles))

    def test_bursts_are_roughly_round_not_smeared(self):
        """Cells are twice as tall as wide, so vx is scaled to match."""
        f = self.field(7)
        for _ in range(15):
            f.spawn("burst", 10, 40)
        spread_y = max(abs(p.vy) for p in f.particles)
        spread_x = max(abs(p.vx) for p in f.particles)
        self.assertGreater(spread_x / spread_y, 1.4)
        self.assertLess(spread_x / spread_y, 2.6)


class TestTick(unittest.TestCase):
    def test_particles_expire(self):
        f = fx.Field(rng=random.Random(2))
        f.spawn("spark", 10, 40)
        for _ in range(100):
            f.tick(0.033)
        self.assertEqual(len(f), 0)

    def test_gravity_pulls_confetti_down(self):
        f = fx.Field(rng=random.Random(3))
        f.spawn("confetti", 10, 40, n=10)
        before = [p.vy for p in f.particles]
        f.tick(0.1)
        self.assertTrue(all(a > b for a, b in zip([p.vy for p in f.particles], before)))

    def test_empty_tick_is_free(self):
        f = fx.Field()
        start = time.perf_counter()
        for _ in range(50000):
            f.tick(0.033)
        self.assertLess(time.perf_counter() - start, 0.5)

    def test_full_field_tick_is_well_under_a_frame(self):
        f = fx.Field(rng=random.Random(4))
        while len(f) < f.cap:
            f.spawn("confetti", 10, 40)
        start = time.perf_counter()
        for _ in range(100):
            f.tick(0.001)   # small dt so nothing dies mid-measurement
        per_tick_ms = (time.perf_counter() - start) * 1000 / 100
        self.assertLess(per_tick_ms, 1.0, "%.3f ms per tick" % per_tick_ms)


class TestDraw(unittest.TestCase):
    def test_particles_flying_off_screen_never_write_out_of_bounds(self):
        f = fx.Field(rng=random.Random(5))
        win = FakeWin()
        for corner in ((0, 0), (0, 79), (23, 0), (23, 79), (12, 40)):
            for _ in range(10):
                f.spawn("burst", corner[0], corner[1])
        for _ in range(60):
            f.tick(0.05)
            f.draw(win)   # FakeWin raises if anything lands off-screen

    def test_empty_field_draws_nothing(self):
        win = FakeWin()
        fx.Field().draw(win)
        self.assertEqual(win.written, [])


class TestModuleDefault(unittest.TestCase):
    def test_clear_resets_the_shared_field(self):
        fx.clear()
        fx.spawn("spark", 1, 1)
        self.assertGreater(fx.count(), 0)
        fx.clear()
        self.assertEqual(fx.count(), 0)

    def test_hosts_can_tick_and_draw_an_empty_field_safely(self):
        """
        The additive guarantee: a mode that never spawns pays nothing and
        behaves exactly as it did before fx existed.
        """
        fx.clear()
        win = FakeWin()
        fx.tick(0.033)
        fx.draw(win)
        self.assertEqual(win.written, [])


if __name__ == "__main__":
    unittest.main()
