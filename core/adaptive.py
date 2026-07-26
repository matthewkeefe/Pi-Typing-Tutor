"""
The adaptive drill engine -- a stdlib port of keybr's mechanism.

Three jobs:

1. Fold each session's per-key stats (from `engine.Session`) into the
   profile as a small recent-weighted summary, and score every key with
   a 0..1 `conf`idence.
2. Unlock the alphabet one letter at a time, in English frequency order,
   once every letter the kid already has is green.
3. Generate drill content: pronounceable pseudo-words built from English
   bigram frequencies, restricted to the unlocked alphabet, with the
   kid's weakest letter forced into every word.

Everything here is pure -- no curses, no I/O -- so it's testable on its
own (see tests/test_adaptive.py).

The BIGRAMS table and the ONSETS/CODAS cluster sets below were derived
offline from /usr/share/dict/words (lowercase a-z words of length 3-10);
rows are scaled to sum ~1000. "^" is word-start, "$" is word-end.
"""

import random

from core import lessons

# --- tuning ---------------------------------------------------------
# All of it lives here on purpose: these numbers want playtesting, not
# archaeology through the functions below.

FREQ_ORDER = "enitrlsauodychgmpbkvwfzxqj"
START_ALPHABET = "enitrl"

# The journey this game is tuned around: a kid arrives hunting and
# pecking at roughly 5 wpm and leaves touch-typing the whole keyboard at
# 40. Both ends are stated here because every number below is derived
# from them.
START_WPM = 5.0     # where a beginner actually starts
MASTER_WPM = 40.0   # the goal: 40 wpm on the full keyboard

# 5 wpm scores zero, 40 wpm scores full. The span is the whole journey,
# so a kid's heatmap keeps visibly moving the entire way up -- it used to
# span 20..80 wpm, which meant a beginner saw a flat wall of nothing.
TARGET_MS = 12000.0 / START_WPM     # 2400 ms
FLOOR_MS = 12000.0 / MASTER_WPM     # 300 ms

SPEED_WEIGHT = 0.6
ACC_WEIGHT = 0.4
ERR_CEILING = 0.5   # a 50%-wrong key scores zero on accuracy
EMA_ALPHA = 0.3     # weight of the newest session in the moving average

# --- two different questions, which used to share one answer ---------
#
# GREEN is mastery: "you type this key at the goal speed, accurately."
# It drives the heatmap, the trick celebrations and the secret, and it is
# meant to be hard -- all 26 green IS the win condition.
#
# READY is the unlock gate: "you've met this key enough to be offered a
# new one." It has to be reachable by a kid still hunting and pecking,
# because until it is, nothing downstream opens at all.
#
# Conflating the two is what made the game unplayable: every unlock
# demanded the win condition, so a simulated year produced zero new
# letters for every persona, including a fluent 40 wpm typist whose
# reaches landed at 325 ms against a 300 ms bar. See tools/simulate.py.

GREEN = 0.9         # conf at or above this, AND at goal speed = mastered

# Mastery is per key, but the goal is 40 wpm across real text -- and the
# keys under your fingers are always quicker than t, y, b and n. Holding
# every individual key to 40 wpm would mean the awkward ones needed 45+
# to compensate, so a kid genuinely typing 40 wpm would still be told
# they hadn't mastered the alphabet. The allowance is what makes "all 26
# green" mean the thing it's supposed to mean.
MASTER_WPM_PER_KEY = 36.0
MASTER_MS = 12000.0 / MASTER_WPM_PER_KEY   # 333 ms

MIN_SAMPLES = 20    # hits before a key can go green

READY_SAMPLES = 40  # hits before the unlock gate will judge a key at all
READY_ACC = 0.85    # get it right this often and you've earned a new letter

# How many letters one session can be worth.
#
# Ability decides this, nothing else. A kid holding the whole of their
# current alphabet at BURST_ACC gets a second letter, and one already
# typing it at the goal speed gets a third -- their competence is the
# only throttle, which is the point.
#
# The extras arrive before they've been practised, deliberately: a kid
# who demonstrably learns fast shouldn't be made to wait a session per
# letter. If the bigger alphabet turns out to be too much, their accuracy
# drops and the next unlock simply doesn't come. It self-corrects.
BURST_ACC = 0.95    # accuracy across the current alphabet for a 2nd letter
BURST_MAX = 3       # ceiling per session, so nobody is handed the deep end

