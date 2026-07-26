"""
The cat: genetics, ASCII rendering, poses.

One integer seed in the profile derives the whole animal, so a cat costs
four bytes of save data and is reconstructable forever.

Every trait is LATERAL -- different, never better. Siblings share this
device and will absolutely compare cats, so there are no rarity tiers, no
"good" genes, and nothing here that ranks one cat above another.

Genes are drawn from independent streams keyed by gene name rather than
from one sequential walk. That means a later phase can add a gene (a
favorite treat, an accessory slot) without every existing cat changing
colour -- "same seed, same cat, forever" has to survive our own future
edits, not just re-runs.
"""

import random
import zlib
from datetime import date, datetime, timedelta

from core import adaptive, ui

# --- genes ----------------------------------------------------------

# Fur: `fill` paints the body interior, `paws` marks the feet in the
# accent colour. Two tabby variants (= and ~) count as one axis.
FUR = {
    "solid":   {"fill": " ", "paws": False},
    "tabby":   {"fill": "=", "paws": False},
    "stripes": {"fill": "~", "paws": False},
    "patches": {"fill": "%", "paws": False},
    "tuxedo":  {"fill": "v", "paws": True},
    "socks":   {"fill": " ", "paws": True},
}
FUR_NAMES = sorted(FUR)

EYES = ["o o", "O o", "- -", "^ ^"]

# What a kid actually reads. The gene keys stay put (saves and later
# phases key off them); these are just kinder words for the same trait --
# a cat a child loves isn't "lazy", it's sleepy.
PERSONALITY_WORDS = {
    "lazy": "sleepy",
    "chaotic": "mischievous",
    "hunter": "curious",
    "cuddly": "cuddly",
}
FUR_WORDS = {
    "solid": "smooth",
    "tabby": "tabby",
    "stripes": "stripy",
    "patches": "patchy",
    "tuxedo": "tuxedo",
    "socks": "white-socked",
}

# What the cat says while it's idling on the menu. Short, warm, and never
# a demand -- the needs callout is Phase 3's job, not the idle loop's.
POSE_LINES = {
    "sit": ["*blink*", "*purr*", "..."],
    "loaf": ["*loaf mode*", "*settles in*"],
    "sleep": ["zzz...", "*dreaming*"],
    "groom": ["*licks paw*", "*tidy*"],
    "pounce": ["*pounce!*", "*wiggles*"],
    "swat": ["*bats at it*", "*swat*"],
    "overjoyed": ["*happy!*", "*prrrp!*"],
    "wary": ["...", "*watching*"],
}
EARS = ["pointy", "round", "tufted"]
BUILDS = ["loaf", "lanky", "round"]
TAILS = ["curl", "straight", "puff"]
PERSONALITIES = ["lazy", "chaotic", "hunter", "cuddly"]

# A cat is a he or a she, drawn like any other gene. Lateral as
# everything else here: neither is rarer, neither unlocks anything, and
# nothing in the game behaves differently because of it. It exists so the
# cat can be talked about as somebody rather than as "it".
GENDERS = ["boy", "girl"]
PRONOUNS = {
    "boy": {"they": "he", "them": "him", "their": "his", "theirs": "his"},
    "girl": {"they": "she", "them": "her", "their": "her", "theirs": "hers"},
}

# Curated body/accent pairs from the 8-colour console space. Both members
# have to stay legible on a bare TERM=linux console, which is why black is
# absent and why no combo pairs two dark colours.
COLOR_COMBOS = [
    ("white", "yellow"),
    ("yellow", "white"),
    ("yellow", "red"),
    ("cyan", "blue"),
    ("cyan", "white"),
    ("magenta", "white"),
    ("magenta", "cyan"),
    ("green", "yellow"),
    ("white", "cyan"),
    ("white", "magenta"),
]

# Idle pose weights per personality. The cat's temperament is the thing
# the kid reads first, long before they notice fur or eye colour.
IDLE_WEIGHTS = {
    "lazy":    {"sleep": 40, "loaf": 35, "sit": 20, "groom": 5},
    "chaotic": {"pounce": 35, "swat": 20, "sit": 20, "groom": 15, "loaf": 10},
    "hunter":  {"pounce": 30, "sit": 35, "groom": 15, "loaf": 15, "sleep": 5},
    "cuddly":  {"sit": 35, "loaf": 30, "groom": 20, "sleep": 15},
}


# --- care gauges ----------------------------------------------------
#
# Nothing about a gauge is stored. `profile["cat"]["care"]` holds one
# timestamp per task and every level is derived from it, which means
# there is no gauge state to migrate, corrupt, or quietly drain while
# the game isn't running.
#
# THE INVARIANT (DESIGN 3.3): the floor of a gauge is "wants", never
# "harmed". An empty gauge changes what the cat does on screen and
# nothing else -- no damage, no debuff, no lost progress, ever.

CARE_TASKS = ("food", "water", "pets", "play", "clean")

