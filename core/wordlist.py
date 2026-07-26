"""
Shared access to `data/words.txt` -- the curated kid-appropriate vocabulary.

Two modes need it: Alphabet Soup validates the words a kid builds, and
Mystery Word draws its hidden word from the same pool. Everything here is
curses-free so it can be tested without a terminal.

The file is read once and kept as a frozenset. On a Pi that matters: 2122
words is nothing to hold, but re-reading the file per keystroke would not
be, and membership has to be O(1) because it runs on every word submitted.
"""

import os
from collections import Counter

DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "words.txt",
)

MIN_LEN = 3
BOWL_SIZES = (6, 7)     # tiles in an Alphabet Soup bowl
MIN_SOLUTIONS = 5       # issue #25's acceptance bar

_CACHE = {}


def load(path=None):
    """
    The word set, read once per path and cached thereafter.

    A missing or empty file yields an empty set rather than raising: a mode
    that depends on it should hide itself (see `soup.available`), not crash
    the menu on a fresh checkout.
    """
    path = path or DATA
    if path not in _CACHE:
        words = set()
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip().lower()
                    if not line or line.startswith("#"):
                        continue
                    if line.isalpha() and line.isascii():
                        words.add(line)
        except OSError:
            words = set()
        _CACHE[path] = frozenset(words)
    return _CACHE[path]


def reset_cache():
    """Drop the cache. For tests that point at a fixture file."""
    _CACHE.clear()


def is_word(word, path=None):
    return word.strip().lower() in load(path)


def for_alphabet(alphabet, path=None, min_len=MIN_LEN, max_len=None):
    """
    Every word spellable using only the letters in `alphabet`.

    Letters may repeat here -- this is the "has the kid met these letters"
    filter, not the tile constraint. Use `solutions` for the tile version.
    """
    allowed = set(alphabet)
    out = []
    for word in load(path):
        if len(word) < min_len:
            continue
        if max_len is not None and len(word) > max_len:
            continue
        if set(word) <= allowed:
            out.append(word)
    return sorted(out)


def formable(tiles, word):
    """
    True if `word` can be built from `tiles`, consuming each tile once.

    `tiles` is a Counter of available letters. This is the rule that makes a
    bowl a bowl: "letter" needs two t's and two e's, so a six-tile bowl of
    distinct letters cannot spell it however many of them look right.
    """
    need = Counter(word)
    for ch, count in need.items():
        if tiles.get(ch, 0) < count:
            return False
    return True


def solutions(letters, pool=None, path=None, min_len=MIN_LEN):
    """Every word in `pool` buildable from `letters` as tiles."""
    tiles = Counter(letters)
    candidates = pool if pool is not None else load(path)
    return sorted(w for w in candidates
                  if len(w) >= min_len and formable(tiles, w))


def seed_candidates(alphabet, path=None, sizes=BOWL_SIZES):
    """Words the right length to be a bowl, spellable from the alphabet."""
    lo, hi = min(sizes), max(sizes)
    return [w for w in for_alphabet(alphabet, path=path, min_len=lo, max_len=hi)]


def make_bowl(alphabet, rng, path=None, min_solutions=MIN_SOLUTIONS,
              sizes=BOWL_SIZES, attempts=40):
    """
    A bowl of tiles plus every word findable in it.

    The bowl is a real word's letters (#25: "generate from a seed word"),
    which guarantees at least one solution and tends to give a satisfying
    spread of shorter ones. Roughly one seed in five yields fewer than
    `min_solutions` -- repeated letters are the usual culprit, so "banana"
    and "church" are quietly rejected here rather than reaching a kid.

    Returns (tiles, solutions) with tiles as a shuffled list of letters, or
    None when the alphabet cannot produce a viable bowl at all. Callers
    should gate on `viable(alphabet)` rather than relying on the None.
    """
    pool = for_alphabet(alphabet, path=path)
    seeds = [w for w in pool if min(sizes) <= len(w) <= max(sizes)]
    if not seeds:
        return None

    order = list(seeds)
    rng.shuffle(order)
    for seed in order[:attempts]:
        found = solutions(seed, pool=pool)
        if len(found) >= min_solutions:
            tiles = list(seed)
            rng.shuffle(tiles)
            return tiles, found

    # Nothing cleared the bar in the sample: fall back to the best seed we
    # saw so the mode degrades to "thin" rather than "broken".
    best, best_found = None, []
    for seed in order[:attempts]:
        found = solutions(seed, pool=pool)
        if len(found) > len(best_found):
            best, best_found = seed, found
    if best is None:
        return None
    tiles = list(best)
    rng.shuffle(tiles)
    return tiles, best_found


def viable(alphabet, path=None, min_solutions=MIN_SOLUTIONS, sizes=BOWL_SIZES):
    """
    How many seeds in this alphabet clear the solution bar.

    Zero means Alphabet Soup has nothing to offer yet. The starting six
    letters (`enitrl`) score 2, which is why the mode is unlock-gated: the
    same two bowls forever is not a game.
    """
    pool = for_alphabet(alphabet, path=path)
    seeds = [w for w in pool if min(sizes) <= len(w) <= max(sizes)]
    good = 0
    for seed in seeds:
        if len(solutions(seed, pool=pool)) >= min_solutions:
            good += 1
    return good
