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

from core import ui

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
        "  {L}_{R} {U}",
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