MIN_WORD, MAX_WORD = 3, 7
REAL_WORD_SHARE = 0.3   # the rest of a lesson is generated pseudo-words
MAX_WORD_TRIES = 12     # walks to attempt before injecting the focus letter
FOCUS_BOOST = 25.0      # how hard the walk leans toward the focus letter
END_FLOOR = 10          # below this "$" weight, a letter never ends a word

VOWELS = "aeiouy"

# Consonant clusters English actually allows at the start / end of a word.
# Anything not on these lists only appears across a syllable boundary.
ONSETS = frozenset(
    "bl br ch cl cr dr fl fr gh gl gn gr kh kn kr ph pl pr ps pt rh sc "
    "sh sk sl sm sn sp sq st sw th tr tw wh wr".split()
)
CODAS = frozenset(
    "ch ck cs ct ds ff ft gh gs ht ks ld lk ll lt mb mp nd ng nk ns nt "
    "ph ps pt rd rk rl rm rn rp rs rt sh sk sm ss st th ts wl wn".split()
)

# Character bigram weights, rows scaled to sum ~1000 (see module docstring).
BIGRAMS = {
    "^": {"a": 73, "b": 58, "c": 82, "d": 47, "e": 36, "f": 35, "g": 34, "h": 35, "i": 27, "j": 10, "k": 13, "l": 31, "m": 54, "n": 23, "o": 32, "p": 86, "q": 5, "r": 45, "s": 110, "t": 58, "u": 56, "v": 16, "w": 22, "x": 2, "y": 4, "z": 5},
    "a": {"a": 1, "b": 38, "c": 54, "d": 35, "e": 19, "f": 9, "g": 31, "h": 6, "i": 26, "j": 2, "k": 15, "l": 116, "m": 42, "n": 148, "o": 2, "p": 31, "q": 1, "r": 114, "s": 53, "t": 103, "u": 19, "v": 14, "w": 9, "x": 6, "y": 12, "z": 6, "$": 85},
    "b": {"a": 155, "b": 30, "c": 4, "d": 6, "e": 161, "f": 2, "g": 1, "h": 4, "i": 118, "j": 3, "k": 1, "l": 163, "m": 3, "n": 2, "o": 119, "p": 2, "r": 91, "s": 15, "t": 6, "u": 78, "v": 2, "w": 2, "y": 13, "$": 19},
    "c": {"a": 136, "c": 13, "e": 92, "h": 134, "i": 69, "k": 62, "l": 38, "m": 1, "n": 2, "o": 145, "q": 1, "r": 56, "s": 4, "t": 50, "u": 51, "y": 30, "z": 1, "$": 115},
    "d": {"a": 89, "b": 4, "c": 2, "d": 21, "e": 186, "f": 4, "g": 11, "h": 5, "i": 148, "j": 2, "l": 33, "m": 5, "n": 6, "o": 76, "p": 2, "r": 43, "s": 11, "t": 1, "u": 32, "v": 2, "w": 6, "y": 21, "$": 290},
    "e": {"a": 47, "b": 10, "c": 29, "d": 69, "e": 26, "f": 10, "g": 11, "h": 4, "i": 12, "j": 1, "k": 3, "l": 58, "m": 29, "n": 88, "o": 12, "p": 21, "q": 2, "r": 173, "s": 70, "t": 50, "u": 9, "v": 9, "w": 9, "x": 12, "y": 6, "z": 2, "$": 229},
    "f": {"a": 96, "b": 1, "c": 1, "d": 1, "e": 110, "f": 75, "g": 1, "h": 1, "i": 145, "l": 109, "m": 1, "n": 1, "o": 150, "p": 1, "r": 67, "s": 2, "t": 42, "u": 114, "w": 2, "y": 33, "$": 48},
    "g": {"a": 112, "b": 4, "c": 1, "d": 2, "e": 169, "f": 2, "g": 30, "h": 41, "i": 87, "l": 82, "m": 10, "n": 26, "o": 73, "p": 1, "r": 80, "s": 8, "t": 3, "u": 58, "w": 4, "y": 37, "$": 168},
    "h": {"a": 157, "b": 3, "c": 1, "d": 2, "e": 194, "f": 3, "g": 1, "h": 1, "i": 148, "k": 1, "l": 21, "m": 9, "n": 8, "o": 148, "p": 2, "r": 35, "s": 3, "t": 24, "u": 40, "w": 7, "y": 67, "$": 124},
    "i": {"a": 76, "b": 13, "c": 109, "d": 61, "e": 27, "f": 20, "g": 25, "h": 1, "i": 2, "j": 1, "k": 15, "l": 60, "m": 28, "n": 185, "o": 43, "p": 25, "q": 2, "r": 29, "s": 116, "t": 87, "u": 11, "v": 21, "w": 1, "x": 4, "z": 19, "$": 18},
    "j": {"a": 284, "d": 2, "e": 171, "h": 2, "i": 79, "j": 1, "l": 1, "m": 1, "n": 1, "o": 207, "p": 1, "r": 3, "u": 237, "y": 3, "$": 7},
    "k": {"a": 88, "b": 9, "c": 2, "d": 3, "e": 293, "f": 7, "g": 1, "h": 19, "i": 146, "j": 1, "k": 5, "l": 47, "m": 10, "n": 26, "o": 39, "p": 4, "r": 14, "s": 24, "t": 7, "u": 22, "v": 1, "w": 13, "y": 30, "$": 190},
    "l": {"a": 131, "b": 5, "c": 6, "d": 15, "e": 191, "f": 5, "g": 5, "h": 2, "i": 155, "k": 6, "l": 82, "m": 8, "n": 2, "o": 92, "p": 8, "r": 1, "s": 7, "t": 18, "u": 39, "v": 7, "w": 2, "y": 92, "$": 121},
    "m": {"a": 204, "b": 44, "c": 1, "d": 1, "e": 161, "f": 2, "h": 1, "i": 151, "l": 5, "m": 27, "n": 11, "o": 110, "p": 54, "r": 1, "s": 5, "t": 1, "u": 39, "w": 1, "y": 32, "$": 148},
    "n": {"a": 76, "b": 8, "c": 45, "d": 65, "e": 126, "f": 14, "g": 98, "h": 7, "i": 97, "j": 3, "k": 14, "l": 10, "m": 6, "n": 20, "o": 62, "p": 7, "q": 2, "r": 8, "s": 34, "t": 101, "u": 17, "v": 6, "w": 7, "x": 1, "y": 13, "z": 2, "$": 152},
    "o": {"a": 18, "b": 19, "c": 39, "d": 39, "e": 11, "f": 9, "g": 33, "h": 4, "i": 31, "j": 1, "k": 11, "l": 78, "m": 64, "n": 144, "o": 45, "p": 50, "q": 1, "r": 127, "s": 56, "t": 57, "u": 69, "v": 23, "w": 26, "x": 10, "y": 6, "z": 4, "$": 26},
    "p": {"a": 124, "b": 3, "c": 2, "d": 1, "e": 144, "f": 2, "g": 1, "h": 105, "i": 111, "k": 1, "l": 70, "m": 3, "n": 3, "o": 118, "p": 33, "r": 109, "s": 25, "t": 35, "u": 43, "w": 3, "y": 21, "$": 42},
    "q": {"a": 1, "e": 1, "i": 2, "o": 1, "q": 1, "r": 1, "u": 991, "$": 3},
    "r": {"a": 129, "b": 13, "c": 19, "d": 28, "e": 153, "f": 6, "g": 14, "h": 8, "i": 138, "j": 1, "k": 12, "l": 14, "m": 27, "n": 20, "o": 111, "p": 10, "q": 1, "r": 22, "s": 20, "t": 34, "u": 32, "v": 6, "w": 5, "y": 39, "z": 1, "$": 138},
    "s": {"a": 52, "b": 2, "c": 44, "d": 1, "e": 97, "f": 1, "g": 1, "h": 76, "i": 80, "k": 12, "l": 18, "m": 41, "n": 8, "o": 49, "p": 40, "q": 6, "r": 1, "s": 84, "t": 150, "u": 42, "w": 10, "y": 14, "$": 169},
    "t": {"a": 101, "b": 3, "c": 10, "d": 1, "e": 199, "f": 4, "g": 1, "h": 72, "i": 149, "l": 19, "m": 4, "n": 3, "o": 93, "p": 2, "r": 77, "s": 8, "t": 30, "u": 36, "w": 8, "y": 35, "z": 2, "$": 140},
    "u": {"a": 32, "b": 37, "c": 36, "d": 26, "e": 27, "f": 8, "g": 20, "h": 1, "i": 30, "j": 1, "k": 6, "l": 106, "m": 76, "n": 208, "o": 6, "p": 32, "r": 112, "s": 141, "t": 70, "u": 1, "v": 4, "x": 4, "y": 1, "z": 3, "$": 10},
    "v": {"a": 167, "e": 492, "i": 226, "l": 1, "o": 83, "r": 2, "s": 1, "u": 16, "v": 1, "y": 7, "$": 3},
    "w": {"a": 224, "b": 10, "c": 2, "d": 11, "e": 148, "f": 6, "g": 2, "h": 66, "i": 162, "k": 8, "l": 27, "m": 6, "n": 43, "o": 153, "p": 4, "r": 30, "s": 15, "t": 6, "u": 5, "w": 4, "y": 9, "z": 1, "$": 58},
    "x": {"a": 105, "b": 7, "c": 41, "d": 2, "e": 92, "f": 6, "g": 1, "h": 15, "i": 202, "k": 1, "l": 9, "m": 6, "n": 1, "o": 94, "p": 53, "r": 2, "s": 10, "t": 77, "u": 24, "w": 6, "y": 88, "$": 159},
    "y": {"a": 39, "b": 8, "c": 23, "d": 15, "e": 27, "f": 4, "g": 11, "h": 3, "i": 17, "k": 1, "l": 52, "m": 34, "n": 29, "o": 26, "p": 39, "r": 31, "s": 35, "t": 26, "u": 5, "w": 6, "x": 3, "z": 3, "$": 561},
    "z": {"a": 101, "b": 2, "c": 1, "d": 2, "e": 441, "g": 1, "h": 1, "i": 102, "k": 1, "l": 23, "m": 1, "n": 1, "o": 178, "r": 2, "t": 2, "u": 15, "w": 1, "y": 46, "z": 49, "$": 29},
}