CARE_LABELS = {
    "food": "Food", "water": "Water", "pets": "Pets",
    "play": "Play", "clean": "Clean",
}
# How the cat asks for each one, for the startup callout.
CARE_NEEDS = {
    "food": "food",
    "water": "fresh water",
    "pets": "a cuddle",
    "play": "playtime",
    "clean": "a clean litter box",
}
CARE_BLURBS = {
    "food": "go fishing for words",
    "water": "fill the bowl, no spills",
    "pets": "purr rhythm",
    "play": "your pick of any game",
    "clean": "scoop the litter box",
}

GAUGE_FULL_HOURS = 12.0    # stays full this long after the task is done
GAUGE_EMPTY_HOURS = 36.0   # ...then drifts to empty by here
WARY_DAYS = 3              # untouched this long and the cat goes wary (Phase 5)


def _parse_when(text):
    """
    Parse a stored care stamp. Accepts a full timestamp or a bare date
    (older saves, or a parent hand-editing the JSON), and shrugs off
    anything it can't read rather than taking the game down.
    """
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        pass
    try:
        return datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
    except (ValueError, TypeError):
        return None


def hours_since_care(profile, task, now=None):
    """Hours since `task` was last done, or None if it never has been."""
    when = _parse_when(((profile.get("cat") or {}).get("care") or {}).get(task))
    if when is None:
        return None
    now = now or datetime.now()
    # The Pi has no network time and may have no RTC battery. A clock that
    # jumped backwards must not make the cat look neglected, so negative
    # deltas read as "just done".
    return max(0.0, (now - when).total_seconds() / 3600.0)


def gauge(profile, task, now=None):
    """This gauge's level, 0.0 (wants attention) to 1.0 (looked after)."""
    hours = hours_since_care(profile, task, now)
    if hours is None:
        return 0.0
    if hours <= GAUGE_FULL_HOURS:
        return 1.0
    span = GAUGE_EMPTY_HOURS - GAUGE_FULL_HOURS
    return max(0.0, 1.0 - (hours - GAUGE_FULL_HOURS) / span)


def gauges(profile, now=None):
    return {t: gauge(profile, t, now) for t in CARE_TASKS}


def hours_for_level(level):
    """Inverse of `gauge`: how long ago a task must have been done to sit here."""
    level = max(0.0, min(1.0, level))
    return GAUGE_FULL_HOURS + (1.0 - level) * (GAUGE_EMPTY_HOURS - GAUGE_FULL_HOURS)


def needs(profile, now=None):
    """Tasks that aren't full -- what the cat asks for on startup."""
    return [t for t in CARE_TASKS if gauge(profile, t, now) < 1.0]


def done_today(profile, task, today=None):
    stamp = ((profile.get("cat") or {}).get("care") or {}).get(task)
    when = _parse_when(stamp)
    if when is None:
        return False
    return when.date() == (today or date.today())


def care_done_today(profile, today=None):
    """All five looked after today -- what opens free play."""
    return all(done_today(profile, t, today) for t in CARE_TASKS)


def tasks_left_today(profile, today=None):
    return [t for t in CARE_TASKS if not done_today(profile, t, today)]


def stamp_care(profile, task, now=None):
    """Record that a care task just happened."""
    data = profile.setdefault("cat", {})
    care = data.setdefault("care", {})
    care[task] = (now or datetime.now()).isoformat(timespec="seconds")
    return care[task]


def hours_since_anything(profile, now=None):
    """
    Time since the cat last had any attention at all. Falls back to the
    hatch date so a kitten that was born five minutes ago doesn't read as
    abandoned. None means we genuinely can't tell.
    """
    now = now or datetime.now()
    seen = None
    for task in CARE_TASKS:
        hours = hours_since_care(profile, task, now)
        if hours is not None:
            seen = hours if seen is None else min(seen, hours)
    if seen is not None:
        return seen
    # Falls back to the latest of "hatched" and "woke". A cat just out of
    # stasis has no fresh care stamps, and reading its hatch date would
    # call it neglected for time it spent frozen. Same lesson as Phase 3:
    # an absence of timestamps is not evidence of absence.
    data = profile.get("cat") or {}
    marks = [_parse_when(data.get("hatched")), _parse_when(data.get("woke"))]
    marks = [m for m in marks if m is not None]
    hatched = max(marks) if marks else None
    if hatched is None:
        return None
    return max(0.0, (now - hatched).total_seconds() / 3600.0)


def is_wary(profile, now=None):
    """
    Nobody has been by in days. Drives the win-it-back beat, which never
    costs the kid anything either way.
    """
    hours = hours_since_anything(profile, now)
    return hours is not None and hours >= WARY_DAYS * 24


def set_wary(profile, value=True):
    """
    Latch the wary state at login. Latched rather than recomputed so that
    doing one care task mid-session doesn't make the cat flip back and
    forth -- it warms up over the session, which is the point.
    """
    profile.setdefault("cat", {})["wary"] = bool(value)


def wary_active(profile):
    return bool((profile.get("cat") or {}).get("wary"))


def wary_won_today(profile, today=None):
    when = _parse_when((profile.get("cat") or {}).get("wary_cleared"))
    return when is not None and when.date() == (today or date.today())


