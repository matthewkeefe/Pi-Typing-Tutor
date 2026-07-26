#!/usr/bin/env python3
"""
Simulated playtest: drive the real engine with synthetic kids.

    python3 tools/simulate.py                 # every persona, matrix at the end
    python3 tools/simulate.py --days 200
    python3 tools/simulate.py --persona hunt_10
    python3 tools/simulate.py --detail        # per-persona milestone tables

WHAT THIS IS FOR
    Pacing and reachability. Does a kid at this ability ever unlock a
    seventh letter? How many months to a grown-up cat? Can they afford the
    shop? These are questions a real playtest can't answer either, because
    nobody runs a 75-day session with a child.

WHAT IT CANNOT TELL YOU
    Anything about reaction. Whether a kid finds the heatmap, whether the
    wary cat reads as rejection rather than "cats being cats", whether
    siblings compare their cats as better or worse. Those are why the
    playtest gate exists and this does not replace it.

HOW MUCH TO TRUST IT
    The engine, growth rules and economy are the real ones, imported
    directly -- if this says a letter never unlocks, that is the shipping
    code's behaviour, not a model's. The PERSONAS are estimates and should
    be argued with. Findings that hold across every persona are strong;
    findings that depend on one persona's numbers are hypotheses.
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adaptive, cat, profiles, shop  # noqa: E402

# --- keyboard geometry ----------------------------------------------
#
# What makes a key hard for a touch typist is how far the finger travels
# and whether it's a stretch. Hunt-and-peck typists barely feel this --
# they're looking at the keyboard either way -- which is exactly the
# difference the personas need to express.

HOME = "asdfjkl;"        # fingers rest here
STRETCH = "gh"           # index stretches without leaving the row
TOP = "qwertyuiop"
BOTTOM = "zxcvbnm"
FAR = "tybn"             # index-finger reaches across, the worst of both

REACH = {}
for _ch in HOME:
    REACH[_ch] = 0.0
for _ch in STRETCH:
    REACH[_ch] = 0.35
for _ch in TOP:
    REACH[_ch] = 0.55
for _ch in BOTTOM:
    REACH[_ch] = 0.75
for _ch in FAR:
    REACH[_ch] = 0.90


def reach_cost(ch):
    """0.0 (resting under a finger) to 1.0 (worst reach)."""
    return REACH.get(ch.lower(), 0.6)


def wpm_to_ms(wpm):
    """The standard 5-characters-per-word convention, same as engine.py."""
    return 12000.0 / max(1.0, wpm)


def ms_to_wpm(ms):
    return 12000.0 / max(1.0, ms)


class Persona:
    """
    One synthetic kid.

    wpm_start / wpm_ceiling
        Comfortable speed on an easy key, at the start and at the limit
        they plateau to. Equal values model a kid who has settled at that
        ability -- which is what you want when asking "can a 10 wpm kid
        ever get anywhere".
    technique
        "touch"  -- home row is genuinely easier; reaches cost real time.
        "hunt"   -- looking at the keyboard for every key, so position
                    barely matters and nothing is ever fast.
    reach_penalty
        How much a full reach costs, as a fraction of speed. A beginner
        with good form but no range has a high value here: fluent at rest,
        lost above and below.
    err_start / err_floor
        Error rate on an unfamiliar key, and once it's well practised.
    familiar
        Keystrokes on one key before it counts as learned.
    words_per_day
        Volume. A care-board Feed drill is ~18 words; most kids will do a
        few drills and a game.
    """

    def __init__(self, key, label, wpm_start, wpm_ceiling, technique,
                 reach_penalty, err_start, err_floor, familiar,
                 words_per_day, note=""):
        self.key = key
        self.label = label
        self.wpm_start = wpm_start
        self.wpm_ceiling = wpm_ceiling
        self.technique = technique
        self.reach_penalty = reach_penalty
        self.err_start = err_start
        self.err_floor = err_floor
        self.familiar = familiar
        self.words_per_day = words_per_day
        self.note = note

    # -- per-key ability ---------------------------------------------

    def _reach_factor(self, ch):
        """Multiplier on comfortable speed for this key, 0..1."""
        cost = reach_cost(ch)
        if self.technique == "hunt":
            # Hunting for every key: position is nearly irrelevant, and
            # the small advantage that exists is familiarity, not form.
            cost *= 0.2
        return max(0.15, 1.0 - cost * self.reach_penalty)

    def comfortable_wpm(self, practice):
        """Speed on an easy key, improving with total practice."""
        span = self.wpm_ceiling - self.wpm_start
        return self.wpm_start + span * (1.0 - 0.5 ** (practice / 60000.0))

    def key_ms(self, ch, practice, exposure):
        base = self.comfortable_wpm(practice) * self._reach_factor(ch)
        ms = wpm_to_ms(base)
        # Unfamiliar keys are slower still, easing off as they're learned.
        green_ish = 0.5 ** (exposure / max(1.0, self.familiar))
        return ms * (1.0 + 0.55 * green_ish)

    def key_err(self, ch, exposure):
        span = self.err_start - self.err_floor
        settled = self.err_floor + span * (0.5 ** (exposure / max(1.0, self.familiar)))
        # Reaches are missed more often, for the same reason they're slow.
        return min(0.9, settled * (1.0 + reach_cost(ch) * self.reach_penalty))


PERSONAS = [
    Persona("hunt_10", "Hunt-and-peck, 10 wpm",
            wpm_start=9, wpm_ceiling=12, technique="hunt",
            reach_penalty=0.25, err_start=0.30, err_floor=0.09,
            familiar=320, words_per_day=70,
            note="two fingers, eyes down; position never becomes muscle memory"),
    Persona("homerow_only", "True beginner, correct form, home row only",
            wpm_start=14, wpm_ceiling=20, technique="touch",
            reach_penalty=0.85, err_start=0.30, err_floor=0.05,
            familiar=300, words_per_day=80,
            note="fluent on asdfghjkl;, lost the moment a word leaves it"),
    Persona("moderate_20", "Moderate form, 20 wpm",
            wpm_start=17, wpm_ceiling=23, technique="touch",
            reach_penalty=0.40, err_start=0.24, err_floor=0.05,
            familiar=280, words_per_day=90,
            note="proper fingers most of the time, reaches still cost them"),
    Persona("improving_30", "Improving, 30 wpm",
            wpm_start=24, wpm_ceiling=33, technique="touch",
            reach_penalty=0.28, err_start=0.18, err_floor=0.035,
            familiar=240, words_per_day=110,
            note="form is holding up; reaches are getting cheap"),
    Persona("fluent_40", "Fluent, 40 wpm",
            wpm_start=34, wpm_ceiling=44, technique="touch",
            reach_penalty=0.18, err_start=0.12, err_floor=0.02,
            familiar=200, words_per_day=130,
            note="the ceiling this game's tuning was written against"),
]

BY_KEY = {p.key: p for p in PERSONAS}


# --- the simulation --------------------------------------------------


def simulate(persona, days=365, seed=7):
    """
    Play `days` days as this persona and return (profile, timeline).

    Everything that decides anything -- unlocks, mastery, growth, fish --
    is the real shipping code. This only decides how fast and how
    accurately a key gets hit.
    """
    rng = random.Random(seed)
    p = profiles._blank_profile(persona.label)
    p["cat"] = {"seed": 4242, "name": "Mittens", "growth": 0}
    adaptive.ensure(p)

    exposure = {}
    practice = 0
    timeline = {"unlocks": {}, "green": {}, "stages": {}, "letters": []}

    for day in range(1, days + 1):
        p["days_played"] = day
        session = {}
        typed = 0

        # generate_lesson only ever draws from unlocked letters, so a kid
        # who stalls keeps drilling the same six for as long as it takes.
        for _ in range(max(1, persona.words_per_day // 18)):
            for word in adaptive.generate_lesson(p, 18, rng):
                for ch in word:
                    seen = exposure.get(ch, 0)
                    entry = session.setdefault(
                        ch, {"n": 0, "err": 0, "ms_sum": 0.0, "ms_n": 0})
                    entry["n"] += 1
                    if rng.random() < persona.key_err(ch, seen):
                        entry["err"] += 1
                    else:
                        entry["ms_sum"] += persona.key_ms(ch, practice, seen)
                        entry["ms_n"] += 1
                    exposure[ch] = seen + 1
                    practice += 1
                    typed += 1

        before = set(adaptive.alphabet(p))
        green_before = _green(p, before)
        adaptive.merge_keys(p, session)
        after = set(adaptive.alphabet(p))

        for ch in sorted(after - before):
            timeline["unlocks"][ch] = day
        for ch in sorted(_green(p, after) - green_before):
            timeline["green"].setdefault(ch, day)

        p["fish"] = p.get("fish", 0) + typed // 5
        timeline["letters"].append(len(after))

        stage = cat.earned_growth(p)
        if stage > cat.growth(p):
            cat.advance_growth(p)
            timeline["stages"].setdefault(stage, day)

    return p, timeline


def _green(profile, letters):
    keys = profile.get("keys") or {}
    return {c for c in letters if adaptive.is_green(keys.get(c) or {})}


def day_reached(timeline, n_letters):
    """The day the alphabet first hit `n_letters`, or None."""
    for day, count in enumerate(timeline["letters"], start=1):
        if count >= n_letters:
            return day
    return None


# --- reporting -------------------------------------------------------


def detail(persona, profile, timeline, days):
    letters = adaptive.alphabet(profile)
    green = sorted(_green(profile, set(letters)))

    print("=" * 72)
    print("%s  (%s)" % (persona.label, persona.key))
    print("  %s" % persona.note)
    print("=" * 72)
    print("  after %d days: %d/26 unlocked, %d/26 mastered, %d fish"
          % (days, len(letters), len(green), profile.get("fish", 0)))

    home = [c for c in letters if reach_cost(c) <= 0.35]
    print("  unlocked letters: %s   (%d of them within easy reach)"
          % ("".join(letters), len(home)))

    print()
    print("  GATE                              DAY")
    for n, label in ((7, "7th letter (any progress at all)"),
                     (12, "12 letters -- Alphabet Soup opens"),
                     (20, "20 letters"),
                     (26, "26 letters -- full alphabet")):
        d = day_reached(timeline, n)
        print("    %-32s %s" % (label, d if d else "NEVER"))

    print()
    print("  GROWTH STAGE                      DAY")
    for stage in range(1, len(cat.GROWTH_STAGES)):
        d = timeline["stages"].get(stage)
        need = "%dd + %dL" % (cat.GROWTH_DAYS[stage], cat.GROWTH_LETTERS[stage])
        print("    %-14s (%-9s)      %s"
              % (cat.GROWTH_STAGES[stage], need, d if d else "NEVER"))

    secret = cat.secret_expressed(profile)
    print()
    print("  the secret: %s" % ("reached" if secret else "not reached"))
    print()


def matrix(rows, days):
    print()
    print("=" * 72)
    print("MATRIX -- %d simulated days" % days)
    print("=" * 72)
    print("  %-38s %5s %5s %6s %6s" %
          ("persona", "7th", "12th", "adult", "26th"))
    print("  %s" % ("-" * 64))
    for persona, profile, timeline in rows:
        def fmt(n):
            d = day_reached(timeline, n)
            return str(d) if d else "never"
        adult = timeline["stages"].get(2)
        print("  %-38s %5s %5s %6s %6s"
              % (persona.label[:38], fmt(7), fmt(12),
                 adult if adult else "never", fmt(26)))
    print()

    print("  affordability (a care day is roughly 50 fish)")
    cheapest = min(i["price"] for i in shop.CATALOG)
    dearest = max(i["price"] for i in shop.CATALOG)
    for persona, profile, _ in rows:
        fish = profile.get("fish", 0)
        print("    %-38s %7d fish  (%d..%d each)"
              % (persona.label[:38], fish, cheapest, dearest))
    print()


def green_ceiling_ms():
    """
    The slowest a key can be and still reach mastery, at 100% accuracy.

    Pure arithmetic from the tuning constants -- no persona involved, so
    this number is a property of the shipping engine rather than of any
    guess made in this file.
    """
    need = (adaptive.GREEN - adaptive.ACC_WEIGHT) / adaptive.SPEED_WEIGHT
    return adaptive.TARGET_MS - need * (adaptive.TARGET_MS - adaptive.FLOOR_MS)


def zone(ch):
    if ch in HOME:
        return "home"
    if ch in STRETCH:
        return "stretch"
    if ch in FAR:
        return "far"
    if ch in TOP:
        return "top"
    if ch in BOTTOM:
        return "bottom"
    return "?"


def keys_table(letters=None):
    """
    Per-key steady-state speed against the mastery threshold.

    This is the diagnostic that explains a matrix full of "never": a
    single un-green letter blocks every future unlock, so the slowest
    letter in the starting alphabet is the whole progression's gate.
    """
    letters = letters or adaptive.START_ALPHABET
    ceiling = green_ceiling_ms()

    print()
    print("=" * 72)
    print("PER-KEY CEILING -- letters %r" % letters)
    print("mastery needs <= %.0f ms/key (~%.0f wpm) even at 100%% accuracy"
          % (ceiling, ms_to_wpm(ceiling)))
    print("=" * 72)
    print("  %-38s %s" % ("persona", "  ".join(letters)))
    for persona in PERSONAS:
        cells = []
        for ch in letters:
            ms = wpm_to_ms(persona.wpm_ceiling * persona._reach_factor(ch))
            cells.append("%4.0f%s" % (ms, "*" if ms <= ceiling else " "))
        print("  %-38s %s" % (persona.label[:38], " ".join(cells)))

    print()
    print("  %-38s %s" % ("keyboard zone",
                          "  ".join("%-4s" % zone(c)[:4] for c in letters)))
    print()
    print("  * = can reach mastery. No star anywhere in a row means that")
    print("    kid never unlocks a seventh letter, however long they play.")
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--persona", action="append",
                    help="persona key; repeatable. default: all")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--detail", action="store_true",
                    help="per-persona milestone tables")
    ap.add_argument("--keys", action="store_true",
                    help="per-key ceiling against the mastery threshold")
    ap.add_argument("--letters", default=None,
                    help="letters for --keys (default: the starting alphabet)")
    args = ap.parse_args(argv)

    if args.keys:
        keys_table(args.letters)
        return 0

    chosen = PERSONAS
    if args.persona:
        missing = [k for k in args.persona if k not in BY_KEY]
        if missing:
            ap.error("unknown persona(s): %s\navailable: %s"
                     % (", ".join(missing), ", ".join(BY_KEY)))
        chosen = [BY_KEY[k] for k in args.persona]

    rows = []
    for persona in chosen:
        profile, timeline = simulate(persona, args.days, args.seed)
        rows.append((persona, profile, timeline))
        if args.detail:
            detail(persona, profile, timeline, args.days)

    matrix(rows, args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