# --- per-key model --------------------------------------------------


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _ema(old, new):
    return (1.0 - EMA_ALPHA) * old + EMA_ALPHA * new


def confidence(entry):
    """
    Blend speed and accuracy into 0..1 for one stored key entry.

    A key with no latency samples yet scores zero on speed rather than
    getting a free pass -- it has to actually be typed to go green.
    """
    ms = entry.get("ms")
    speed = 0.0 if ms is None else _clamp(
        (TARGET_MS - ms) / (TARGET_MS - FLOOR_MS), 0.0, 1.0
    )
    err = _clamp(entry.get("err", 0.0), 0.0, ERR_CEILING)
    acc = 1.0 - err / ERR_CEILING
    return SPEED_WEIGHT * speed + ACC_WEIGHT * acc


def is_green(entry):
    """
    Mastered: at the goal speed, accurately, with evidence behind it.

    The speed gate is explicit rather than left to the blend. Mastery is
    supposed to mean "40 wpm on this key", and a weighted score can be
    dragged over the line by accuracy alone -- which would quietly turn
    the win condition into something you can reach at 20 wpm.
    """
    if not entry:
        return False
    if entry.get("n", 0) < MIN_SAMPLES:
        return False
    ms = entry.get("ms")
    if ms is None or ms > MASTER_MS:
        return False
    return entry.get("conf", 0.0) >= GREEN


