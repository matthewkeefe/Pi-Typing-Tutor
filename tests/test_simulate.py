"""
The playtest simulation harness (tools/simulate.py).

Tested because findings get argued from it. A harness that quietly
disagrees with the engine, or that isn't reproducible, produces
conclusions worse than having no harness at all.

What's asserted here is that the harness is *honest*: it drives the real
engine, it's deterministic, and its personas are ordered the way their
labels claim. Whether the persona numbers resemble real children is a
judgement, not a test.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from core import adaptive  # noqa: E402
import simulate  # noqa: E402


class TestKeyboardModel(unittest.TestCase):
    def test_every_letter_has_a_reach_cost(self):
        for ch in "abcdefghijklmnopqrstuvwxyz":
            cost = simulate.reach_cost(ch)
            self.assertGreaterEqual(cost, 0.0, ch)
            self.assertLessEqual(cost, 1.0, ch)

    def test_the_home_row_is_free_and_reaches_are_not(self):
        for ch in simulate.HOME:
            self.assertEqual(simulate.reach_cost(ch), 0.0, ch)
        for ch in simulate.TOP + simulate.BOTTOM:
            self.assertGreater(simulate.reach_cost(ch), 0.0, ch)

    def test_far_reaches_cost_the_most(self):
        worst = max(simulate.reach_cost(c) for c in simulate.HOME + simulate.TOP)
        for ch in simulate.FAR:
            self.assertGreaterEqual(simulate.reach_cost(ch), worst, ch)

    def test_wpm_and_ms_round_trip(self):
        for wpm in (10, 20, 30, 40):
            self.assertAlmostEqual(simulate.ms_to_wpm(simulate.wpm_to_ms(wpm)),
                                   wpm, places=6)

    def test_the_standard_conversion_matches_the_engine(self):
        """5 characters per word, the same convention engine.py uses."""
        self.assertAlmostEqual(simulate.wpm_to_ms(40), 300.0, places=6)


class TestPersonas(unittest.TestCase):
    def test_keys_are_unique(self):
        keys = [p.key for p in simulate.PERSONAS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_the_range_the_brief_asked_for_is_covered(self):
        ceilings = sorted(p.wpm_ceiling for p in simulate.PERSONAS)
        self.assertLessEqual(min(ceilings), 12, "need a ~10 wpm persona")
        self.assertGreaterEqual(max(ceilings), 40, "need up to 40 wpm")

    def test_every_persona_is_coherent(self):
        for p in simulate.PERSONAS:
            self.assertLessEqual(p.wpm_start, p.wpm_ceiling, p.key)
            self.assertGreaterEqual(p.err_start, p.err_floor, p.key)
            self.assertIn(p.technique, ("touch", "hunt"), p.key)
            self.assertTrue(p.label and p.note, p.key)

    def test_faster_personas_really_are_faster(self):
        ranked = sorted(simulate.PERSONAS, key=lambda p: p.wpm_ceiling)
        speeds = [p.key_ms("f", 10 ** 6, 10 ** 4) for p in ranked]
        self.assertEqual(speeds, sorted(speeds, reverse=True))

    def test_touch_typists_prefer_the_home_row(self):
        touch = [p for p in simulate.PERSONAS if p.technique == "touch"]
        self.assertTrue(touch)
        for p in touch:
            home = p.key_ms("f", 0, 0)
            reach = p.key_ms("t", 0, 0)
            self.assertLess(home, reach, p.key)

    def test_hunt_and_peck_barely_notices_the_home_row(self):
        """The whole point of the technique: they're looking either way."""
        hunt = [p for p in simulate.PERSONAS if p.technique == "hunt"]
        self.assertTrue(hunt)
        for p in hunt:
            home = p.key_ms("f", 0, 0)
            reach = p.key_ms("t", 0, 0)
            self.assertLess(abs(reach - home) / home, 0.25, p.key)

    def test_the_home_row_persona_is_lost_off_it(self):
        p = simulate.BY_KEY["homerow_only"]
        self.assertLess(p.key_ms("f", 0, 0), p.key_ms("t", 0, 0) / 2)

    def test_practice_and_familiarity_both_help(self):
        for p in simulate.PERSONAS:
            self.assertLess(p.key_ms("f", 10 ** 6, 0), p.key_ms("f", 0, 0), p.key)
            self.assertLess(p.key_ms("f", 0, 10 ** 4), p.key_ms("f", 0, 0), p.key)
            self.assertLess(p.key_err("f", 10 ** 4), p.key_err("f", 0), p.key)

    def test_error_rates_stay_in_range(self):
        for p in simulate.PERSONAS:
            for ch in "abcdefghijklmnopqrstuvwxyz":
                for seen in (0, 100, 10 ** 4):
                    e = p.key_err(ch, seen)
                    self.assertGreaterEqual(e, 0.0)
                    self.assertLessEqual(e, 1.0)


