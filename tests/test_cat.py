"""
Tests for the cat's genetics and rendering. No curses -- `Cat.draw` is
the only part that touches a window, and it's exercised by the pty
screenshot harness rather than here.
"""

import os
import random
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat  # noqa: E402

SEEDS = [1, 2, 3, 7, 42, 100, 483921, 999999]


class TestGenetics(unittest.TestCase):
    def test_same_seed_same_cat(self):
        for seed in SEEDS:
            a, b = cat.Cat(seed), cat.Cat(seed)
            for gene in ("fur", "eyes", "ears", "build", "tail",
                         "personality", "colors"):
                self.assertEqual(getattr(a, gene), getattr(b, gene))

    def test_genes_survive_a_fresh_interpreter(self):
        """
        The trap this guards: Python randomises str hashing per process,
        so a hash()-based derivation would give a kid a different cat on
        every launch. Has to be checked in a separate process to catch it.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        code = ("import sys; sys.path.insert(0, %r)\n"
                "from core import cat\n"
                "print([cat.Cat(s).glyph() + cat.Cat(s).fur + "
                "'/'.join(cat.Cat(s).colors) for s in %r])" % (root, SEEDS))
        runs = [subprocess.run([sys.executable, "-c", code], capture_output=True,
                               text=True, env=dict(os.environ, PYTHONHASHSEED=str(s)))
                for s in (0, 1, 12345)]
        for r in runs:
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(runs[0].stdout, runs[1].stdout)
        self.assertEqual(runs[0].stdout, runs[2].stdout)

    def test_genes_are_independent_streams(self):
        """
        Adding a gene later must not repaint existing cats. Proxy for that:
        each gene varies across seeds on its own, so none of them is a
        positional draw off one shared sequence.
        """
        for gene in ("fur", "eyes", "ears", "tail", "personality"):
            seen = {getattr(cat.Cat(s), gene) for s in range(200)}
            self.assertGreater(len(seen), 1, gene)

    def test_traits_are_lateral(self):
        """No gene is rarer than any other -- no accidental rarity tier."""
        for options, gene in ((cat.FUR_NAMES, "fur"), (cat.EYES, "eyes"),
                              (cat.EARS, "ears"), (cat.TAILS, "tail"),
                              (cat.PERSONALITIES, "personality")):
            counts = {o: 0 for o in options}
            for s in range(3000):
                counts[getattr(cat.Cat(s), gene)] += 1
            lo, hi = min(counts.values()), max(counts.values())
            self.assertGreater(lo, 0, "%s never appears: %s" % (gene, counts))
            self.assertLess(hi / lo, 1.35, "%s is lopsided: %s" % (gene, counts))

    def test_from_profile(self):
        self.assertIsNone(cat.Cat.from_profile({}))
        self.assertIsNone(cat.Cat.from_profile({"cat": {}}))
        c = cat.Cat.from_profile({"cat": {"seed": 7, "name": "Mochi", "growth": 3}})
        self.assertEqual(c.name, "Mochi")
        self.assertEqual(c.growth, 3)
        self.assertEqual(c.seed, 7)

    def test_blank_cat_data(self):
        d = cat.blank_cat_data(7, "Mochi", "2026-07-26")
        self.assertEqual(d["growth"], 0)
        self.assertEqual(d["tricks"], [])
        self.assertFalse(d["wary"])


class TestRendering(unittest.TestCase):
    def test_every_pose_renders_for_every_seed(self):
        for seed in SEEDS:
            c = cat.Cat(seed)
            for growth in (0, 3):
                for pose in cat.POSES:
                    rows = c.art(pose, growth)
                    self.assertTrue(rows, "%s/%s empty" % (seed, pose))
                    self.assertLessEqual(max(len(r) for r in rows), 12,
                                         "%s/%s too wide" % (seed, pose))

    def test_pure_ascii(self):
        for seed in SEEDS:
            c = cat.Cat(seed)
            for growth in (0, 3):
                for pose in cat.POSES:
                    for row in c.art(pose, growth):
                        self.assertTrue(row.isascii(), repr(row))
                        self.assertTrue(all(32 <= ord(ch) < 127 for ch in row))

    def test_no_unexpanded_slots(self):
        for seed in SEEDS:
            c = cat.Cat(seed)
            for growth in (0, 3):
                for pose in cat.POSES:
                    for row in c.art(pose, growth):
                        self.assertNotIn("{", row)
                        self.assertNotIn("}", row)

    def test_accent_columns_are_in_range(self):
        for seed in SEEDS:
            c = cat.Cat(seed)
            for pose in cat.POSES:
                for text, accents in c._render(pose, 3):
                    for j in accents:
                        self.assertLess(j, len(text))

    def test_solid_fur_has_no_body_markings(self):
        solid = next(c for c in (cat.Cat(s) for s in range(500))
                     if c.fur == "solid")
        body = solid.art("loaf", 3)[3]
        self.assertEqual(body.strip("()"), " " * 5)

    def test_kittens_are_smaller_than_adults(self):
        c = cat.Cat(42)
        self.assertLess(c.width("sit", 0), c.width("sit", 3))
        self.assertTrue(c.is_kitten(0))
        self.assertTrue(c.is_kitten(1))
        self.assertFalse(c.is_kitten(2))

    def test_unknown_pose_falls_back_rather_than_crashing(self):
        self.assertEqual(cat.Cat(1).art("nonsense"), cat.Cat(1).art("sit"))

    def test_glyphs_differ_across_cats(self):
        glyphs = {cat.Cat(s).glyph() for s in range(300)}
        self.assertGreaterEqual(len(glyphs), 12)  # 4 eyes x 3 ear shapes
        for g in glyphs:
            self.assertEqual(len(g), 5)


class TestBehaviour(unittest.TestCase):
    def test_idle_poses_are_real_poses(self):
        rng = random.Random(4)
        for seed in SEEDS:
            c = cat.Cat(seed)
            for _ in range(200):
                self.assertIn(c.next_idle(rng), cat.POSES)

    def test_personality_actually_steers_idling(self):
        rng = random.Random(5)
        lazy = next(c for c in (cat.Cat(s) for s in range(500))
                    if c.personality == "lazy")
        hunter = next(c for c in (cat.Cat(s) for s in range(500))
                      if c.personality == "hunter")
        lazy_sleeps = sum(lazy.next_idle(rng) == "sleep" for _ in range(2000))
        hunter_sleeps = sum(hunter.next_idle(rng) == "sleep" for _ in range(2000))
        self.assertGreater(lazy_sleeps, hunter_sleeps * 3)

    def test_says_returns_something_short(self):
        rng = random.Random(6)
        c = cat.Cat(1)
        for pose in cat.POSES:
            line = c.says(pose, rng)
            self.assertTrue(line)
            self.assertLessEqual(len(line), 20)

    def test_describe_is_kid_readable(self):
        for seed in SEEDS:
            text = cat.Cat(seed, "Mochi").describe()
            self.assertTrue(text.startswith("Mochi is a "))
            self.assertNotIn("lazy", text)  # display words, not gene keys
            self.assertNotIn("chaotic", text)


if __name__ == "__main__":
    unittest.main()