def is_ready(entry):
    """
    Ready to be offered a new letter. NOT mastery -- see the note above.

    Deliberately speed-blind. A kid hunting and pecking at 5 wpm is
    typing correctly, just slowly, and there is no pedagogical reason to
    withhold the rest of the alphabet from them until they get fast. Speed
    is what `is_green` and the heatmap are for; this only asks whether
    they can hit the key on purpose.
    """
    if not entry:
        return False
    if entry.get("n", 0) < READY_SAMPLES:
        return False
    return (1.0 - entry.get("err", 1.0)) >= READY_ACC


def ensure(profile):
    """Fill in the adaptive keys on a profile that predates this engine."""
    profile.setdefault("keys", {})
    profile.setdefault("alphabet", START_ALPHABET)
    return profile


def alphabet(profile):
    """The letters this kid has unlocked, in unlock order."""
    return profile.get("alphabet") or START_ALPHABET


def key_entry(profile, ch):
    return profile.get("keys", {}).get(ch)


def key_state(profile, ch):
    """
    'green' | 'steady' | 'learning' | 'locked' -- what the heatmap paints.

    'steady' is the middle rung, and it exists because mastery now means
    40 wpm: without it a kid would sit on the same colour for the better
    part of two years while genuinely getting better every week. Steady
    says "you can hit this key on purpose now" -- the thing that actually
    earned them the next letter -- and green stays for the goal.
    """
    if ch not in alphabet(profile):
        return "locked"
    entry = key_entry(profile, ch)
    if is_green(entry):
        return "green"
    return "steady" if is_ready(entry) else "learning"


