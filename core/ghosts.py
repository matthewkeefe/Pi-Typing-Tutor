"""
Ghost recordings -- the data behind asynchronous sibling racing (#21).

A ghost is the shape of one run: cumulative seconds at each completed
word. Replaying it is a lookup, not a simulation, so a race against a
recording is byte-for-byte the same every time it's watched.

Why races use a fixed passage list rather than whatever a kid last typed:
the drill modes generate their words per kid, from that kid's own unlocked
alphabet and weakest letter, so two siblings essentially never produce the
same sequence. Keying ghosts off those runs would give everyone a shelf of
recordings nobody else could ever race. The passages here are shared and
identical for every profile, which is what makes "race your sister" work
at all.

Everything is curses-free and keyed off plain profile data.
"""

import zlib

from core import lessons

MAX_GHOSTS = 20      # per profile, oldest dropped -- the history-cap pattern
PASSAGE_WORDS = 8


def _passage_list():
    """
    The shared race texts, one per lesson level that has plain words.

    Level 7 is sentences rather than words, so it sits this out -- per-word
    timing is the whole recording format.
    """
    out = []
    for level in lessons.LEVELS:
        words = [w for w in level["words"] if " " not in w]
        if len(words) < PASSAGE_WORDS:
            continue
        out.append((level["name"], tuple(words[:PASSAGE_WORDS])))
    return out


PASSAGES = _passage_list()


def key_for(words):
    """
    A stable id for a word sequence.

    crc32 rather than hash(): Python randomises string hashing per process,
    so a hash-based key would change every launch and orphan every ghost.
    Same reasoning as the cat's genes (see core/cat.py).
    """
    joined = " ".join(words)
    return "%08x" % (zlib.crc32(joined.encode("utf-8")) & 0xFFFFFFFF)


def passage_keys():
    """[(key, name, words), ...] for every shared passage."""
    return [(key_for(words), name, list(words)) for name, words in PASSAGES]


def find_passage(key):
    for k, name, words in passage_keys():
        if k == key:
            return name, words
    return None


def all_ghosts(profile):
    return profile.setdefault("ghosts", {})


def get(profile, key):
    """The recorded split times for `key`, or None."""
    times = all_ghosts(profile).get(key)
    if not times:
        return None
    return list(times)


def record(profile, key, times):
    """
    Store a run, keeping only the best one per passage.

    Best rather than latest so a ghost is something to aim at; a kid who
    has a bad round doesn't overwrite the run they were proud of. Ghosts
    only ever improve, which also means racing yourself never gets easier.
    """
    if not times:
        return False
    ghosts = all_ghosts(profile)
    existing = ghosts.get(key)
    if existing and existing[-1] <= times[-1]:
        return False

    ghosts.pop(key, None)          # re-insert so it counts as most recent
    ghosts[key] = [round(float(t), 3) for t in times]

    # Bounded save: drop the oldest keys once we're over the cap. dicts
    # keep insertion order, and json round-trips it, so "oldest" survives
    # a save/load cycle.
    while len(ghosts) > MAX_GHOSTS:
        ghosts.pop(next(iter(ghosts)))
    return True


def position(times, elapsed):
    """
    How many words the ghost had finished at `elapsed` seconds.

    A plain count of splits already passed -- deterministic, and cheap
    enough to call every frame.
    """
    if not times:
        return 0
    done = 0
    for t in times:
        if elapsed >= t:
            done += 1
        else:
            break
    return done


def finish_time(times):
    return times[-1] if times else None


def opponents(all_profiles, me, key):
    """
    Everyone with a recording for this passage, me included.

    Racing your own ghost is the solo-kid case and the most common one on
    a single-child device, so it is never filtered out.
    """
    out = []
    for name in sorted(all_profiles):
        times = get(all_profiles[name], key)
        if times:
            out.append((name, times, name == me))
    return out


def raceable(all_profiles):
    """Passages somebody has run, most-contested first."""
    out = []
    for key, name, words in passage_keys():
        runners = sum(1 for p in all_profiles.values() if get(p, key))
        out.append((key, name, words, runners))
    out.sort(key=lambda row: (-row[3], row[1]))
    return out
