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
from datetime import date, datetime

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
}
EARS = ["pointy", "round", "tufted"]
BUILDS = ["loaf", "lanky", "round"]
TAILS = ["curl", "straight", "puff"]
PERSONALITIES = ["lazy", "chaotic", "hunter", "cuddly"]

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
    hatched = _parse_when((profile.get("cat") or {}).get("hatched"))
    if hatched is None:
        return None
    return max(0.0, (now - hatched).total_seconds() / 3600.0)


def is_wary(profile, now=None):
    """
    Nobody has been by in days. Phase 5 turns this into the win-it-back
    beat; it never costs the kid anything either way.
    """
    hours = hours_since_anything(profile, now)
    return hours is not None and hours >= WARY_DAYS * 24


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

# A tail lying behind the cat, and the same tail held up when it's happy.
TAIL_LIE = {"curl": "_)", "straight": "__", "puff": "_*"}
TAIL_TIP = {"curl": ")", "straight": "|", "puff": "*"}

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
}

POSES = sorted(ADULT)

# Ear shapes for the one-line profile glyph -- all three have to differ at
# a glance, since the picker may be the only place a sibling sees the cat.
GLYPH_EARS = {"pointy": ("/", "\\"), "round": ("(", ")"), "tufted": ("<", ">")}


def _expand(row, subs):
    """
    Expand one template row. Returns (text, accent_columns), where the
    accent columns are the ones the accent colour paints.
    """
    out = []
    accents = set()
    i = 0
    while i < len(row):
        if row[i] == "{" and i + 2 < len(row) and row[i + 2] == "}":
            text, hot = subs.get(row[i + 1], (row[i:i + 3], False))
            for ch in text:
                if hot:
                    accents.add(len(out))
                out.append(ch)
            i += 3
        else:
            out.append(row[i])
            i += 1
    return "".join(out), accents


class Cat:
    """A rendered cat. Cheap to build -- make one per screen, not per frame."""

    def __init__(self, seed, name=None, growth=0):
        self.seed = int(seed)
        self.name = name or "your cat"
        self.growth = growth

        self.fur = _gene(self.seed, "fur", FUR_NAMES)
        self.eyes = _gene(self.seed, "eyes", EYES)
        self.ears = _gene(self.seed, "ears", EARS)
        self.build = _gene(self.seed, "build", BUILDS)
        self.tail = _gene(self.seed, "tail", TAILS)
        self.personality = _gene(self.seed, "personality", PERSONALITIES)
        self.colors = _gene(self.seed, "colors", COLOR_COMBOS)

    # -- classmethods ------------------------------------------------

    @classmethod
    def from_profile(cls, profile):
        """The profile's cat, or None if this kid hasn't hatched one yet."""
        data = (profile or {}).get("cat") or {}
        if "seed" not in data:
            return None
        return cls(data["seed"], data.get("name"), data.get("growth", 0))

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
        fur = FUR[self.fur]
        fill = fur["fill"]
        subs = {
            "L": (left, False),
            "R": (right, False),
            "E": (self.eyes, False),
            "f": (fill, fill != " "),
            "p": ("(_)", fur["paws"]),
            "T": (TAIL_LIE[self.tail], True),
            "U": (TAIL_TIP[self.tail], True),
        }
        return [_expand(row, subs) for row in self._template(pose, growth)]

    def art(self, pose="sit", growth=None):
        """Plain text rows -- handy for ui.message art and for tests."""
        return [text for text, _ in self._render(pose, growth)]

    def width(self, pose="sit", growth=None):
        return max((len(r) for r in self.art(pose, growth)), default=0)

    def height(self, pose="sit", growth=None):
        return len(self._template(pose, growth))

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

    def says(self, pose, rng=None):
        """A short idle line for the speech bubble."""
        rng = rng or random
        return rng.choice(POSE_LINES.get(pose) or POSE_LINES["sit"])

    def describe(self, subject=None):
        """One line a kid can read."""
        return "%s is a %s %s cat." % (
            subject or self.name,
            PERSONALITY_WORDS[self.personality],
            FUR_WORDS[self.fur],
        )


def new_seed(rng=None):
    rng = rng or random
    return rng.randrange(1, 1000000)


def blank_cat_data(seed, name, today, growth=0):
    """The `cat` block as it lands in the profile (DESIGN 9.3)."""
    return {
        "seed": seed,
        "name": name,
        "hatched": today,
        "tricks": [],
        "growth": growth,
        "care": {},
        "wary": False,
    }