def burst_size(profile):
    """
    How many letters this kid's current performance is worth, 1..BURST_MAX.

    Reads the alphabet they already hold: how accurately they type it, and
    how close to the goal speed. Both are ability, which is the only thing
    allowed to gate the alphabet.
    """
    keys = profile.get("keys") or {}
    entries = [keys.get(c) for c in alphabet(profile)]
    entries = [e for e in entries if e and e.get("n", 0) >= READY_SAMPLES]
    if not entries:
        return 1

    acc = sum(1.0 - e.get("err", 1.0) for e in entries) / len(entries)
    timed = [e.get("ms") for e in entries if e.get("ms") is not None]

    size = 1
    if acc >= BURST_ACC:
        size += 1
    if timed and (sum(timed) / len(timed)) <= MASTER_MS:
        size += 1
    return min(BURST_MAX, size)


def _next_letter(unlocked):
    for ch in FREQ_ORDER:
        if ch not in unlocked:
            return ch
    return None


def merge_keys(profile, session_keys):
    """
    Fold one session's raw per-key counters into the profile.

    `session_keys` is `summary["keys"]` from `engine.Session`:
    `{ch: {"n", "err", "ms_sum", "ms_n"}}`. Stored form is the compact
    recent-weighted one from DESIGN 4.1: `{ch: {"n", "err", "ms", "conf"}}`.

    Returns `{"green": [...], "unlocked": [...]}` -- the letters that just
    crossed into mastery and any letter this earned, so the caller can
    celebrate. Both lists are usually empty.
    """
    ensure(profile)
    keys = profile["keys"]
    if not session_keys:
        return {"green": [], "unlocked": []}

    was_green = {ch for ch, e in keys.items() if is_green(e)}

    for ch, s in session_keys.items():
        n = s.get("n", 0)
        if not ch or len(ch) != 1 or n <= 0:
            continue
        s_err = s.get("err", 0) / float(n)
        ms_n = s.get("ms_n", 0)
        s_ms = (s.get("ms_sum", 0.0) / ms_n) if ms_n else None

        e = keys.get(ch)
        if e is None:
            # First sighting: the session IS the average.
            e = {"n": 0, "err": s_err, "ms": s_ms, "conf": 0.0}
            keys[ch] = e
        else:
            e["err"] = _ema(e.get("err", 0.0), s_err)
            if s_ms is not None:
                prev_ms = e.get("ms")
                e["ms"] = s_ms if prev_ms is None else _ema(prev_ms, s_ms)

        e["n"] = e.get("n", 0) + n
        e["err"] = round(e["err"], 4)
        if e.get("ms") is not None:
            e["ms"] = round(e["ms"], 1)
        e["conf"] = round(confidence(e), 3)

    fresh_green = sorted(
        ch for ch, e in keys.items() if is_green(e) and ch not in was_green
    )

    # This asks `is_ready`, not `is_green`. Gating the next letter on
    # mastery meant gating it on the game's win condition, which no
    # beginner could clear -- and since every unlocked letter had to
    # clear it, one hard reach stalled a kid forever.
    #
    # A strong session is worth more than one letter. The check runs
    # against the letters that have actually been typed, so the freshly
    # granted ones don't veto their own siblings; ability is the throttle
    # and nothing else is.
    unlocked = []
    allowance = burst_size(profile)
    for _ in range(len(FREQ_ORDER)):
        if len(unlocked) >= allowance:
            break
        current = alphabet(profile)
        judged = [keys.get(c) for c in current if c not in unlocked]
        if not all(is_ready(e) for e in judged):
            break
        nxt = _next_letter(current)
        if nxt is None:
            break
        profile["alphabet"] = current + nxt
        unlocked.append(nxt)

    return {"green": fresh_green, "unlocked": unlocked}


