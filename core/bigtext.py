"""
Big block letters, for the one screen that should look like a title.

Letters are drawn as a 6x5 dot bitmap and rendered two dot-rows per
character row using half-blocks, so a 6-row letter fits in 3 rows of
text and still has curves in it. Same trick as core/braille.py, coarser:
one character carries a top and a bottom pixel instead of eight.

    ##  ##      ->   ██
    ##  ##           ██
    ######           ▀▀

ABOUT THE CHARACTERS
    U+2580, U+2584 and U+2588 are the CP437 block elements, which the
    Linux console has had since it was a VGA text mode -- they're what
    every TUI on earth draws its bars with, and they are in the default
    console font. That is a much safer bet than the braille range, which
    genuinely isn't there without installing a font.

    It is still a bet, and it isn't detectable (a console with no glyph
    draws a blank and never says so). `ASCII_FALLBACK` renders the same
    bitmaps with plain '#' at full height if a Pi ever shows boxes here.
"""

# (top, bottom) -> the character that lights those halves.
HALVES = {(0, 0): " ", (1, 0): "▀", (0, 1): "▄", (1, 1): "█"}

WIDTH, HEIGHT = 5, 6
GAP = 1                 # blank columns between letters

# 6 rows of 5, '#' on. Only the letters the game's titles need; anything
# else renders as a blank space rather than raising, because a title is
# never worth taking the screen down for.
FONT = {
    "A": ["·###·", "#···#", "#···#", "#####", "#···#", "#···#"],
    "C": ["·####", "#····", "#····", "#····", "#····", "·####"],
    "E": ["#####", "#····", "####·", "#····", "#····", "#####"],
    "G": ["·####", "#····", "#····", "#·###", "#···#", "·####"],
    "H": ["#···#", "#···#", "#####", "#···#", "#···#", "#···#"],
    "I": ["#####", "··#··", "··#··", "··#··", "··#··", "#####"],
    "M": ["#···#", "##·##", "#·#·#", "#···#", "#···#", "#···#"],
    "N": ["#···#", "##··#", "#·#·#", "#··##", "#···#", "#···#"],
    "O": ["·###·", "#···#", "#···#", "#···#", "#···#", "·###·"],
    "P": ["####·", "#···#", "#···#", "####·", "#····", "#····"],
    "R": ["####·", "#···#", "#···#", "####·", "#··#·", "#···#"],
    "T": ["#####", "··#··", "··#··", "··#··", "··#··", "··#··"],
    "U": ["#···#", "#···#", "#···#", "#···#", "#···#", "·###·"],
    "Y": ["#···#", "#···#", "·#·#·", "··#··", "··#··", "··#··"],
    " ": ["·····", "·····", "·····", "·····", "·····", "·····"],
}

ASCII_FALLBACK = False   # flip if a console has no block elements


def _bitmap(text):
    """The whole string as one 6-row grid of on/off columns."""
    rows = [[] for _ in range(HEIGHT)]
    for i, ch in enumerate(text.upper()):
        glyph = FONT.get(ch, FONT[" "])
        for r in range(HEIGHT):
            if i:
                rows[r].extend([0] * GAP)
            rows[r].extend(1 if c == "#" else 0 for c in glyph[r])
    return rows


def render(text):
    """`text` as block-letter rows. Three rows tall, or six in ASCII mode."""
    grid = _bitmap(text)
    if ASCII_FALLBACK:
        return ["".join("#" if c else " " for c in row).rstrip()
                for row in grid]
    out = []
    for top, bottom in zip(grid[0::2], grid[1::2]):
        line = "".join(HALVES[(t, b)] for t, b in zip(top, bottom))
        out.append(line.rstrip())
    return out


def width(text):
    return max((len(r) for r in render(text)), default=0)


def block(lines, gap=0):
    """
    Several strings rendered and stacked, centred on the widest.

    A title that wraps to two lines has to agree with itself about where
    the middle is, or the second line sits visibly off to one side.
    """
    parts = [render(line) for line in lines]
    full = max((max((len(r) for r in p), default=0) for p in parts), default=0)
    out = []
    for i, part in enumerate(parts):
        if i and gap:
            out.extend([""] * gap)
        pad = (full - max((len(r) for r in part), default=0)) // 2
        out.extend((" " * pad + r).rstrip() if r else "" for r in part)
    return out
