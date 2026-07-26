"""
Shared curses helpers. Stdlib only so this runs on a stripped
Buildroot image with nothing but python3 + ncurses terminfo.
"""

import curses

# Color pair IDs
C_DEFAULT = 1
C_CORRECT = 2
C_WRONG = 3
C_PENDING = 4
C_TITLE = 5
C_ACCENT = 6
C_WARN = 7
C_BADGE = 8
C_FLAME = 9

# Cat genes get their own block of pairs (DESIGN 9.4). Black is missing on
# purpose: on a bare console it's invisible against the background, and a
# cat nobody can see isn't a lateral trait, it's a bad one.
C_CAT_BASE = 10
CAT_COLOR_NAMES = ["white", "yellow", "cyan", "magenta", "green", "blue", "red"]


def _cat_color_number(name):
    return getattr(curses, "COLOR_" + name.upper(), curses.COLOR_WHITE)


def cat_color(name, bold=False):
    """Attribute for one of the named cat colours."""
    try:
        idx = CAT_COLOR_NAMES.index(name)
    except ValueError:
        return cp(C_DEFAULT, bold)
    return cp(C_CAT_BASE + idx, bold)


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK

    curses.init_pair(C_DEFAULT, curses.COLOR_WHITE, bg)
    curses.init_pair(C_CORRECT, curses.COLOR_GREEN, bg)
    curses.init_pair(C_WRONG, curses.COLOR_RED, bg)
    curses.init_pair(C_PENDING, curses.COLOR_BLUE, bg)
    curses.init_pair(C_TITLE, curses.COLOR_CYAN, bg)
    curses.init_pair(C_ACCENT, curses.COLOR_MAGENTA, bg)
    curses.init_pair(C_WARN, curses.COLOR_YELLOW, bg)
    curses.init_pair(C_BADGE, curses.COLOR_YELLOW, bg)
    curses.init_pair(C_FLAME, curses.COLOR_YELLOW, bg)

    for i, name in enumerate(CAT_COLOR_NAMES):
        try:
            curses.init_pair(C_CAT_BASE + i, _cat_color_number(name), bg)
        except curses.error:
            pass  # terminal is short on pairs; cats fall back to white


def cp(pair, bold=False):
    attr = curses.color_pair(pair)
    if bold:
        attr |= curses.A_BOLD
    return attr


