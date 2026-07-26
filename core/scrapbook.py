"""
The Scrapbook -- the completion ladder that runs alongside the shop.

The shop is where fish go. This is where everything else accumulates: the
fish species a kid has hooked, the gifts the cat has dragged in, the toys
and outfits they own, the tricks they taught, the ribbons they won.

The research finding behind it (docs/research/pet-game-care-loops.md) is
that a solved daily loop flatlines within months without something that
accumulates on a scale of seasons. Neopets had stamp albums; Animal
Crossing has a museum.

Two rules hold the whole thing up:

**Nothing here can ever be lost.** Not on a bad day, not after an absence,
not by spending anything. Every list is append-only, and there is no code
path that removes from one. That is the additive-only principle (DESIGN
guard 2) in its purest form.

**Nothing here expires.** Unfound items show as silhouettes, which say
"there is more to find" and never "you missed it". No countdowns, no
limited windows -- that is guard 8, and a collection is exactly where a
game would normally start manufacturing urgency.

Derived collections (toys, outfits, tricks) read their source of truth
rather than copying it, so the album can never drift out of step with the
inventory it describes.
"""

from core import adaptive

# --- fish species ----------------------------------------------------
#
# One species per letter, and here is the nice part: rarity is not a dice
# roll, it's English. A kid meets the E-fish in their first week because
# `e` is in everything, and the Q-fish is a legend because `q` is the last
# letter they unlock and turns up in almost nothing.
#
# So catching is deterministic -- type a word containing the letter and
# the fish is yours. No roll, no near-miss, no "keep fishing and maybe".
# A random drop table here would be a loot box pointed at a seven-year-old,
# and the emergent rarity is better than the manufactured kind anyway.

FISH_NAMES = {
    "e": "eel", "n": "needlefish", "i": "icefish", "t": "trout",
    "r": "ray", "l": "lionfish", "s": "salmon", "a": "angelfish",
    "u": "unicornfish", "o": "oarfish", "d": "dory", "y": "yellowtail",
    "c": "catfish", "h": "herring", "g": "guppy", "m": "minnow",
    "p": "pike", "b": "bass", "k": "koi", "v": "viperfish",
    "w": "wrasse", "f": "flounder", "z": "zebrafish", "x": "x-ray tetra",
    "q": "queen angel", "j": "jellynose",
}

# Tiers follow unlock order, so "rare" and "late" mean the same thing.
TIERS = [(8, "common"), (16, "uncommon"), (22, "rare"), (26, "legendary")]


def fish_letters():
    """Every species letter, in the order a kid will meet them."""
    return [c for c in adaptive.FREQ_ORDER if c in FISH_NAMES]


def fish_tier(letter):
    idx = adaptive.FREQ_ORDER.find(letter)
    if idx < 0:
        return "common"
    for cutoff, name in TIERS:
        if idx < cutoff:
            return name
    return "legendary"


def fish_name(letter):
    return FISH_NAMES.get(letter, "fish")


# --- show-up gifts ---------------------------------------------------
#
# What the cat brings for turning up. Deferred out of Phase 3 because
# there was nowhere to put a feather until this album existed.
#
# Ordinary things a cat would actually carry in. Nothing here is valuable
# and nothing is a payout -- the point is that it accumulates.

GIFTS = [
    ("feather", "a grey feather"),
    ("bottlecap", "a shiny bottle cap"),
    ("leaf", "a very good leaf"),
    ("pebble", "a smooth pebble"),
    ("acorn", "one acorn"),
    ("shell", "half a shell"),
    ("button", "a lost button"),
    ("twig", "a promising twig"),
    ("marble", "a cloudy marble"),
    ("ribbonscrap", "a scrap of ribbon"),
]
GIFT_IDS = [g for g, _ in GIFTS]
GIFT_NAMES = dict(GIFTS)


# --- storage ---------------------------------------------------------


def book(profile):
    """The stored half of the scrapbook, filled in for older saves."""
    sb = (profile if profile is not None else {}).setdefault("scrapbook", {})
    sb.setdefault("fish", [])
    sb.setdefault("gifts", [])
    sb.setdefault("ribbons", [])
    return sb


