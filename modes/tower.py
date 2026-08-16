"""
CAT TOWER -- level based.

Seven levels, seven tiers of a cat tree. Clear a level's word drill at
85%+ accuracy and the next tier gets bolted on. Finish all seven and the
cat climbs it.

The tower art lives on a fixed 14-wide / 18-tall canvas so it grows
upward in place instead of jumping around the screen. Every tier is
drawn bottom-up for the same reason: the base never moves, so the kid
watches the thing they built get taller rather than watching it redraw.
"""

import curses

from core import cat, lessons, ui, engine, fx
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_FLAME, C_DEFAULT, C_WRONG)

BLANK = " " * 14

# Full canvas, top (0) to bottom (17). Posts sit at columns 4 and 9 in
# every piece, which is what lets the tiers stack without a seam.
PERCH = [
    "  __________  ",
    " /          \\ ",
    " |__________| ",
    "    |    |    ",
]
POST_PLAIN = "    |    |    "
POST_HAMMOCK = "   (~~~~~~)   "
POST_CUBBY = "    |(__)|    "
POST_TOY = "    |    |-o  "

POST_SISAL = "    |####|    "
WING_T = "   /|####|\\   "
POST_BOTTOM = "    |____|    "
WING_M = "  / |####| \\  "
WING_B = " /__|####|__\\ "

BASE = [
    "    |    |    ",
    "  __|____|__  ",
    " /          \\ ",
    "/____________\\",
]
RUG = "~~~~~~~~~~~~~~"

TIER_NAMES = [
    "Base Board",
    "Lower Post",
    "Upper Post",
    "Top Perch",
    "Sisal Wrap",
    "Hammock & Cubby",
    "Catnip & Dangly Toy",
]


def build_tower(tiers, toy=False):
    """
    Render the tower at `tiers` completion (0-7).
    Returns a list of 18 strings, always the same height.
    """
    has_base = tiers >= 1
    has_lower = tiers >= 2
    has_upper = tiers >= 3
    has_perch = tiers >= 4
    has_sisal = tiers >= 5
    has_detail = tiers >= 6
    has_toy = toy or tiers >= 7

    canvas = []

    # Lines 0-3: top perch
    canvas += PERCH if has_perch else [BLANK] * 4

    # Lines 4-7: upper post (gains the hammock and cubby at tier 6, and
    # the dangly toy at tier 7)
    if has_upper:
        canvas.append(POST_TOY if has_toy else POST_PLAIN)
        canvas.append(POST_HAMMOCK if has_detail else POST_PLAIN)
        canvas.append(POST_PLAIN)
        canvas.append(POST_CUBBY if has_detail else POST_PLAIN)
    else:
        canvas += [BLANK] * 4

    # Lines 8-11: lower post, wrapped in sisal and given wings at tier 5
    if has_lower:
        canvas.append(POST_SISAL if has_sisal else POST_PLAIN)
        canvas.append(WING_T if has_sisal else POST_PLAIN)
        canvas.append(WING_M if has_sisal else POST_PLAIN)
        canvas.append(WING_B if has_sisal else POST_BOTTOM)
    else:
        canvas += [BLANK] * 4

    # Lines 12-15: base board
    canvas += BASE if has_base else [BLANK] * 4

    # Lines 16-17: the rug it stands on
    canvas.append(RUG)
    canvas.append(BLANK)

    return canvas


def _draw_frame(stdscr, profile, tiers, level, targets, idx, typed, sess, err_flash):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    lvl = lessons.get_level(level)

    center(stdscr, 0, "C A T   T O W E R", cp(C_TITLE, True))

    tower = build_tower(tiers)
    for i, line in enumerate(tower):
        safe_addstr(stdscr, 2 + i, 2, line, cp(C_ACCENT, True))

    col = 20
    safe_addstr(stdscr, 2, col, "Level %d/%d  -  %s" % (level, lessons.max_level(), lvl["name"]),
                cp(C_WARN, True))
    safe_addstr(stdscr, 3, col, "Building: " + TIER_NAMES[min(tiers, 6)], cp(C_PENDING))
    safe_addstr(stdscr, 5, col, "Word %d of %d" % (idx + 1, len(targets)), cp(C_DEFAULT))

    # progress bar
    bar_w = min(30, max(10, w - col - 4))
    filled = int(bar_w * idx / max(1, len(targets)))
    safe_addstr(stdscr, 6, col, "[" + "#" * filled + "." * (bar_w - filled) + "]",
                cp(C_CORRECT, True))

    target = targets[idx]
    safe_addstr(stdscr, 9, col, "Type this:", cp(C_PENDING))
    ui.draw_typing_line(stdscr, 10, col, target, typed)

    if err_flash:
        safe_addstr(stdscr, 12, col, "Oops! Backspace and try again.", cp(C_WRONG, True))

    safe_addstr(stdscr, 15, col, "WPM %5.1f" % sess.wpm, cp(C_WARN))
    safe_addstr(stdscr, 16, col, "Accuracy %5.1f%%" % sess.accuracy, cp(C_WARN))
    safe_addstr(stdscr, 17, col, "Tower tiers %d/7" % tiers, cp(C_ACCENT))

    center(stdscr, h - 1, "ESC to quit to menu", cp(C_PENDING))
    stdscr.refresh()


