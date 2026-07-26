"""
The shop: catalog, weekly rotation, and the fish economy.

Fish are earned by **words typed**, never by hitting a score, so buying
power comes from showing up rather than from being good. That is the
whole point of the currency and it is why nothing in here is priced
against performance.

Things this module deliberately does NOT do, all of them design guards
rather than oversights:

- **No fake scarcity.** Stock rotates weekly but nothing expires and
  nothing is ever gone for good. Missing a week costs nothing; the item
  comes back around.
- **No gambling shapes.** No loot boxes, no random rewards, no "spin to
  win". You can see the price and you get the thing.
- **No pay-to-type.** Treats are buffers and bonuses only. Nothing here
  makes the typing easier or completes practice for a kid.
- **Nothing is taken away.** Fish never go negative, purchases are
  permanent, and there is no upkeep or decay on anything owned.

Rotation is derived from the ISO week, so it needs no stored state, no
clock beyond the date, and it survives a wiped save.
"""

import random
import zlib
from datetime import date

WEEKLY_SLOTS = 3        # not-yet-owned items offered each week
KIND_TOY = "toy"
KIND_TREAT = "treat"
KIND_LITTER = "litter"
KIND_DECOR = "decor"

# Streak insurance. Bought ahead of time -- protection, not pardon.
LITTER_TIERS = ["basic", "clumping", "deluxe"]
LITTER_COVERAGE = {"basic": 0, "clumping": 1, "deluxe": 2}

# What a treat does when the kid chooses to use it. Every one of these is
# a buffer or a bonus; none of them types anything for anybody.
EFFECT_SHIELD = "shield"          # first mistake in a platformer run forgiven
EFFECT_COMBO_SAVER = "combo_saver"  # first dropped dino combo restored
EFFECT_BONUS = "bonus"            # 30 seconds of double score

EFFECT_NAMES = {
    EFFECT_SHIELD: "mistake shield",
    EFFECT_COMBO_SAVER: "combo saver",
    EFFECT_BONUS: "bonus round",
}
EFFECT_BLURBS = {
    EFFECT_SHIELD: "your first slip in Platform Jumper is forgiven",
    EFFECT_COMBO_SAVER: "your first dropped combo in Dino Chomp comes back",
    EFFECT_BONUS: "30 seconds of double score in Dino Chomp",
}

BONUS_SECONDS = 30.0
BONUS_MULTIPLIER = 2