def needs_win_back(profile, today=None):
    """The beat runs once a day at most, however wary the cat is."""
    return wary_active(profile) and not wary_won_today(profile, today)


def mark_wary_won(profile, now=None):
    profile.setdefault("cat", {})["wary_cleared"] = (
        now or datetime.now()).isoformat(timespec="seconds")


def clear_wary(profile):
    """A full day of care and the cat is simply itself again."""
    data = profile.setdefault("cat", {})
    data["wary"] = False
    data.pop("wary_cleared", None)


# Moods, warmest first. The bottom of the range is a cat that misses you
# and is asleep -- there is deliberately nothing below it.
MOODS = ("thriving", "content", "hopeful", "missing")
MOOD_POSES = {
    "thriving": "overjoyed",
    "content": "loaf",
    "hopeful": "sit",
    "missing": "sleep",
}
MOOD_WORDS = {
    "thriving": "delighted",
    "content": "comfy",
    "hopeful": "hoping for some attention",
    "missing": "curled up, missing you",
}


def mood(profile, now=None):
    levels = list(gauges(profile, now).values())
    if not levels:
        return "missing"
    average = sum(levels) / len(levels)
    if average >= 0.999:
        return "thriving"
    if average >= 0.5:
        return "content"
    if average > 0.0:
        return "hopeful"
    # Empty gauges alone aren't sadness: a cat that has only just hatched
    # is hopeful, not missing anybody. Only real absence reads as absence.
    return "missing" if is_wary(profile, now) else "hopeful"


def mood_pose(name):
    return MOOD_POSES.get(name, "sit")


