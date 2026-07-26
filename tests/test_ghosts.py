"""
Ghost recordings and racing -- issue #21.

Two acceptance criteria drive most of this: playback must be
deterministic, and the save must stay bounded. The third -- racing your
own ghost -- is the common case on a one-kid device, so it gets its own
coverage rather than being treated as an edge.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cat, fx, ghosts, profiles  # noqa: E402
from modes import race  # noqa: E402


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
        mock.patch.object(race, "cp", mock.Mock(return_value=0)),
    )


def a_profile(name="Test", seed=4242):
    p = profiles._blank_profile(name)
    p["cat"] = {"seed": seed, "name": "Mittens", "growth": 0}
    return p


FIRST_KEY = ghosts.passage_keys()[0][0]


class TestPassages(unittest.TestCase):
    def test_there_are_shared_passages(self):
        self.assertGreaterEqual(len(ghosts.PASSAGES), 4)

    def test_every_passage_is_plain_words(self):
        for _name, words in ghosts.PASSAGES:
            self.assertEqual(len(words), ghosts.PASSAGE_WORDS)
            for w in words:
                self.assertNotIn(" ", w, "per-word timing needs single words")
                self.assertTrue(w.isascii(), w)

    def test_keys_are_stable_across_processes(self):
        """
        crc32, not hash(): Python randomises string hashing per process, so
        a hash-based key would orphan every ghost on the next launch.
        """
        import subprocess
        code = ("import sys; sys.path.insert(0, %r);"
                "from core import ghosts;"
                "print(ghosts.key_for(['ask','dad']))"
                % os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        seen = set()
        for seed in ("0", "1", "2"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run([sys.executable, "-c", code], env=env,
                                 capture_output=True, text=True)
            seen.add(out.stdout.strip())
        self.assertEqual(len(seen), 1, seen)

    def test_keys_are_unique_per_passage(self):
        keys = [k for k, _, _ in ghosts.passage_keys()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_different_words_give_different_keys(self):
        self.assertNotEqual(ghosts.key_for(["a", "b"]),
                            ghosts.key_for(["b", "a"]))

    def test_find_passage_round_trips(self):
        for key, name, words in ghosts.passage_keys():
            self.assertEqual(ghosts.find_passage(key), (name, words))

    def test_an_unknown_key_finds_nothing(self):
        self.assertIsNone(ghosts.find_passage("deadbeef"))


class TestRecording(unittest.TestCase):
    def test_a_first_run_is_stored(self):
        p = a_profile()
        self.assertTrue(ghosts.record(p, FIRST_KEY, [1.0, 2.0, 3.0]))
        self.assertEqual(ghosts.get(p, FIRST_KEY), [1.0, 2.0, 3.0])

    def test_only_improvements_overwrite(self):
        p = a_profile()
        ghosts.record(p, FIRST_KEY, [1.0, 5.0])
        self.assertFalse(ghosts.record(p, FIRST_KEY, [1.0, 9.0]))
        self.assertEqual(ghosts.get(p, FIRST_KEY), [1.0, 5.0])
        self.assertTrue(ghosts.record(p, FIRST_KEY, [0.5, 3.0]))
        self.assertEqual(ghosts.get(p, FIRST_KEY), [0.5, 3.0])

    def test_an_empty_run_is_ignored(self):
        p = a_profile()
        self.assertFalse(ghosts.record(p, FIRST_KEY, []))
        self.assertIsNone(ghosts.get(p, FIRST_KEY))

    def test_missing_ghosts_read_as_none(self):
        self.assertIsNone(ghosts.get(a_profile(), "nope"))

    def test_the_save_stays_bounded(self):
        p = a_profile()
        for i in range(ghosts.MAX_GHOSTS * 3):
            ghosts.record(p, "key%03d" % i, [float(i + 1)])
        self.assertEqual(len(ghosts.all_ghosts(p)), ghosts.MAX_GHOSTS)

    def test_the_cap_drops_oldest_and_keeps_newest(self):
        p = a_profile()
        for i in range(ghosts.MAX_GHOSTS + 5):
            ghosts.record(p, "key%03d" % i, [float(i + 1)])
        keys = list(ghosts.all_ghosts(p))
        self.assertNotIn("key000", keys)
        self.assertIn("key%03d" % (ghosts.MAX_GHOSTS + 4), keys)

    def test_times_survive_a_json_round_trip_in_order(self):
        import json
        p = a_profile()
        for i in range(5):
            ghosts.record(p, "key%d" % i, [float(i + 1)])
        back = json.loads(json.dumps(p))
        self.assertEqual(list(back["ghosts"]), list(p["ghosts"]))

    def test_recorded_times_are_rounded_not_sprawling(self):
        p = a_profile()
        ghosts.record(p, FIRST_KEY, [1.23456789, 2.3456789])
        for t in ghosts.get(p, FIRST_KEY):
            self.assertEqual(t, round(t, 3))


class TestPlayback(unittest.TestCase):
    """'Ghost playback is deterministic.'"""

    def test_position_counts_splits_already_passed(self):
        times = [1.0, 2.5, 4.0]
        self.assertEqual(ghosts.position(times, 0.0), 0)
        self.assertEqual(ghosts.position(times, 0.99), 0)
        self.assertEqual(ghosts.position(times, 1.0), 1)
        self.assertEqual(ghosts.position(times, 3.0), 2)
        self.assertEqual(ghosts.position(times, 99.0), 3)

    def test_position_never_exceeds_the_run(self):
        times = [1.0, 2.0]
        for e in (0, 1, 5, 1000):
            self.assertLessEqual(ghosts.position(times, e), len(times))

    def test_position_is_monotonic(self):
        times = [0.5, 1.0, 3.0, 3.1, 8.0]
        seen = [ghosts.position(times, e / 10.0) for e in range(0, 900)]
        self.assertEqual(seen, sorted(seen))

    def test_replay_is_identical_every_time(self):
        times = [0.4, 1.9, 2.2, 6.0]
        samples = [e / 20.0 for e in range(0, 200)]
        first = [ghosts.position(times, e) for e in samples]
        for _ in range(5):
            self.assertEqual([ghosts.position(times, e) for e in samples],
                             first)

    def test_an_empty_ghost_never_moves(self):
        self.assertEqual(ghosts.position([], 100.0), 0)
        self.assertEqual(ghosts.position(None, 100.0), 0)


class TestOpponents(unittest.TestCase):
    def test_only_profiles_with_a_recording_are_offered(self):
        me, sib, cousin = a_profile("Me"), a_profile("Sib"), a_profile("Cuz")
        ghosts.record(me, FIRST_KEY, [1.0])
        ghosts.record(sib, FIRST_KEY, [2.0])
        everyone = {"Me": me, "Sib": sib, "Cuz": cousin}
        names = [n for n, _, _ in ghosts.opponents(everyone, "Me", FIRST_KEY)]
        self.assertEqual(names, ["Me", "Sib"])

    def test_racing_yourself_is_offered_and_flagged(self):
        me = a_profile("Me")
        ghosts.record(me, FIRST_KEY, [1.0])
        rows = ghosts.opponents({"Me": me}, "Me", FIRST_KEY)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0][2], "own ghost should be flagged as mine")

    def test_nobody_with_ghosts_yields_nothing(self):
        self.assertEqual(
            ghosts.opponents({"A": a_profile("A")}, "A", FIRST_KEY), [])

    def test_raceable_sorts_by_contested_first(self):
        a, b = a_profile("A"), a_profile("B")
        keys = [k for k, _, _ in ghosts.passage_keys()]
        ghosts.record(a, keys[2], [1.0])
        ghosts.record(b, keys[2], [1.5])
        ghosts.record(a, keys[1], [1.0])
        rows = ghosts.raceable({"A": a, "B": b})
        self.assertEqual(rows[0][0], keys[2])
        self.assertEqual(rows[0][3], 2)
        self.assertEqual(rows[1][0], keys[1])


class TestNoStakes(unittest.TestCase):
    """'No coupling to gauges/streaks/fish -- racing is pure free-play.'"""

    def test_the_mode_never_touches_progress_state(self):
        with open(race.__file__, encoding="utf-8") as fh:
            body = fh.read().split('"""', 2)[-1]
        for banned in ('profile["fish"]', "fish -=", "current_streak",
                       "stamp_care", "set_wary", "clear_wary", "gauge"):
            self.assertNotIn(banned, body, banned)

    def test_the_game_never_ranks_siblings(self):
        """Fairness invariant: the kid picks, the game never volunteers."""
        with open(race.__file__, encoding="utf-8") as fh:
            body = fh.read().split('"""', 2)[-1]
        for banned in ("leaderboard", "ranking", "fastest kid"):
            self.assertNotIn(banned, body.lower(), banned)


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

    def _draw(self, win, my_cat, their_cat, **over):
        words = list(ghosts.PASSAGES[0][1])
        kw = dict(words=words, index=3, typed="fa", their_name="Sib",
                  their_done=2, elapsed=4.2, msg="", countdown=None)
        kw.update(over)
        race._draw(win, kw["words"], kw["index"], kw["typed"], my_cat,
                   their_cat, kw["their_name"], kw["their_done"],
                   kw["elapsed"], kw["msg"], kw["countdown"])

    def test_draws_a_two_cat_race(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1, "A"), cat.Cat(2, "B"))
        self.assertTrue(win.written)

    def test_draws_without_cats(self):
        win = FakeWin()
        self._draw(win, None, None)

    def test_draws_a_solo_run_with_no_ghost(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1, "A"), None, their_name="", their_done=0)

    def test_draws_the_countdown(self):
        win = FakeWin()
        for n in (3, 2, 1):
            self._draw(win, cat.Cat(1), cat.Cat(2), countdown=n, index=0,
                       typed="")

    def test_every_position_on_the_track_stays_on_screen(self):
        win = FakeWin()
        words = list(ghosts.PASSAGES[0][1])
        for i in range(0, len(words) + 1):
            for j in range(0, len(words) + 1):
                self._draw(win, cat.Cat(1), cat.Cat(2), index=i,
                           their_done=j, typed="")

    def test_a_finished_ghost_does_not_run_off_the_edge(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), cat.Cat(2), index=99, their_done=99,
                   typed="")

    def test_adult_cats_fit_the_lanes(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1, growth=3), cat.Cat(2, growth=3))

    def test_narrow_screen_does_not_escape(self):
        win = FakeWin(h=20, w=60)
        self._draw(win, cat.Cat(1), cat.Cat(2))

    def test_a_long_opponent_name_is_clipped(self):
        win = FakeWin()
        self._draw(win, cat.Cat(1), cat.Cat(2), their_name="X" * 40)


class TestRegistration(unittest.TestCase):
    def test_it_is_in_the_arcade(self):
        import main
        labels = [lbl for _, _, lbl, _ in main.arcade_for(a_profile())]
        self.assertIn("Ghost Race", labels)

    def test_available_even_before_any_ghost_exists(self):
        """Somebody has to set the first pace."""
        self.assertTrue(race.available(a_profile()))

    def test_ghosts_key_migrates_on_old_saves(self):
        p = profiles.get_or_create({"Old": {"name": "Old"}}, "Old")
        self.assertEqual(ghosts.all_ghosts(p), {})


if __name__ == "__main__":
    unittest.main()