# Everyday prices are days of fish, not weeks -- a full care day is
# roughly 50 fish, so most of this is one or two days of showing up.
CATALOG = [
    # --- toys: permanent, unlock idle animations and mini-game variants
    {"id": "yarn_ball", "kind": KIND_TOY, "name": "Yarn ball", "price": 25,
     "blurb": "endlessly batted, never caught",
     "says": "I could chase that for hours."},
    {"id": "cardboard_box", "kind": KIND_TOY, "name": "Cardboard box", "price": 30,
     "blurb": "the finest furniture known to cats",
     "says": "If I fits, I sits."},
    {"id": "feather_wand", "kind": KIND_TOY, "name": "Feather wand", "price": 35,
     "blurb": "for the serious hunter",
     "says": "*pupils enormous*"},
    {"id": "crinkle_tunnel", "kind": KIND_TOY, "name": "Crinkle tunnel", "price": 45,
     "blurb": "loud, and that's the point",
     "says": "I will live in there now."},
    {"id": "red_dot", "kind": KIND_TOY, "name": "The red dot", "price": 40,
     "blurb": "nobody has ever caught it",
     "says": "This time. This time I get it."},

    # --- treats: consumable buffers, chosen by the kid before a game
    {"id": "tuna_flake", "kind": KIND_TREAT, "name": "Tuna flake", "price": 18,
     "effect": EFFECT_SHIELD, "blurb": "a small, serious snack",
     "says": "Yes. That one. Right now."},
    {"id": "salmon_bite", "kind": KIND_TREAT, "name": "Salmon bite", "price": 24,
     "effect": EFFECT_SHIELD, "blurb": "fancy, and it knows it",
     "says": "*sniffs approvingly*"},
    {"id": "catnip_cookie", "kind": KIND_TREAT, "name": "Catnip cookie", "price": 30,
     "effect": EFFECT_COMBO_SAVER, "blurb": "makes everything hilarious",
     "says": "*already rolling on the floor*"},
    {"id": "birthday_feast", "kind": KIND_TREAT, "name": "Birthday feast", "price": 55,
     "effect": EFFECT_BONUS, "blurb": "the whole spread, no occasion needed",
     "says": "Is it my birthday? It's my birthday."},

    # --- litter: streak insurance, bought before you need it
    {"id": "clumping", "kind": KIND_LITTER, "name": "Clumping litter", "price": 40,
     "tier": "clumping", "blurb": "covers one missed day",
     "says": "Tidier. I approve."},
    {"id": "deluxe", "kind": KIND_LITTER, "name": "Self-raking deluxe", "price": 90,
     "tier": "deluxe", "blurb": "covers two missed days",
     "says": "It rakes ITSELF. What a world."},

    # --- decor: the visible record of months of care
    {"id": "rug", "kind": KIND_DECOR, "name": "Woven rug", "price": 30,
     "art": ["[~~~~]"], "blurb": "for dignified lounging",
     "says": "Mine. All of it."},
    {"id": "cushion", "kind": KIND_DECOR, "name": "Round cushion", "price": 28,
     "art": ["(____)"], "blurb": "shaped like a loaf, for a loaf",
     "says": "*immediately asleep*"},
    {"id": "plant", "kind": KIND_DECOR, "name": "Potted plant", "price": 35,
     "art": [" \\|/ ", " [_] "], "blurb": "destined for the floor",
     "says": "I'm going to knock that over."},
    {"id": "window_perch", "kind": KIND_DECOR, "name": "Window perch", "price": 50,
     "art": ["+----+", "|    |", "+====+"], "blurb": "front row for bird TV",
     "says": "Birds. So many birds."},
    {"id": "shelf", "kind": KIND_DECOR, "name": "Wall shelf", "price": 45,
     "art": ["======", "  ||  "], "blurb": "high ground, secured",
     "says": "From up there I see everything."},

    # --- the dream item: always visible, priced for saving up
    {"id": "cat_tree", "kind": KIND_DECOR, "name": "Deluxe cat tree", "price": 900,
     "art": [" +--+ ", " |  | ", "=+--+=", "  ||  ", " /||\\ "],
     "blurb": "three storeys. THREE.", "dream": True,
     "says": "One day. One day that will be mine."},
]

BY_ID = {item["id"]: item for item in CATALOG}
DREAM_ITEM = next(i for i in CATALOG if i.get("dream"))


# --- inventory -------------------------------------------------------


def inventory(profile):
    """The profile's inventory, filled in for saves that predate the shop."""
    inv = profile.setdefault("inventory", {})
    inv.setdefault("toys", [])
    inv.setdefault("treats", {})
    inv.setdefault("litter", "basic")
    inv.setdefault("decor", [])
    return inv


def owns(profile, item_id):
    """
    True for permanent things already owned. Treats are consumable, so
    they are never 'owned' -- you can always buy another.
    """
    item = BY_ID.get(item_id)
    if item is None:
        return False
    inv = inventory(profile)
    if item["kind"] == KIND_TOY:
        return item_id in inv["toys"]
    if item["kind"] == KIND_DECOR:
        return item_id in inv["decor"]
    if item["kind"] == KIND_LITTER:
        have = LITTER_COVERAGE.get(inv["litter"], 0)
        return have >= LITTER_COVERAGE.get(item["tier"], 0)
    return False


def treat_count(profile, item_id):
    return inventory(profile)["treats"].get(item_id, 0)


def owned_decor(profile):
    return [BY_ID[i] for i in inventory(profile)["decor"] if i in BY_ID]


def litter_coverage(profile):
    """How many missed days this kid's litter tier covers."""
    return LITTER_COVERAGE.get(inventory(profile)["litter"], 0)


# --- rotation --------------------------------------------------------


def _order_key(item_id, salt):
    """
    Stable shuffle key. zlib.crc32 rather than hash(): Python randomises
    string hashing per process, so hash() would reshuffle the shop on
    every launch.
    """
    return zlib.crc32(("%s:%s" % (item_id, salt)).encode("ascii"))


def _rotatable():
    return [i for i in CATALOG if not i.get("dream")]


def week_salt(today=None):
    iso = (today or date.today()).isocalendar()
    return "%04d-w%02d" % (iso[0], iso[1])


def available_this_week(profile, today=None):
    """
    This week's stock: the first few not-yet-owned items in a stable
    per-week order. Buying one slides the next in rather than reshuffling
    the rest, so the shelf stays recognisable all week.
    """
    salt = week_salt(today)
    ordered = sorted(_rotatable(), key=lambda i: _order_key(i["id"], salt))
    return [i for i in ordered if not owns(profile, i["id"])][:WEEKLY_SLOTS]


