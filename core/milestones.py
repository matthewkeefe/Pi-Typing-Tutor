"""
Milestone unlocks -- the second progression bar.

Fish are spendable and therefore finite in usefulness: a kid who owns the
shop has nothing left to earn. Milestones are the unspendable half. Every
session advances both, and the things milestones unlock cannot be bought
at any price.

The research calls this dual progression (Nintendogs' two currencies, in
docs/research/pet-game-care-loops.md). What matters here is which of the
two carries which meaning:

- **Fish** are volume. Show up, type, earn -- a bad day pays the same as
  a good one, and that is deliberate (guard 4).
- **Milestones** are accumulation. Not thresholds you clear by being
  good, but totals that only ever go up by continuing to turn up.

Every track is derived from data the profile already keeps. No new
counters, so a kid who has been playing for months gets full retroactive
credit the first time this runs rather than starting from zero -- taking
someone back to nothing for a feature they never saw would be the exact
opposite of guard 2.
"""

from core import adaptive, scrapbook

# --- tracks ----------------------------------------------------------
#
# (id, label, reader). Readers take a profile and return a plain number.


def _words(profile):
    return int((profile or {}).get("total_words", 0) or 0)


def _care_days(profile):
    return int((profile or {}).get("days_played", 0) or 0)


def _letters_mastered(profile):
    keys = (profile or {}).get("keys") or {}
    return sum(1 for ch in adaptive.alphabet(profile or {})
               if adaptive.is_green(keys.get(ch) or {}))


def _album(profile):
    return int(scrapbook.completion(profile or {}))


TRACKS = [
    ("words", "Words typed", _words),
    ("days", "Days shown up", _care_days),
    ("letters", "Letters mastered", _letters_mastered),
    ("album", "Scrapbook filled", _album),
]
TRACK_READERS = {tid: fn for tid, _label, fn in TRACKS}
TRACK_LABELS = {tid: label for tid, label, _fn in TRACKS}

# --- the ladder ------------------------------------------------------
#
# (track, threshold, item_id, announcement). Thresholds are generous at
# the bottom on purpose: the first one should land in a kid's first week,
# because a reward track nobody reaches the first rung of is decoration.
#
# Rewards are cosmetic without exception. Nothing here makes a game
# easier, pays out fish, or is better than something buyable -- it is
# just different, and unbuyable.

LADDER = [
    ("words", 500, "milestone_ribbon", "your first 500 words"),
    ("words", 2500, "golden_collar", "two and a half thousand words"),
    ("words", 10000, "silver_bell", "ten thousand words"),
    ("words", 50000, "comet_charm", "fifty thousand words"),

    ("days", 7, "milestone_tag", "a whole week of showing up"),
    ("days", 30, "velvet_cushion", "thirty days"),
    ("days", 100, "sunbeam_mat", "a hundred days"),
    ("days", 365, "old_friend_blanket", "a year together"),

    ("letters", 1, "first_key_charm", "your first mastered letter"),
    ("letters", 13, "half_alphabet_pin", "half the alphabet mastered"),
    ("letters", 26, "star_charm", "every letter mastered"),

    ("album", 25, "album_clip", "a quarter of the scrapbook"),
    ("album", 50, "album_frame", "half the scrapbook"),
    ("album", 100, "album_crown", "the whole scrapbook"),
]


def milestone_id(track, threshold):
    return "%s:%d" % (track, threshold)


def value(profile, track):
    reader = TRACK_READERS.get(track)
    return reader(profile) if reader else 0


def claimed(profile):
    """Milestone ids already awarded. Append-only, like everything else."""
    return (profile if profile is not None else {}).setdefault(
        "milestones", [])


def earned(profile):
    """Every milestone this profile's history qualifies for, right now."""
    out = []
    for track, threshold, item_id, blurb in LADDER:
        if value(profile, track) >= threshold:
            out.append((milestone_id(track, threshold), track, threshold,
                        item_id, blurb))
    return out


def check_new(profile):
    """
    Award anything newly qualified. Returns [(item_id, blurb), ...].

    A returning kid can trip several at once -- that is the retroactive
    credit working, not a bug -- so callers should expect a list and
    queue the popups rather than assuming one.
    """
    from core import shop

    have = set(claimed(profile))
    fresh = []
    for mid, _track, _threshold, item_id, blurb in earned(profile):
        if mid in have:
            continue
        claimed(profile).append(mid)
        if grant(profile, item_id):
            fresh.append((item_id, blurb))
        else:
            fresh.append((item_id, blurb))
    return fresh


def grant(profile, item_id):
    """
    Put an unlocked item in the inventory. Never spends anything.

    Milestone items are real shop-catalogue entries so they render and
    equip like everything else -- they simply cannot be bought.
    """
    from core import shop

    item = shop.BY_ID.get(item_id)
    if not item:
        return False
    inv = shop.inventory(profile)
    if item["kind"] == shop.KIND_ACCESSORY:
        if item_id not in inv["accessories"]:
            inv["accessories"].append(item_id)
            return True
    elif item["kind"] == shop.KIND_DECOR:
        if item_id not in inv["decor"]:
            inv["decor"].append(item_id)
            return True
    elif item["kind"] == shop.KIND_TOY:
        if item_id not in inv["toys"]:
            inv["toys"].append(item_id)
            return True
    return False


def next_up(profile, track):
    """
    (current, threshold, blurb) for the next rung, or None when a track is
    finished. Used by the stats screen -- visible competence, and a thing
    to look forward to rather than a number that just happens.
    """
    current = value(profile, track)
    for t, threshold, _item, blurb in LADDER:
        if t == track and current < threshold:
            return current, threshold, blurb
    return None


def summary(profile):
    """[(label, current, threshold_or_None), ...] for every track."""
    out = []
    for track, label, _reader in TRACKS:
        nxt = next_up(profile, track)
        if nxt:
            current, threshold, _blurb = nxt
            out.append((label, current, threshold))
        else:
            out.append((label, value(profile, track), None))
    return out