def _climb_animation(stdscr, profile):
    """
    The finished tower stays put and the cat climbs it.

    The rocket this mode grew out of flew off the top of the screen, which
    took the thing the kid spent seven levels building with it. A tower is
    the opposite promise: it stays, and the payoff is watching the cat get
    to the top of it.
    """
    h, w = stdscr.getmaxyx()
    tower = build_tower(7)
    x = max(0, (w - 14) // 2)
    top = max(1, (h - len(tower)) // 2)

    kitty = cat.Cat.from_profile(profile)
    # Bottom of the rug up to the top perch, in screen rows.
    start_row = top + 16
    end_row = top + 2

    stdscr.nodelay(True)
    fx.clear()
    for step in range(start_row - end_row + 12):
        stdscr.erase()
        for i, line in enumerate(tower):
            safe_addstr(stdscr, top + i, x, line, cp(C_ACCENT, True))

        row = max(end_row, start_row - step)
        arrived = row <= end_row
        if kitty is not None:
            pose = "overjoyed" if arrived else "pounce"
            rows = kitty.height(pose)
            kitty.draw(stdscr, row - rows + 1, x + 5, pose)
        else:
            safe_addstr(stdscr, row, x + 5, "=^.^=", cp(C_FLAME, True))

        if arrived:
            center(stdscr, 0, "T O P   O F   T H E   T O W E R !", cp(C_WARN, True))
            fx.spawn("confetti", top, x + 7, n=3, scale=0.5)
        fx.tick(0.09)
        fx.draw(stdscr)
        stdscr.refresh()
        curses.napms(90)
        if stdscr.getch() == 27:
            break
    stdscr.nodelay(False)
    fx.clear()

    ui.message(
        stdscr,
        [
            "You built the whole tower and the cat climbed it.",
            "",
            "Best WPM: %.1f    Best accuracy: %.1f%%" % (profile["best_wpm"], profile["best_accuracy"]),
            "",
            "The tower resets so you can build a taller one.",
        ],
        title="TOP PERCH REACHED",
    )


def play(stdscr, profile):
    """Run one level of tower mode. Returns a session summary or None."""
    level = profile.get("tower_level", 1)
    tiers = profile.get("tower_tiers", 0)

    targets = lessons.words_for_level(level, count=8)
    idx = 0
    typed = ""
    err_flash = False
    sess = engine.Session()

    curses.curs_set(0)
    stdscr.nodelay(False)

    while idx < len(targets):
        _draw_frame(stdscr, profile, tiers, level, targets, idx, typed, sess, err_flash)
        key = stdscr.getch()

        if engine.is_quit(key):
            sess.finish()
            return sess.summary() if sess.total_keystrokes else None

        if engine.is_backspace(key):
            typed = typed[:-1]
            err_flash = False
            continue

        if not engine.is_typable(key):
            continue

        ch = chr(key)
        target = targets[idx]

        # Block progress past a mistake -- accuracy is the point
        if len(typed) < len(target) and ch == target[len(typed)]:
            typed += ch
            sess.keystroke(True)
            err_flash = False
        else:
            sess.keystroke(False)
            err_flash = True
            if len(typed) < len(target):
                typed += ch  # show the wrong char so they can see it

        if typed == target:
            sess.word_done()
            idx += 1
            typed = ""
            err_flash = False

    sess.finish()

    # Did they earn the tier?
    earned = sess.accuracy >= 85.0
    if earned:
        tiers += 1
        profile["tower_tiers"] = tiers
        if level < lessons.max_level():
            profile["tower_level"] = level + 1

        if tiers >= 7:
            _climb_animation(stdscr, profile)
            profile["tower_tiers"] = 0
            profile["tower_level"] = 1
        else:
            ui.message(
                stdscr,
                [
                    "%s bolted on!" % TIER_NAMES[tiers - 1],
                    "",
                    "WPM %.1f    Accuracy %.1f%%" % (sess.wpm, sess.accuracy),
                    "",
                    "Next up: " + TIER_NAMES[min(tiers, 6)],
                ],
                title="TIER COMPLETE",
                art=build_tower(tiers),
            )
    else:
        ui.message(
            stdscr,
            [
                "Accuracy %.1f%% -- you need 85%% to bolt the tier on." % sess.accuracy,
                "",
                "Slow down a little. Speed comes from accuracy,",
                "not the other way around.",
            ],
            title="ALMOST!",
            art=build_tower(tiers),
        )

    return sess.summary()