def focus_letter(profile):
    """
    The letter to force into every generated word: the weakest unlocked
    one. Never-typed letters sort first (conf 0), which is what we want --
    a freshly unlocked letter becomes the focus immediately.
    """
    unlocked = alphabet(profile)
    if not unlocked:
        return None
    keys = profile.get("keys", {})

    def rank(ch):
        e = keys.get(ch) or {}
        return (e.get("conf", 0.0), e.get("n", 0), FREQ_ORDER.find(ch))

    return min(unlocked, key=rank)


def weighted_char(profile, rng=None):
    """
    One letter from the unlocked alphabet, biased toward weak keys.

    The +0.2 floor keeps mastered letters in rotation so a drill never
    turns into the same three letters over and over.
    """
    rng = rng or random
    unlocked = alphabet(profile)
    keys = profile.get("keys", {})
    weights = [(1.0 - (keys.get(c, {}).get("conf", 0.0))) + 0.2 for c in unlocked]
    return _pick(list(zip(unlocked, weights)), rng)


def has_data(profile):
    """True once the kid has fed the engine at least one keystroke."""
    return bool(profile.get("keys"))


# --- word generation ------------------------------------------------


def _pick(pool, rng):
    """Weighted choice over [(value, weight), ...]."""
    total = sum(w for _, w in pool)
    if total <= 0:
        return pool[-1][0]
    r = rng.uniform(0.0, total)
    value = pool[-1][0]
    for v, w in pool:
        r -= w
        if r <= 0:
            value = v
            break
    return value


def _ok_next(out, ch):
    """
    Bigram frequencies alone will happily emit "trdembl". These three
    rules are what keeps output on the pronounceable side of the line.
    """
    if ch in VOWELS or not out or out[-1] in VOWELS:
        return True
    if len(out) == 1:
        return out[-1] + ch in ONSETS   # word-initial clusters are picky
    if out[-2] not in VOWELS:
        return False                    # never three consonants in a row
    return True


def _can_end(ch):
    """Some letters simply don't end English words -- J, Q, V."""
    return BIGRAMS.get(ch, {}).get("$", 0) >= END_FLOOR


def _ok_end(out):
    if not out or not _can_end(out[-1]):
        return False
    if len(out) < 2 or out[-1] in VOWELS or out[-2] in VOWELS:
        return True
    return out[-2] + out[-1] in CODAS