def featured_today(profile, today=None):
    """
    One extra item keyed to the date, so there's a reason to look in
    every day and not only on rotation day. Still nothing that expires:
    everything here returns.
    """
    today = today or date.today()
    salt = today.isoformat()
    regulars = {i["id"] for i in available_this_week(profile, today)}
    ordered = sorted(_rotatable(), key=lambda i: _order_key(i["id"], salt))
    for item in ordered:
        if item["id"] not in regulars and not owns(profile, item["id"]):
            return item
    return None


def shelf(profile, today=None):
    """Everything on offer right now, in display order."""
    items = available_this_week(profile, today)
    feature = featured_today(profile, today)
    if feature is not None:
        items = items + [feature]
    if not owns(profile, DREAM_ITEM["id"]):
        items = items + [DREAM_ITEM]
    return items


def is_featured(profile, item_id, today=None):
    feature = featured_today(profile, today)
    return feature is not None and feature["id"] == item_id


# --- buying ----------------------------------------------------------


def fish(profile):
    return profile.get("fish", 0)


def can_buy(profile, item_id):
    """Returns (ok, reason). The reason is shown to the kid, so it's kind."""
    item = BY_ID.get(item_id)
    if item is None:
        return False, "That's not for sale."
    if owns(profile, item_id):
        return False, "You've already got that one."
    short = item["price"] - fish(profile)
    if short > 0:
        return False, "%d more fish and it's yours." % short
    return True, ""


def buy(profile, item_id):
    """
    Spend fish on an item. Returns True if it happened.

    Fish can never go negative and a refused purchase changes nothing,
    so a power cut mid-buy loses at most the purchase.
    """
    ok, _ = can_buy(profile, item_id)
    if not ok:
        return False
    item = BY_ID[item_id]
    inv = inventory(profile)

    profile["fish"] = fish(profile) - item["price"]
    kind = item["kind"]
    if kind == KIND_TOY:
        inv["toys"].append(item_id)
    elif kind == KIND_DECOR:
        inv["decor"].append(item_id)
    elif kind == KIND_LITTER:
        inv["litter"] = item["tier"]
    elif kind == KIND_TREAT:
        inv["treats"][item_id] = inv["treats"].get(item_id, 0) + 1
    return True


# --- treat effects ---------------------------------------------------


def active_effects(profile):
    return profile.setdefault("active_effects", {})


def has_effect(profile, effect):
    return bool(active_effects(profile).get(effect))


def activate(profile, item_id):
    """
    Use a treat, arming its effect for the next game that can use it.

    Effects don't stack -- one of each at a time -- and an armed effect
    survives a restart, so nothing is wasted by quitting.
    """
    item = BY_ID.get(item_id)
    if item is None or item["kind"] != KIND_TREAT:
        return None
    inv = inventory(profile)
    if inv["treats"].get(item_id, 0) <= 0:
        return None
    effect = item["effect"]
    if has_effect(profile, effect):
        return None

    inv["treats"][item_id] -= 1
    if inv["treats"][item_id] <= 0:
        del inv["treats"][item_id]
    active_effects(profile)[effect] = True
    return effect


def take_effect(profile, effect):
    """
    Spend an armed effect. Modes call this at the exact moment they would
    otherwise penalise, so an unused treat is never quietly eaten.
    """
    if not has_effect(profile, effect):
        return False
    del active_effects(profile)[effect]
    return True


def armed(profile):
    """Effect names currently waiting to be used."""
    return sorted(k for k, v in active_effects(profile).items() if v)


# --- flavour ---------------------------------------------------------


def favourite_treat(seed):
    """
    Each cat prefers one treat. Derived from the cat's own seed via the
    same independent-stream trick genes use, so adding this didn't
    disturb any existing cat.
    """
    treats = sorted(i["id"] for i in CATALOG if i["kind"] == KIND_TREAT)
    rng = random.Random((int(seed) * 1000003) ^ zlib.crc32(b"favourite_treat"))
    return rng.choice(treats)


def favourite_toy(seed):
    toys = sorted(i["id"] for i in CATALOG if i["kind"] == KIND_TOY)
    rng = random.Random((int(seed) * 1000003) ^ zlib.crc32(b"favourite_toy"))
    return rng.choice(toys)