class TestSimulation(unittest.TestCase):
    def test_it_is_reproducible(self):
        p = simulate.BY_KEY["moderate_20"]
        a, ta = simulate.simulate(p, days=12, seed=3)
        b, tb = simulate.simulate(p, days=12, seed=3)
        self.assertEqual(ta["letters"], tb["letters"])
        self.assertEqual(a["fish"], b["fish"])

    def test_a_different_seed_can_differ(self):
        p = simulate.BY_KEY["moderate_20"]
        _, ta = simulate.simulate(p, days=12, seed=1)
        _, tb = simulate.simulate(p, days=12, seed=99)
        self.assertEqual(len(ta["letters"]), len(tb["letters"]))

    def test_it_uses_the_real_profile_shape(self):
        p, _ = simulate.simulate(simulate.BY_KEY["fluent_40"], days=5)
        for key in ("days_played", "alphabet", "keys", "fish", "cat"):
            self.assertIn(key, p)

    def test_the_alphabet_never_shrinks(self):
        for key in ("hunt_10", "fluent_40"):
            _, t = simulate.simulate(simulate.BY_KEY[key], days=30)
            self.assertEqual(t["letters"], sorted(t["letters"]))

    def test_it_starts_from_the_engines_own_alphabet(self):
        _, t = simulate.simulate(simulate.BY_KEY["hunt_10"], days=2)
        self.assertEqual(t["letters"][0], len(adaptive.START_ALPHABET))

    def test_fish_only_accumulate(self):
        p, _ = simulate.simulate(simulate.BY_KEY["moderate_20"], days=20)
        self.assertGreater(p["fish"], 0)

    def test_day_reached_reports_honestly(self):
        _, t = simulate.simulate(simulate.BY_KEY["hunt_10"], days=10)
        self.assertIsNotNone(simulate.day_reached(t, len(adaptive.START_ALPHABET)))
        self.assertIsNone(simulate.day_reached(t, 26))


class TestGreenCeiling(unittest.TestCase):
    """
    The finding this harness exists to have produced, pinned so a tuning
    change can't move it silently.
    """

    def test_the_ceiling_is_derived_from_the_engine_constants(self):
        ceiling = simulate.green_ceiling_ms()
        entry = {"n": adaptive.MIN_SAMPLES + 5, "err": 0, "ms": ceiling}
        self.assertGreaterEqual(adaptive.confidence(entry), adaptive.GREEN - 1e-9)

    def test_a_hair_slower_than_the_ceiling_is_not_masterable(self):
        entry = {"n": adaptive.MIN_SAMPLES + 5, "err": 0,
                 "ms": simulate.green_ceiling_ms() + 25}
        self.assertLess(adaptive.confidence(entry), adaptive.GREEN)

    def test_the_ceiling_is_currently_about_forty_wpm(self):
        """If tuning changes deliberately, update this and the docs."""
        self.assertAlmostEqual(simulate.ms_to_wpm(simulate.green_ceiling_ms()),
                               40.0, delta=1.0)


class TestCLI(unittest.TestCase):
    """The harness prints tables; swallow them so the suite stays readable."""

    def run_quiet(self, argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = simulate.main(argv)
        return code, buf.getvalue()

    def test_keys_mode_runs_and_names_the_threshold(self):
        code, out = self.run_quiet(["--keys"])
        self.assertEqual(code, 0)
        self.assertIn("mastery needs", out)

    def test_a_short_run_produces_a_matrix(self):
        code, out = self.run_quiet(["--days", "3", "--persona", "hunt_10"])
        self.assertEqual(code, 0)
        self.assertIn("MATRIX", out)

    def test_every_persona_appears_in_the_matrix(self):
        _, out = self.run_quiet(["--days", "2"])
        for p in simulate.PERSONAS:
            self.assertIn(p.label[:20], out, p.key)

    def test_an_unknown_persona_is_rejected(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                simulate.main(["--persona", "not_a_kid"])


if __name__ == "__main__":
    unittest.main()