def caught(profile):
    return list(book(profile)["fish"])


def found_gifts(profile):
    return list(book(profile)["gifts"])


def ribbons(profile):
    return list(book(profile)["ribbons"])


def catch(profile, letter):
    """
    Record the species for `letter`. Returns its name if it's new.

    Append-only. There is deliberately no counterpart that removes one.
    """
    letter = (letter or "").lower()
    if letter not in FISH_NAMES:
        return None
    fish = book(profile)["fish"]
    if letter in fish:
        return None
    fish.append(letter)
    return fish_name(letter)


def catch_from_word(profile, word):
    """
    Every new species in a completed word.

    Called from the feed drill: typing "quiet" while the Q-fish is still
    a silhouette is the moment that collection is designed around.
    """
    out = []
    for ch in sorted(set((word or "").lower())):
        name = catch(profile, ch)
        if name:
            out.append((ch, name))
    return out


def find_gift(profile, gift_id):
    """Record a show-up gift. Returns its description if it's new."""
    if gift_id not in GIFT_NAMES:
        return None
    gifts = book(profile)["gifts"]
    if gift_id in gifts:
        return None
    gifts.append(gift_id)
    return GIFT_NAMES[gift_id]


def award_ribbon(profile, ribbon_id):
    """A contest ribbon (#28). Append-only like everything else."""
    if not ribbon_id:
        return None
    rib = book(profile)["ribbons"]
    if ribbon_id in rib:
        return None
    rib.append(ribbon_id)
    return ribbon_id


# --- albums ----------------------------------------------------------
#
# Derived collections read their source of truth rather than copying it.
# A duplicated list is a list that eventually disagrees with the thing it
# was copied from, and the album would be the last place anyone looked.


def _album_fish(profile):
    have = set(caught(profile))
    return [(fish_name(c), c in have, fish_tier(c)) for c in fish_letters()]


def _album_gifts(profile):
    have = set(found_gifts(profile))
    return [(name, gid in have, "") for gid, name in GIFTS]


def _album_toys(profile):
    from core import shop
    owned = set((profile.get("inventory") or {}).get("toys") or [])
    rows = []
    for item in shop.CATALOG:
        if item["kind"] == shop.KIND_TOY:
            rows.append((item["name"], item["id"] in owned, ""))
    return rows


def _album_outfits(profile):
    from core import shop
    owned = set((profile.get("inventory") or {}).get("accessories") or [])
    rows = []
    for item in shop.CATALOG:
        if item["kind"] == shop.KIND_ACCESSORY:
            rows.append((item["name"], item["id"] in owned, ""))
    return rows


def _album_tricks(profile):
    from core import cat
    known = set(((profile.get("cat") or {}).get("tricks")) or [])
    return [(name, name in known, "") for name in cat.TRICKS]


def _album_ribbons(profile):
    have = set(ribbons(profile))
    if not have:
        return []
    return [(r, True, "") for r in sorted(have)]


ALBUMS = [
    ("Fish", _album_fish),
    ("Gifts", _album_gifts),
    ("Toys", _album_toys),
    ("Outfits", _album_outfits),
    ("Tricks", _album_tricks),
    ("Ribbons", _album_ribbons),
]


def albums(profile):
    """[(title, [(label, found, note), ...]), ...] -- empty pages dropped."""
    out = []
    for title, build in ALBUMS:
        rows = build(profile)
        if rows:
            out.append((title, rows))
    return out


def page_progress(rows):
    return sum(1 for _, found, _ in rows if found), len(rows)


def completion(profile):
    """
    Overall completion 0..100, for the milestone tracks in #29.

    Counts every page equally by item, so the big collections dominate --
    which is right: the fish album is the long haul and should feel like
    the bulk of it.
    """
    found = total = 0
    for _title, rows in albums(profile):
        f, t = page_progress(rows)
        found += f
        total += t
    if not total:
        return 0.0
    return 100.0 * found / total