def safe_addstr(win, y, x, text, attr=0):
    """Write without ever throwing on edge-of-screen."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    space = w - x
    if space <= 0:
        return
    text = text[:space]
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def center(win, y, text, attr=0):
    h, w = win.getmaxyx()
    x = max(0, (w - len(text)) // 2)
    safe_addstr(win, y, x, text, attr)


def draw_art(win, top, art_lines, attr=0, center_x=True):
    """Draw a block of ASCII art, centered horizontally by default."""
    h, w = win.getmaxyx()
    width = max((len(l) for l in art_lines), default=0)
    x0 = max(0, (w - width) // 2) if center_x else 2
    for i, line in enumerate(art_lines):
        safe_addstr(win, top + i, x0, line, attr)


def draw_box(win, y, x, h, w, title=None, attr=0):
    safe_addstr(win, y, x, "+" + "-" * (w - 2) + "+", attr)
    for i in range(1, h - 1):
        safe_addstr(win, y + i, x, "|", attr)
        safe_addstr(win, y + i, x + w - 1, "|", attr)
    safe_addstr(win, y + h - 1, x, "+" + "-" * (w - 2) + "+", attr)
    if title:
        safe_addstr(win, y, x + 2, " " + title + " ", attr | curses.A_BOLD)


def speech_bubble(win, y, x, lines, attr=0, tail_x=3, tail_up=False):
    """
    The cat's voice. Everything the game wants to say to a kid comes out
    of the cat, not out of a system message.

     .---------------.
     | Hi Matt!      |
     '--v------------'

    `tail_x` is the tail's offset inside the bubble; `tail_up` points it
    at a cat sitting above instead of below. Returns the height drawn.
    """
    if isinstance(lines, str):
        lines = [lines]
    lines = list(lines) or [""]
    inner = max(len(l) for l in lines) + 2
    tail_x = max(1, min(inner, tail_x))

    def edge(corner_l, corner_r, tail_ch):
        row = [corner_l] + ["-"] * inner + [corner_r]
        if tail_ch:
            row[tail_x] = tail_ch
        return "".join(row)

    safe_addstr(win, y, x, edge(".", ".", "^" if tail_up else None), attr)
    for i, line in enumerate(lines):
        safe_addstr(win, y + 1 + i, x, "| " + line.ljust(inner - 1) + "|", attr)
    safe_addstr(win, y + 1 + len(lines), x,
                edge("'", "'", None if tail_up else "v"), attr)
    return len(lines) + 2


def draw_typing_line(win, y, x, target, typed, wrong_at=None):
    """
    Render `target` with per-character coloring based on `typed`.
    Correct chars green, the current mistake red, untyped dim blue.
    """
    for i, ch in enumerate(target):
        display = ch if ch != " " else " "
        if i < len(typed):
            if typed[i] == ch:
                attr = cp(C_CORRECT, True)
            else:
                attr = cp(C_WRONG, True) | curses.A_REVERSE
                display = ch if ch != " " else "_"
        elif i == len(typed):
            attr = cp(C_WARN, True) | curses.A_UNDERLINE
        else:
            attr = cp(C_PENDING)
        safe_addstr(win, y, x + i, display, attr)


def menu(stdscr, title, options, subtitle=None, footer=None, art=None,
         draw_extra=None, option_icons=None, tick_ms=110):
    """
    Arrow-key menu. Returns the selected index, or -1 if the user
    backs out with q / ESC.

    `draw_extra(win)` is called after the options each frame; passing it
    switches the loop to non-blocking so something can animate (the cat on
    the main menu) without input ever going sluggish. Without it the loop
    blocks on getch exactly as it always did.

    `option_icons` is an optional per-option `(text, attr)` drawn just left
    of the label in its own colour -- the cat glyphs in the profile picker.
    """
    idx = 0
    curses.curs_set(0)
    animated = draw_extra is not None
    stdscr.nodelay(animated)
    try:
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            top = 1
            if art:
                draw_art(stdscr, top, art, cp(C_TITLE, True))
                top += len(art) + 1
            center(stdscr, top, title, cp(C_TITLE, True))
            top += 1
            if subtitle:
                center(stdscr, top, subtitle, cp(C_PENDING))
                top += 1
            top += 1

            for i, opt in enumerate(options):
                selected = i == idx
                label = ("  > " + opt + "  ") if selected else ("    " + opt + "  ")
                attr = cp(C_WARN, True) | curses.A_REVERSE if selected else cp(C_DEFAULT)
                x = max(0, (w - len(label)) // 2)
                safe_addstr(stdscr, top + i, x, label, attr)
                icon = option_icons[i] if option_icons and i < len(option_icons) else None
                if icon:
                    text, icon_attr = icon
                    safe_addstr(stdscr, top + i, x - len(text) - 1, text, icon_attr)

            foot = footer or "up/down to move   ENTER to pick   q to go back"
            center(stdscr, min(h - 2, top + len(options) + 2), foot, cp(C_PENDING))
            if draw_extra:
                draw_extra(stdscr)
            stdscr.refresh()

            key = stdscr.getch()
            if key == -1:
                curses.napms(tick_ms)
                continue
            if key in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(options)
            elif key in (curses.KEY_ENTER, 10, 13):
                return idx
            elif key in (ord("q"), 27):
                return -1
    finally:
        stdscr.nodelay(False)


def message(stdscr, lines, title=None, art=None, wait=True):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    top = 2
    if art:
        draw_art(stdscr, top, art, cp(C_ACCENT, True))
        top += len(art) + 1
    if title:
        center(stdscr, top, title, cp(C_TITLE, True))
        top += 2
    for i, line in enumerate(lines):
        center(stdscr, top + i, line, cp(C_DEFAULT))
    if wait:
        center(stdscr, min(h - 2, top + len(lines) + 2),
               "press any key", cp(C_PENDING))
        stdscr.refresh()
        stdscr.nodelay(False)
        stdscr.getch()
    else:
        stdscr.refresh()


def celebrate(stdscr, lines, title=None, art=None, kind="confetti"):
    """
    `message`, with a short particle flourish over it first. Any keypress
    skips the animation -- a kid who has seen the confetti twice should
    never have to sit through it again.
    """
    # Imported here rather than at module scope: fx draws through these
    # helpers, so a top-level import would be circular.
    from core import fx

    fx.sparkle_over(stdscr, kind,
                    lambda win: message(win, lines, title=title, art=art, wait=False))
    message(stdscr, lines, title=title, art=art)


def ask_text(stdscr, prompt, maxlen=16):
    """Simple single-line text input (used for profile names)."""
    curses.curs_set(1)
    buf = ""
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        center(stdscr, h // 2 - 2, prompt, cp(C_TITLE, True))
        box_w = maxlen + 4
        x = max(0, (w - box_w) // 2)
        draw_box(stdscr, h // 2 - 1, x, 3, box_w, attr=cp(C_PENDING))
        safe_addstr(stdscr, h // 2, x + 2, buf, cp(C_WARN, True))
        center(stdscr, h // 2 + 3, "ENTER to confirm   ESC to cancel", cp(C_PENDING))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            if buf.strip():
                curses.curs_set(0)
                return buf.strip()
        elif key == 27:
            curses.curs_set(0)
            return None
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            buf = buf[:-1]
        elif 32 <= key < 127 and len(buf) < maxlen:
            buf += chr(key)