def _walk(letters, rng, min_len, max_len, focus=None):
    """
    A Markov walk over BIGRAMS, restricted to `letters`.

    If `focus` is given the walk works it in itself rather than leaving it
    to injection: it won't stop before placing it, and on the last slot it
    takes it if the cluster rules allow. Placing it during the walk keeps
    the word pronounceable; injecting it afterwards can't.
    """
    prev = "^"
    out = []
    while len(out) < max_len:
        row = BIGRAMS.get(prev) or {}
        pool = [(c, w) for c, w in row.items()
                if c in letters and _ok_next(out, c)]
        wants_focus = focus is not None and focus not in out
        if wants_focus:
            if len(out) >= max_len - 1 and _can_end(focus):
                forced = [(c, w) for c, w in pool if c == focus]
                if forced:
                    pool = forced
            else:
                # Weight it up rather than slotting it in at the end: a
                # word with the focus buried in the middle reads better,
                # and nothing in English ends in J.
                pool = [(c, w * FOCUS_BOOST if c == focus else w)
                        for c, w in pool]
        if (len(out) >= min_len and not wants_focus
                and _ok_end(out) and row.get("$")):
            pool.append(("$", row["$"]))
        if not pool:
            # Dead end (small alphabets hit this): restart the chain from
            # word-start frequencies rather than emitting nothing.
            pool = [(c, BIGRAMS["^"].get(c, 1)) for c in letters
                    if _ok_next(out, c)]
            if not pool:
                break
        ch = _pick(pool, rng)
        if ch == "$":
            break
        out.append(ch)
        prev = ch

    # Hitting max_len mid-cluster leaves things like "brerysp".
    while len(out) > min_len and not _ok_end(out):
        out.pop()
    return "".join(out)


def _triple(word):
    """Three consonants in a row -- the loudest tell of keyboard mash."""
    run = 0
    for ch in word:
        run = 0 if ch in VOWELS else run + 1
        if run >= 3:
            return True
    return False


def _speakable(word):
    """The same rules the walk follows, checked against a finished word."""
    for i, ch in enumerate(word):
        if not _ok_next(word[:i], ch):
            return False
    return _ok_end(word)


def _inject(word, focus, letters, rng):
    """
    Last resort when the walk won't produce the focus letter (common on a
    six-letter alphabet). Slot it in wherever the bigrams like it most,
    preferring spots that don't wreck the word's pronounceability.
    """
    if not word:
        return focus
    best, best_key = word[:0] + focus + word, None
    for i in range(len(word) + 1):
        left = word[i - 1] if i > 0 else "^"
        right = word[i] if i < len(word) else "$"
        cand = word[:i] + focus + word[i:]
        key = (_speakable(cand),
               not _triple(cand),
               BIGRAMS.get(left, {}).get(focus, 0)
               + BIGRAMS.get(focus, {}).get(right, 0))
        if best_key is None or key > best_key:
            best, best_key = cand, key
    return best


def generate_word(letters, focus, rng=None, min_len=MIN_WORD, max_len=MAX_WORD):
    """
    A pronounceable pseudo-word using only `letters`, always containing
    `focus`. Terminates: bounded retries, then injection.
    """
    rng = rng or random
    letters = "".join(sorted(set(letters)))
    if not letters:
        return focus or ""
    if focus and focus not in letters:
        letters += focus

    word = ""
    for _ in range(MAX_WORD_TRIES):
        word = _walk(letters, rng, min_len, max_len, focus)
        if not word:
            continue
        if not focus or focus in word:
            return word
    if not word:
        word = focus or rng.choice(letters)
    return _inject(word, focus, letters, rng) if focus else word


def _real_words(letters):
    """Real words from the lesson content that fit the unlocked alphabet."""
    pool = set(letters)
    out = []
    for lvl in lessons.LEVELS:
        for w in lvl["words"]:
            if len(w) >= MIN_WORD and w.isalpha() and set(w) <= pool:
                out.append(w)
    return sorted(set(out))


def generate_lesson(profile, n_words, rng=None):
    """
    A drill's worth of words: mostly generated, seasoned with real words
    the kid can already spell, all of it hammering the focus letter.
    """
    rng = rng or random
    ensure(profile)
    letters = alphabet(profile)
    focus = focus_letter(profile)

    real = _real_words(letters)
    # Real words that drill the focus letter earn their place first.
    real.sort(key=lambda w: (focus not in w, len(w)))
    n_real = min(len(real), int(round(n_words * REAL_WORD_SHARE)))

    words = real[:n_real]
    words += [generate_word(letters, focus, rng)
              for _ in range(n_words - n_real)]
    rng.shuffle(words)
    return words