def gauge_bar(level, width=10):
    filled = int(round(max(0.0, min(1.0, level)) * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


# --- tricks ---------------------------------------------------------
#
# One trick per letter of the alphabet, assigned by unlock order, so a
# given letter always earns the same trick. This is the research's
# "perceived competence" lever wearing a cat suit: the kid sees the skill
# they just gained, named and kept.

TRICKS = [
    "pounce", "spin", "high-five", "backflip", "box-sit", "slow-blink",
    "zoomies", "paw-shake", "chirp", "biscuits", "sploot", "periscope",
    "shoulder-perch", "tail-flick", "fetch", "roll-over", "wave",
    "head-boop", "loaf-flip", "chatter", "moonwalk", "string-bat",
    "catnap-flop", "knead", "leap", "purr-song",
]


def trick_for_letter(letter):
    """Stable mapping: R always earns the same trick, forever."""
    idx = adaptive.FREQ_ORDER.find(letter)
    if idx < 0:
        return None
    return TRICKS[idx % len(TRICKS)]


def learn_trick(profile, letter):
    """
    Teach the cat the trick for `letter`. Returns its name if it's new,
    None if the cat already knew it -- tricks are additive and permanent.
    """
    name = trick_for_letter(letter)
    if not name:
        return None
    tricks = profile.setdefault("cat", {}).setdefault("tricks", [])
    if name in tricks:
        return None
    tricks.append(name)
    return name


def _gene(seed, key, options):
    """
    One trait, drawn from its own stream so gene order never matters.

    zlib.crc32 rather than hash(): Python randomises string hashing per
    process, which would give a kid a different cat on every launch.
    """
    rng = random.Random((seed * 1000003) ^ zlib.crc32(key.encode("ascii")))
    return rng.choice(options)


# --- art ------------------------------------------------------------
#
# Poses are templates with single-letter slots, expanded by `_expand`,
# which tracks which output columns came from which gene so the accent
# colour lands on exactly the right characters:
#
#   {L}{R}  ears      {E}  eyes        {f}  one fur-fill char
#   {p}  a paw        {T}  tail lying behind   {U}  tail held up
#
# Adults are 5 rows and stay inside 11 columns; kittens get their own
# smaller 4-row art. Both fit the menu corner at 80x24.

EAR_CHARS = {
    "pointy": ("/\\", "/\\"),
    "round":  ("(\\", "/)"),
    "tufted": ("//", "\\\\"),
}

# Ears half-back: the wary cat's whole tell, and an honest one -- this is
# exactly what a real cat does when it isn't sure about you yet.
EAR_BACK = {
    "pointy": ("\\/", "\\/"),
    "round":  ("(_", "_)"),
    "tufted": ("\\\\", "//"),
}

# A tail lying behind the cat, and the same tail held up when it's happy.
TAIL_LIE = {"curl": "_)", "straight": "__", "puff": "_*"}
TAIL_TIP = {"curl": ")", "straight": "|", "puff": "*"}

# The cat, adapted from the front-facing sitting cat on asciiart.eu.
# Roughly twice the size of the first version, which was ten columns of
# squint. Credit where it's due: the ASCII cat tradition these are drawn
# from is the work of hobbyist artists over decades, and the sitting-cat
# form here follows one of theirs.
#
# The gene slots survive the redraw, which is the point -- the eyes are a
# three-character slot, the chest is the fur fill, the feet are the paws
# and the sweep off the shoulder is the tail. Every kid still gets their
# own cat.
#
# Head geometry: {L} + 7 fixed + {R} = 11 wide from column 5, so the ear
# tips on the row above sit at columns 5 and 15. Keep that if you edit.

# One cat, one size. A larger front-facing portrait was tried and looked
# worse, not bigger: at this character density the head dominates and the
# body reads as a smudge under it. The compact cat is legible, and
# legible beats large.

ADULT = {
    "sit": [
        "  {L}_{R}",
        " ( {E} )",
        "  > ^ <",
        " /{f}{f}{f}\\",
        " {p} {p}{T}",
    ],
    "loaf": [
        "",
        "  {L}_{R}",
        " ( {E} )",
        "({f}{f}{f}{f}{f})",
        " \\_____/{T}",
    ],
    "sleep": [
        "       z",
        "  {L}_{R}",
        " ( - - )",
        "({f}{f}{f}{f}{f})",
        " \\_____/{T}",
    ],
    "groom": [
        "  {L}_{R}",
        " ( {E} ),",
        "  > ^ <'",
        " /{f}{f}{f}\\",
        " {p} {p}{T}",
    ],
    "pounce": [
        "  {L}_{R}",
        " ( O O )",
        " <  ^  >",
        "/{f}{f}{f}{f}{f}\\",
        " '     '{T}",
    ],
    "swat": [
        "  {L}_{R}",
        " ( - - )",
        "  > ^ <-,",
        " /{f}{f}{f}\\",
        " {p} {p}{T}",
    ],
    "overjoyed": [
        "  {L}_{R}  {U}",
        " ( ^ ^ ) |",
        "  > w <  |",
        " /{f}{f}{f}\\",
        " {p} {p}",
    ],
    "wary": [
        "  {l}_{r}",
        " ( - - )",
        "  - ^ -",
        " /{f}{f}{f}\\",
        " {p} {p}{T}",
    ],
}

KITTEN = {
    "sit": [
        " {L}_{R}",
        "( {E} )",
        " /{f}\\",
        " {p}{p}{T}",
    ],
    "loaf": [
        "",
        " {L}_{R}",
        "( {E} )",
        " \\{f}{f}{f}/{T}",
    ],
    "sleep": [
        "     z",
        " {L}_{R}",
        "( - - )",
        " \\{f}{f}{f}/{T}",
    ],
    "groom": [
        " {L}_{R}",
        "( {E} ),",
        " /{f}\\",
        " {p}{p}{T}",
    ],
    "pounce": [
        " {L}_{R}",
        "( O O )",
        "<  ^  >",
        " '   '{T}",
    ],
    "swat": [
        " {L}_{R}",
        "( - - )",
        " /{f}\\-,",
        " {p}{p}{T}",
    ],
    "overjoyed": [
        " {L}_{R} {U}",
        "( ^ ^ )|",
        " /{f}\\  |",
        " {p}{p}",
    ],
    "wary": [
        " {l}_{r}",
        "( - - )",
        " /{f}\\",
        " {p}{p}{T}",
    ],
}

POSES = sorted(ADULT)

# Which row each pose's face sits on, per art set. Sixteen entries: this
# is the accessory slot the issue asks for, kept as a table rather than
# threaded through sixteen hand-aligned ASCII templates. Editing the
# templates risks shifting art that is currently correct and can only be
# checked by eye; a table can be asserted against the rendered result,
# which is what tests/test_accessories.py does for all sixteen.
FACE_ROW = {
    "kitten": {"sit": 1, "loaf": 2, "sleep": 2, "groom": 1,
               "pounce": 1, "swat": 1, "overjoyed": 1, "wary": 1},
    "adult": {"sit": 1, "loaf": 2, "sleep": 2, "groom": 1,
              "pounce": 1, "swat": 1, "overjoyed": 1, "wary": 1},
}

# Accessories (DESIGN 5.3, deferred from Phase 5 to #22).
#
# Rendered as an inserted row rather than painted into the body, because
# the body is where the fur gene lives -- there is no column that is
# reliably blank across six fur patterns and sixteen pose/growth
# combinations. An extra row is uniform, never damages the art, and a cat
# with nothing on is byte-identical to one from before accessories
# existed.
#
# All lateral. Different, never better: no tiers, no rarity, and the
# prices sit close together so no one item reads as the good one.
ACCESSORIES = {
    "red_collar": {"art": "-o-", "slot": "neck", "word": "a red collar"},
    "blue_bandana": {"art": "\\_/", "slot": "neck", "word": "a blue bandana"},
    "bow_tie": {"art": ">o<", "slot": "neck", "word": "a bow tie"},
    "sun_hat": {"art": "[_]", "slot": "head", "word": "a sun hat"},
    "daisy": {"art": ",*,", "slot": "head", "word": "a daisy behind the ear"},

    # Earned by accumulation rather than bought (#29). They need art here
    # like any other accessory: an item that lands in the inventory but
    # has no entry in this table is silently unwearable, which is the
    # worst possible outcome for something a kid spent a year earning.
    "milestone_ribbon": {"art": "-8-", "slot": "neck", "word": "a paper ribbon"},
    "golden_collar": {"art": "=o=", "slot": "neck", "word": "a golden collar"},
    "silver_bell": {"art": "-Q-", "slot": "neck", "word": "a silver bell"},
    "comet_charm": {"art": "~*~", "slot": "neck", "word": "a comet charm"},
    "milestone_tag": {"art": "[i]", "slot": "neck", "word": "a name tag"},
    "first_key_charm": {"art": "-+-", "slot": "neck", "word": "a key charm"},
    "half_alphabet_pin": {"art": "-:-", "slot": "neck", "word": "a half pin"},
    "star_charm": {"art": "-*-", "slot": "neck", "word": "a star charm"},
    "album_clip": {"art": "-#-", "slot": "neck", "word": "an album clip"},
}
ACCESSORY_IDS = sorted(ACCESSORIES)

# Slow-reveal markings (DESIGN 3.2). Withheld at first and expressed as
# the cat matures, so the randomisation gets a second act months in.
MARKS = ["*", "o", ".", "'"]

# The secret. Never hinted at anywhere in the UI -- discovery is meant to
# travel by sibling word of mouth, which it can't do if the game tells
# you. Derived, never stored, so it can't be edited into a save.
STAR = "*"


def _face_row(pose, kitten):
    table = FACE_ROW["kitten" if kitten else "adult"]
    return table.get(pose, table["sit"])


# `worn` has three states, and the difference between two of them is the
# whole reason this isn't a one-liner:
#   None  -- never chosen; fall back to whatever was bought last
#   ""    -- taken off on purpose; the cat wears nothing
#   <id>  -- deliberately chosen
# Collapsing the first two would mean a kid who takes the collar off gets
# it put straight back on by the fallback.
BARE = ""


def worn_accessory(profile):
    """
    The accessory this cat has on, or None.

    Buying something puts it on without a second step, because a
    seven-year-old reads "I bought a hat and nothing happened" as the
    purchase having failed. A deliberate choice always wins over that,
    including the deliberate choice of nothing at all.
    """
    inv = ((profile or {}).get("inventory") or {})
    worn = inv.get("worn")
    if worn == BARE and worn is not None:
        return None
    if worn in ACCESSORIES:
        return worn
    owned = [i for i in (inv.get("accessories") or []) if i in ACCESSORIES]
    return owned[-1] if owned else None


def wear(profile, item_id):
    """Put one on, or take everything off with None."""
    inv = (profile or {}).setdefault("inventory", {})
    if item_id is None:
        inv["worn"] = BARE
        return True
    if item_id not in ACCESSORIES:
        return False
    if item_id not in (inv.get("accessories") or []):
        return False
    inv["worn"] = item_id
    return True


def secret_expressed(profile):
    """
    The hidden reveal: every letter unlocked AND every one mastered.

    Derived, never stored -- there is nothing in a save file to find, and
    nothing to edit yourself into. Deliberately unmentioned anywhere in
    the UI until it happens; the discovery is supposed to travel between
    siblings, which it can't do if the game announces it in advance.
    """
    profile = profile or {}
    letters = adaptive.alphabet(profile)
    if len(letters) < 26:
        return False
    keys = profile.get("keys") or {}
    return all(adaptive.is_green(keys.get(ch) or {}) for ch in letters)


def secret_unseen(profile):
    """True when the secret has expressed but its ceremony hasn't run."""
    data = (profile or {}).get("cat") or {}
    if "seed" not in data:
        return False
    return secret_expressed(profile) and not data.get("secret_seen")


def mark_secret_seen(profile):
    data = (profile or {}).get("cat") or {}
    if "seed" in data:
        data["secret_seen"] = True


# --- growth (DESIGN 3.2, issue #22) ---------------------------------
#
# A cat grows on time-plus-care, never on performance. Both thresholds
# have to be met: days shown up, and letters learned. That pairing is
# deliberate -- days alone would reward leaving the Pi switched on, and
# letters alone would turn growth into a score. Neither is something a
# kid can grind in an afternoon, which is the point: this is the layer
# that pays out in months.
#
# Nothing here is a new counter. `days_played` and the unlocked alphabet
# already exist and are already earned honestly.

GROWTH_STAGES = ["kitten", "young", "adult", "elder"]

# Kid-facing words. "elder" is never shown -- a cat that reads as old
# reads as a cat that will die, and nothing in this game ever does.
GROWTH_WORDS = {
    "kitten": "kitten",
    "young": "young cat",
    "adult": "grown-up cat",
    "elder": "great fluffy cat",
}

# Index by stage: what it takes to reach it. Stage 0 is free.
GROWTH_DAYS = [0, 10, 30, 75]
GROWTH_LETTERS = [0, 12, 20, 26]


def growth(profile):
    """The stage actually recorded on this cat."""
    return int(((profile or {}).get("cat") or {}).get("growth", 0) or 0)


def earned_growth(profile):
    """
    The stage this kid's history has earned, derived from data that
    already exists. Stops at the first unmet threshold, so the stages
    always arrive in order.
    """
    # The LIVE cat's own days, not the profile's. A shelved cat must not
    # grow up while it is frozen (#33). Identical on a one-cat profile.
    from core import stasis
    days = stasis.days_active(profile or {})
    letters = len(adaptive.alphabet(profile or {}))
    stage = 0
    for s in range(1, len(GROWTH_STAGES)):
        if days >= GROWTH_DAYS[s] and letters >= GROWTH_LETTERS[s]:
            stage = s
        else:
            break
    return stage


def advance_growth(profile):
    """
    Move the cat up if it has earned it. Returns the new stage, or None.

    Written immediately and never regressed, so an interrupted ceremony
    can't cost a kid a stage they earned. Whether the ceremony has been
    *seen* is tracked separately -- see `growth_unseen`.
    """
    data = (profile or {}).get("cat") or {}
    if "seed" not in data:
        return None
    have = growth(profile)
    earned = earned_growth(profile)
    if earned <= have:
        return None
    data["growth"] = earned
    return earned


def growth_unseen(profile):
    """
    The stage whose ceremony is still owed, or None.

    Quitting mid-ceremony leaves this set, so the reveal comes back next
    time rather than being silently spent.
    """
    data = (profile or {}).get("cat") or {}
    if "seed" not in data:
        return None
    have = growth(profile)
    seen = int(data.get("growth_seen", 0) or 0)
    return have if have > seen else None


def mark_growth_seen(profile, stage):
    data = (profile or {}).get("cat") or {}
    if "seed" in data:
        data["growth_seen"] = max(int(data.get("growth_seen", 0) or 0),
                                  int(stage))


def growth_progress(profile):
    """
    (days, days_needed, letters, letters_needed) for the next stage, or
    None at full growth. Used by the stats screen -- growth is meant to be
    something you can look forward to, not something that just happens.
    """
    have = growth(profile)
    nxt = have + 1
    if nxt >= len(GROWTH_STAGES):
        return None
    from core import stasis
    return (stasis.days_active(profile or {}), GROWTH_DAYS[nxt],
            len(adaptive.alphabet(profile or {})), GROWTH_LETTERS[nxt])

# Ear shapes for the one-line profile glyph -- all three have to differ at
# a glance, since the picker may be the only place a sibling sees the cat.
GLYPH_EARS = {"pointy": ("/", "\\"), "round": ("(", ")"), "tufted": ("<", ">")}


def _expand(row, subs, track=None):
    """
    Expand one template row.

    Returns (text, accent_columns, tracked), where `tracked` maps each
    placeholder letter named in `track` to the columns it produced. The
    marking reveal needs to know which columns are fur rather than
    outline, and it can't tell by looking: a "solid" cat's fill is a
    space, which is indistinguishable from the blank around the body.
    """
    out = []
    accents = set()
    tracked = {k: [] for k in (track or ())}
    i = 0
    while i < len(row):
        if row[i] == "{" and i + 2 < len(row) and row[i + 2] == "}":
            key = row[i + 1]
            text, hot = subs.get(key, (row[i:i + 3], False))
            for ch in text:
                if hot:
                    accents.add(len(out))
                if key in tracked:
                    tracked[key].append(len(out))
                out.append(ch)
            i += 3
        else:
            out.append(row[i])
            i += 1
    return "".join(out), accents, tracked


class Cat:
    """A rendered cat. Cheap to build -- make one per screen, not per frame."""

    def __init__(self, seed, name=None, growth=0, accessory=None,
                 secret=False, parent=None):
        self.seed = int(seed)
        self.name = name or "your cat"
        self.growth = growth
        self.accessory = accessory if accessory in ACCESSORIES else None
        self.secret = bool(secret)
        self.parent = None if parent is None else int(parent)

        # Family resemblance (#32). Colour and coat come from the parent
        # when there is one, everything else from the kitten's own seed:
        # colour reads as "these two are related", while temperament and
        # shape read as "this is a different cat". A kitten that inherited
        # everything would just be a copy with a new name.
        family = self.seed if self.parent is None else self.parent
        self.fur = _gene(family, "fur", FUR_NAMES)
        self.colors = _gene(family, "colors", COLOR_COMBOS)

        self.eyes = _gene(self.seed, "eyes", EYES)
        self.ears = _gene(self.seed, "ears", EARS)
        self.build = _gene(self.seed, "build", BUILDS)
        self.tail = _gene(self.seed, "tail", TAILS)
        self.personality = _gene(self.seed, "personality", PERSONALITIES)
        # Own stream, per the Phase 2 convention -- adding this gene must
        # not change a single existing cat's appearance.
        self.gender = _gene(self.seed, "gender", GENDERS)
        # Own stream, per the Phase 2 convention -- adding this gene must
        # not repaint a single existing cat.
        self.marks = _gene(self.seed, "marks", MARKS)

    # -- classmethods ------------------------------------------------

    @classmethod
    def from_profile(cls, profile):
        """The profile's cat, or None if this kid hasn't hatched one yet."""
        data = (profile or {}).get("cat") or {}
        if "seed" not in data:
            return None
        return cls(data["seed"], data.get("name"), data.get("growth", 0),
                   accessory=worn_accessory(profile),
                   secret=secret_expressed(profile),
                   parent=data.get("parent"))

    # -- appearance --------------------------------------------------

    @property
    def body_attr(self):
        return ui.cat_color(self.colors[0], bold=True)

    @property
    def accent_attr(self):
        return ui.cat_color(self.colors[1], bold=True)

    def is_kitten(self, growth=None):
        g = self.growth if growth is None else growth
        return g <= 1

    def _template(self, pose, growth=None):
        table = KITTEN if self.is_kitten(growth) else ADULT
        return table.get(pose) or table["sit"]

    def _render(self, pose, growth=None):
        """The pose as [(text, accent_columns), ...] with genes filled in."""
        left, right = EAR_CHARS[self.ears]
        back_l, back_r = EAR_BACK[self.ears]
        fur = FUR[self.fur]
        fill = fur["fill"]
        subs = {
            "L": (left, False),
            "R": (right, False),
            "l": (back_l, False),
            "r": (back_r, False),
            "E": (self.eyes, False),
            "f": (fill, fill != " "),
            "p": ("(_)", fur["paws"]),
            "T": (TAIL_LIE[self.tail], True),
            "U": (TAIL_TIP[self.tail], True),
        }

        stage = self.growth if growth is None else growth
        rows = []
        for row in self._template(pose, growth):
            text, accents, tracked = _expand(row, subs, track="f")
            text, accents = self._reveal(text, accents, tracked["f"], stage)
            rows.append((text, accents))

        return self._wear(rows, pose, growth)

    def _reveal(self, text, accents, fill_cols, stage):
        """
        Slow-reveal markings, and the secret beyond them.

        Additive and gated on growth, so a kitten looks exactly as it
        always did -- "same seed, same cat, forever" has to survive this
        feature too. Markings appear as the cat matures: one at the adult
        stage, the whole flank at elder.
        """
        if not fill_cols or stage < 2:
            return text, accents

        chars = list(text)
        hot = set(accents)
        glyph = STAR if self.secret else self.marks
        # Adult shows a single mark; elder shows the full pattern. The
        # secret, when it's expressed, takes over every one of them.
        chosen = fill_cols if (stage >= 3 or self.secret) else \
            fill_cols[len(fill_cols) // 2:len(fill_cols) // 2 + 1]
        for col in chosen:
            chars[col] = glyph
            hot.add(col)
        return "".join(chars), hot

    def _wear(self, rows, pose, growth=None):
        """
        Insert the accessory row, if anything is being worn.

        A row rather than a painted-on character: the body columns belong
        to the fur gene, and across six fur patterns and sixteen
        pose/growth combinations there is no column that is reliably
        blank. Inserting is uniform and cannot damage the art -- with
        nothing worn, this returns `rows` untouched.
        """
        if not self.accessory:
            return rows
        item = ACCESSORIES[self.accessory]
        face = _face_row(pose, self.is_kitten(growth))
        face = max(0, min(face, len(rows) - 1))

        # Centre it on the face, which is the one landmark every pose has.
        face_text = rows[face][0]
        open_at = face_text.find("(")
        close_at = face_text.rfind(")")
        art = item["art"]
        if open_at >= 0 and close_at > open_at:
            centre = (open_at + close_at) // 2
        else:
            centre = len(face_text) // 2
        col = max(0, centre - len(art) // 2)

        line = " " * col + art
        accents = set(range(col, col + len(art)))
        # Neck sits under the face; head goes above the *ears*, which are
        # the row before the face -- a hat between the ears and the eyes
        # reads as a hat being worn on the nose.
        at = face + 1 if item["slot"] == "neck" else max(0, face - 1)
        return rows[:at] + [(line, accents)] + rows[at:]

    def art(self, pose="sit", growth=None):
        """Plain text rows -- handy for ui.message art and for tests."""
        return [text for text, _ in self._render(pose, growth)]

    def width(self, pose="sit", growth=None):
        return max((len(r) for r in self.art(pose, growth)), default=0)

    def height(self, pose="sit", growth=None):
        return len(self.art(pose, growth))

    def draw(self, win, y, x, pose="sit", growth=None):
        """
        Paint the cat at (y, x). Body in the body colour, fur markings,
        tail and (for socks/tuxedo) paws in the accent -- two colours is
        all a bare console reliably gives us, and it's enough to make
        every cat look like somebody's.
        """
        body, accent = self.body_attr, self.accent_attr
        for i, (row, accents) in enumerate(self._render(pose, growth)):
            ui.safe_addstr(win, y + i, x, row, body)
            for j in sorted(accents):
                ui.safe_addstr(win, y + i, x + j, row[j], accent)

    def glyph(self):
        """
        The one-line face used as a profile icon. Ears and eyes vary it by
        shape so it still reads on a mono terminal; colour does the rest.
        """
        left, right = GLYPH_EARS[self.ears]
        return "%s%s%s" % (left, self.eyes.replace(" ", "."), right)

    # -- behaviour ---------------------------------------------------

    def next_idle(self, rng=None):
        """A pose to drift into, weighted by personality."""
        rng = rng or random
        weights = IDLE_WEIGHTS[self.personality]
        names = sorted(weights)
        total = sum(weights[n] for n in names)
        r = rng.uniform(0, total)
        for n in names:
            r -= weights[n]
            if r <= 0:
                return n
        return names[-1]

    @property
    def favourite_treat(self):
        from core import shop   # deferred: shop is a consumer of cats
        return shop.favourite_treat(self.seed)

    @property
    def favourite_toy(self):
        from core import shop
        return shop.favourite_toy(self.seed)

    def says(self, pose, rng=None):
        """A short idle line for the speech bubble."""
        rng = rng or random
        return rng.choice(POSE_LINES.get(pose) or POSE_LINES["sit"])

    # -- pronouns ----------------------------------------------------

    @property
    def they(self):
        return PRONOUNS[self.gender]["they"]

    @property
    def them(self):
        return PRONOUNS[self.gender]["them"]

    @property
    def their(self):
        return PRONOUNS[self.gender]["their"]

    @property
    def theirs(self):
        return PRONOUNS[self.gender]["theirs"]

    def They(self):
        return self.they.capitalize()

    def Their(self):
        return self.their.capitalize()

    def describe(self, subject=None):
        """One line a kid can read."""
        return "%s is a %s %s cat." % (
            subject or self.name,
            PERSONALITY_WORDS[self.personality],
            FUR_WORDS[self.fur],
        )

    def describe_full(self):
        """The hatch reveal: what they are, and who they are."""
        return "%s is a %s %s %s." % (
            self.They(),
            PERSONALITY_WORDS[self.personality],
            FUR_WORDS[self.fur],
            "tomcat" if self.gender == "boy" else "she-cat",
        )


def panel(kitty, pose="sit", lines=None, min_width=0, width_hint=0,
          n_lines=None):
    """
    A framed-menu left column for a cat: `(width, height, draw)` for
    `ui.menu(panel=...)`, or None when there's no cat.

    Lives here so every screen gets the same column rather than each one
    inventing its own placement -- the care board used to pin the cat to
    the far right edge with its own status bars at column 8, which on a
    wide terminal put half a screen of nothing between them.

    `pose` and `lines` may both be callables, evaluated at DRAW time.
    That matters: the care board's gauges change as a kid works through
    the tasks, and a snapshot taken when the menu opened would show them
    yesterday's numbers.

    `lines` are extra rows drawn under the cat, each `(text, attr)`.
    """
    if kitty is None:
        return None
    art_w = max(kitty.width(p) for p in POSES)
    art_h = max(kitty.height(p) for p in POSES)
    # Never call `lines()` here just to count them -- it resolves colour
    # pairs, and a panel gets built outside curses in tests and tools.
    # A callable must declare how many rows it will draw.
    if n_lines is None:
        n_lines = 0 if callable(lines) else len(lines or [])
    width = max(min_width, art_w, width_hint or 0)
    height = art_h + (1 + n_lines if n_lines else 0)

    def draw(win, top, left):
        shown = pose() if callable(pose) else pose
        kitty.draw(win, top, left + max(0, (width - kitty.width(shown)) // 2),
                   shown)
        rows = lines() if callable(lines) else (lines or [])
        row = top + art_h + 1
        for text, attr in rows:
            ui.safe_addstr(win, row, left, text, attr)
            row += 1

    return width, height, draw


def new_seed(rng=None):
    rng = rng or random
    return rng.randrange(1, 1000000)


# A kitten arrives already looked after. Hatching is a delighted moment,
# and five empty bars underneath it would read as "you're already behind"
# thirty seconds into owning a cat. It starts fed and watered, wanting a
# cuddle and a game -- which is also a nudge toward the two warmest tasks.
HATCH_GAUGES = {
    "food": 0.7, "water": 0.7, "clean": 0.6, "pets": 0.4, "play": 0.3,
}


def _hatch_care(now):
    """
    Backdated care stamps giving a new kitten the levels above.

    Every stamp is dated before today, so the day's five tasks are still
    the day's five tasks: this changes how the cat *looks*, never what
    the kid does. Expressing the starting state as ordinary care history
    also means nothing else needs a special case for a new cat.
    """
    yesterday_end = (datetime.combine(now.date(), datetime.min.time())
                     - timedelta(seconds=1))
    care = {}
    for task, level in HATCH_GAUGES.items():
        when = now - timedelta(hours=hours_for_level(level))
        care[task] = min(when, yesterday_end).isoformat(timespec="seconds")
    return care


def blank_cat_data(seed, name, today, growth=0, now=None, parent=None):
    """The `cat` block as it lands in the profile (DESIGN 9.3)."""
    data = {
        "seed": seed,
        "name": name,
        "hatched": today,
        "tricks": [],
        "growth": growth,
        "care": _hatch_care(now or datetime.now()),
        "wary": False,
        "days_active": 0,
    }
    if parent is not None:
        data["parent"] = int(parent)
    return data
