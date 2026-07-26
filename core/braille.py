"""
Braille rendering -- the same cat, at eight times the resolution.

A braille character encodes 2x4 dots, so a cat drawn on a dot canvas and
emitted as braille has eight times the detail of the same cat drawn as
characters, in exactly the same number of columns.

WHY THIS ISN'T JUST TRACED ART
    Every traced cat we tried was one fixed picture, which would have
    given every kid on the device an identical animal -- the thing the
    whole lateral-variety design rests on not happening. So the art here
    is authored as a DOT BITMAP with named zones, and the genes fill the
    zones: eyes, coat, ears and tail are each a small dot pattern chosen
    by the same `_gene` streams the ASCII cat uses.

    Same cat, same seed, same kid. Just drawn finer.

AUTHORING
    Art is written as plain text, one character per dot, which keeps it
    editable by hand:

        '#'  a dot
        '.'  or space, no dot
        'E'  eye zone      'F'  coat zone
        'R'  ear zone      'T'  tail zone

    Zone characters are replaced by the gene's pattern before rendering,
    so a zone is just "dots to be decided later".

FALLBACK
    Two separate things have to hold, and only one of them is knowable.

    Whether curses counts a braille character as ONE column is knowable,
    so `wide_curses()` measures it -- by drawing one offscreen and
    reading the cursor back, rather than by asking how CPython was built.
    Those are different questions: the binding writes UTF-8 bytes, and a
    widec ncurses reassembles them on its own, so a terminal with no
    `get_wch` can still be perfectly capable. macOS is that terminal.

    Whether the console font HAS the glyphs is not knowable -- a console
    with nothing at U+2801 draws a blank and never says so. That half is
    declared: --braille, a kid's saved choice, or the flag install-pi.sh
    writes once it has installed a font.

    Every caller keeps an ASCII path either way. Cute where it works,
    never broken where it doesn't.
"""

import os

BLANK = "⠀"

# Braille dot bit for each (col, row) in the 2x4 cell. Bits 0-5 are the
# top three rows; 6-7 are the fourth, added later in Unicode's history,
# which is why the numbering looks arbitrary.
DOT_BITS = {
    (0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (0, 3): 0x40,
    (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (1, 3): 0x80,
}

CELL_W, CELL_H = 2, 4


class Canvas:
    """A dot grid that renders to braille rows."""

    def __init__(self, width, height):
        # width/height are in DOTS, not characters.
        self.w = max(1, width)
        self.h = max(1, height)
        self.dots = [[0] * self.w for _ in range(self.h)]

    def set(self, x, y, on=True):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.dots[y][x] = 1 if on else 0

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.dots[y][x]
        return 0

    def blit(self, lines, ox=0, oy=0):
        """Stamp a text bitmap ('#' is a dot) at (ox, oy)."""
        for dy, line in enumerate(lines):
            for dx, ch in enumerate(line):
                if ch == "#":
                    self.set(ox + dx, oy + dy)

    def rows(self):
        """The canvas as braille strings, one per 4 dot-rows."""
        out = []
        for cy in range(0, self.h, CELL_H):
            line = []
            for cx in range(0, self.w, CELL_W):
                code = 0
                for (dx, dy), bit in DOT_BITS.items():
                    if self.get(cx + dx, cy + dy):
                        code |= bit
                line.append(chr(0x2800 + code))
            out.append("".join(line).rstrip(BLANK))
        return out


def from_bitmap(lines):
    """Build a canvas from text art, padded to a whole number of cells."""
    lines = list(lines)
    w = max((len(l) for l in lines), default=1)
    h = len(lines)
    # Round up to full cells so the last row isn't clipped.
    canvas = Canvas(w + (-w % CELL_W), h + (-h % CELL_H))
    canvas.blit(lines)
    return canvas


def render(lines):
    """Text art -> braille rows, in one step."""
    return from_bitmap(lines).rows()


def _regions(grid, letter):
    """
    Every separate run of a zone letter, as its own list of cells.

    A cat has two eyes and two ears, and they're written with the same
    zone letter because they get the same gene. If they shared one
    bounding box the pattern would be stretched across the whole face
    with a nose in the middle of it, so each connected blob is found and
    filled on its own.
    """
    seen = set()
    out = []
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch != letter or (y, x) in seen:
                continue
            blob, stack = [], [(y, x)]
            seen.add((y, x))
            while stack:
                cy, cx = stack.pop()
                blob.append((cy, cx))
                # 8-way: diagonal neighbours count, or a pattern drawn on
                # a slant would come apart into single-cell regions.
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if (ny, nx) in seen:
                            continue
                        if 0 <= ny < len(grid) and 0 <= nx < len(grid[ny]) \
                                and grid[ny][nx] == letter:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            out.append(blob)
    return out


def fill_zones(lines, zones):
    """
    Replace zone letters with their gene's dot pattern.

    `zones` maps a zone letter to a small list of strings. The pattern
    TILES across each region, so a 1x1 "#" fills a tail solid and a 4x1
    "#.#." stripes a coat of any size -- a gene doesn't have to know how
    big the thing it's colouring is.
    """
    grid = [list(line) for line in lines]
    for letter, art in zones.items():
        art = [row for row in art if row] or ["."]
        for blob in _regions(grid, letter):
            top = min(y for y, _x in blob)
            left = min(x for _y, x in blob)
            for y, x in blob:
                row = art[(y - top) % len(art)]
                ch = row[(x - left) % len(row)]
                grid[y][x] = "#" if ch == "#" else "."
    return ["".join(row) for row in grid]


def zone_columns(lines, letters):
    """
    Which CHARACTER columns each zone lands in, per character row.

    Colour is applied per character cell, not per dot, so after the art
    is rendered there's no way to tell which cells came from the tail and
    which from the coat. This reads that off the authored art, before the
    zones are filled, and gives `draw` the same body/accent split the
    ASCII cat has.
    """
    out = {}
    for y, row in enumerate(lines):
        for x, ch in enumerate(row):
            if ch in letters:
                out.setdefault(y // CELL_H, set()).add(x // CELL_W)
    return out


# --- genes ------------------------------------------------------------
#
# The ASCII cat spends its genes on characters; the braille cat spends
# them on dot patterns. The gene VALUES are identical -- same names, same
# `_gene` streams -- so a kid's cat is the same animal either way, and
# switching the flag changes how it's drawn and nothing about who it is.

# On a solid head, an eye is an absence of ink. These are holes punched
# out of the skull, which is why the "open" eyes are mostly dots-off:
# drawing MORE dots where an eye goes just makes a darker forehead.
EYE_DOTS = {
    # Sized to the 6x4 eye zone. A pattern smaller than its zone TILES,
    # which turns an eye into stripes, so these are exact.
    "o o": ["......",                    # round, with a pupil
            "..##..",
            "..##..",
            "......"],
    "O o": ["......",                    # wide awake, all iris
            "......",
            "......",
            "......"],
    "- -": ["######",                    # a contented slit
            "......",
            "......",
            "######"],
    "^ ^": ["##..##",                    # happy, squeezed shut
            "#....#",
            "......",
            "######"],
}

EAR_DOTS = {
    "pointy": ["#"],                     # solid to the tip
    "round":  ["##", "#."],              # softened
    "tufted": ["#.", ".#"],              # broken up, so it reads as fluff
}

# Coat markings tile across the chest, so a pattern doesn't need to know
# how big the cat is -- a kitten and an elder use the same gene.
FUR_DOTS = {
    "solid":   ["."],
    "tabby":   ["#.#.", "...."],
    "stripes": ["##..", "##.."],
    "patches": ["##..", "..##"],
    "tuxedo":  ["#"],
    "socks":   ["....", "..#."],
}

TAIL_DOTS = {
    "curl":     ["#"],
    "straight": ["#"],
    "puff":     ["##", "#."],
}


def cat_rows(kitty, pose="sit", growth=None):
    """
    One pose of one cat, as `[(text, accent_columns), ...]`.

    The same shape `cat.Cat._render` returns, so a caller can paint this
    with the code it already has.
    """
    from core import braille_art

    kitten = kitty.is_kitten(growth)
    table = braille_art.KITTEN if kitten else braille_art.ADULT
    art = table.get(pose) or table["sit"]

    zones = {
        "E": EYE_DOTS.get(kitty.eyes, EYE_DOTS["o o"]),
        "R": EAR_DOTS.get(kitty.ears, EAR_DOTS["round"]),
        "F": FUR_DOTS.get(kitty.fur, FUR_DOTS["solid"]),
        "T": TAIL_DOTS.get(kitty.tail, TAIL_DOTS["curl"]),
    }
    # Tail and markings take the accent colour, matching the ASCII cat.
    accents = zone_columns(art, "TF")
    rows = render(fill_zones(art, zones))
    return [(text, accents.get(i, set())) for i, text in enumerate(rows)]


# --- can we actually use it? -----------------------------------------
#
# Nothing here probes the terminal, because there is no reliable way to
# ask a console "will you render U+2801?" -- it either has the glyph in
# its font or it draws a blank, and it won't tell you which.
#
# So this is a declared capability, not a detected one. install-pi.sh
# sets it when it has installed and merged a braille console font;
# everything else defaults to off and gets the ASCII cat.

ENV_FLAG = "TYPING_TUTOR_BRAILLE"


_WIDE = None


def _probe_wide():
    """
    Draw one braille character offscreen and see how far the cursor moved.

    One column means the stack handles it and the layout will be right.
    Three means each UTF-8 byte took a cell, so everything drawn to the
    right of the cat would land in the wrong place.

    Uses a pad, so nothing a child can see is touched.
    """
    import curses
    pad = curses.newpad(1, 8)
    pad.addstr(0, 0, "⠿")
    return pad.getyx()[1] == 1


def wide_curses():
    """
    True when curses counts a braille character as ONE column.

    This asks what the stack DOES, not how it was built, because those
    turn out to be different questions. `hasattr(curses, "get_wch")` only
    reports whether CPython was compiled with HAVE_NCURSESW -- but the
    binding writes UTF-8 bytes to `waddstr`, and a widec ncurses composes
    those bytes back into one character on its own. macOS is exactly that
    case: no `get_wch`, and braille still lays out perfectly. Trusting the
    build flag refused a terminal that works fine.

    The answer is cached: it cannot change within a run, and this is
    called for every row of every frame.
    """
    global _WIDE
    if _WIDE is not None:
        return _WIDE
    try:
        import curses
    except ImportError:
        return False
    try:
        _WIDE = _probe_wide()
        return _WIDE
    except Exception:                       # noqa: BLE001
        # curses isn't up yet (tests, tools, --check). Don't cache a
        # guess -- answer statically now and probe properly once the
        # screen exists.
        return _static_wide()


def _static_wide():
    """
    Best answer available before curses is running.

    Asks the loaded ncurses whether it has the wide entry points at all;
    a library exporting `wadd_wch` was built with --enable-widec and will
    compose UTF-8 in `waddstr`. Falls back to the build flag.
    """
    try:
        import ctypes
        import ctypes.util
        path = ctypes.util.find_library("ncursesw") or \
            ctypes.util.find_library("ncurses")
        if path:
            lib = ctypes.CDLL(path)
            if hasattr(lib, "wadd_wch"):
                return True
    except Exception:                       # noqa: BLE001
        pass
    try:
        import curses
        return hasattr(curses, "get_wch")
    except ImportError:
        return False


# Set by --braille / --no-braille. None means "not asked for either way".
_OVERRIDE = None


def force(on):
    """
    Answer for the whole run, from the command line.

    The point is being able to try it, and to turn it off again, without
    reinstalling -- if a console font renders the cat as boxes, the
    person finding that out needs a way to say so immediately.
    """
    global _OVERRIDE
    _OVERRIDE = None if on is None else bool(on)


def supported(profile=None):
    """
    True when braille art is safe to draw.

    Two questions, and they fail differently:

    1. Can curses place it? Detectable, and answered by `wide_curses`.
       No amount of asking the user makes a narrow ncurses build work,
       so this one outranks every preference below it.
    2. Does the console font have the glyphs? NOT detectable -- a console
       either has them or silently draws blanks, and it won't say which.
       So that half is declared, most specific first: the command line,
       then the kid's own setting, then the environment flag that
       install-pi.sh writes once it has installed the font.

    Off is the safe answer, because a wrong "yes" means a child opens the
    game to a grid of empty boxes where their cat should be.
    """
    if not wide_curses():
        return False
    if _OVERRIDE is not None:
        return _OVERRIDE
    if profile is not None:
        pref = (profile or {}).get("braille")
        if pref is not None:
            return bool(pref)
    flag = os.environ.get(ENV_FLAG, "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def set_preference(profile, on):
    """
    Remember a kid's choice, so it survives a restart.

    Per profile rather than per device: siblings share this Pi, and one
    of them preferring letters to dots shouldn't change the other's cat.
    """
    if profile is not None:
        profile["braille"] = bool(on)


def preference(profile):
    """This kid's setting, or None if they've never said."""
    pref = (profile or {}).get("braille")
    return None if pref is None else bool(pref)


def offerable(profile=None):
    """
    Whether to show the kid a choice at all.

    Only when curses could actually draw it. Offering a switch that
    cannot work is worse than not offering one -- a child flips it,
    nothing happens, and the game looks broken rather than the terminal.
    The command line also wins outright, so there's no toggle to argue
    with an explicit --braille / --no-braille.
    """
    return wide_curses() and _OVERRIDE is None
