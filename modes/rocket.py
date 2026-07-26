"""
ROCKET BUILDER -- level based.

Seven levels, seven rocket parts. Clear a level's word drill at 85%+
accuracy and the next part gets welded onto your ship. Finish all
seven and it launches.

The ship art lives on a fixed 14-wide / 17-tall canvas so the rocket
grows upward in place instead of jumping around the screen.
"""

import curses

from core import lessons, ui, engine, fx
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_FLAME, C_DEFAULT, C_WRONG)

BLANK = " " * 14

# Full canvas, top (0) to bottom (16)
NOSE = [
    "      /\\      ",
    "     /  \\     ",
    "    /    \\    ",
    "   /______\\   ",
]
BODY_PLAIN = "   |      |   "
BODY_WINDOW = "   |  ()  |   "
BODY_HATCH = "   | |--| |   "
BODY_BOTTOM = "   |______|   "

FIN_L = "  /|      |\\  "
FIN_M = " / |      | \\ "
FIN_B = "/__|______|__\\"

ENGINE = [
    "   |  ||  |   ",
    "   |__||__|   ",
    "    \\ || /    ",
    "     \\||/     ",
]
PAD = "=============="

FLAMES = [
    "     \\||/     ",
    "     (  )     ",
    "      \\/      ",
]

PART_NAMES = [
    "Engine Bell",
    "Lower Fuel Tank",
    "Upper Fuel Tank",
    "Nose Cone",
    "Stabilizer Fins",
    "Viewport & Hatch",
    "Fuel & Ignition",
]


def build_ship(parts, flames=False):
    """
    Render the ship at `parts` completion (0-7).
    Returns a list of 18 strings, always the same height.
    """
    has_engine = parts >= 1
    has_lower = parts >= 2
    has_upper = parts >= 3
    has_nose = parts >= 4
    has_fins = parts >= 5
    has_detail = parts >= 6

    canvas = []

    # Lines 0-3: nose cone
    canvas += NOSE if has_nose else [BLANK] * 4

    # Lines 4-7: upper tank (with viewport/hatch at 6)
    if has_upper:
        canvas.append(BODY_PLAIN)
        canvas.append(BODY_WINDOW if has_detail else BODY_PLAIN)
        canvas.append(BODY_PLAIN)
        canvas.append(BODY_HATCH if has_detail else BODY_PLAIN)
    else:
        canvas += [BLANK] * 4

    # Lines 8-11: lower tank, gains fins at part 5
    if has_lower:
        canvas.append(BODY_PLAIN)
        canvas.append(FIN_L if has_fins else BODY_PLAIN)
        canvas.append(FIN_M if has_fins else BODY_PLAIN)
        canvas.append(FIN_B if has_fins else BODY_BOTTOM)
    else:
        canvas += [BLANK] * 4

    # Lines 12-15: engine
    canvas += ENGINE if has_engine else [BLANK] * 4

    # Line 16-17: flame or pad
    if flames:
        canvas.append(FLAMES[1])
        canvas.append(FLAMES[2])
    else:
        canvas.append(PAD)
        canvas.append(BLANK)

    return canvas


def _draw_frame(stdscr, profile, parts, level, targets, idx, typed, sess, err_flash):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    lvl = lessons.get_level(level)

    center(stdscr, 0, "R O C K E T   B U I L D E R", cp(C_TITLE, True))

    ship = build_ship(parts)
    for i, line in enumerate(ship):
        safe_addstr(stdscr, 2 + i, 2, line, cp(C_ACCENT, True))

    col = 20
    safe_addstr(stdscr, 2, col, "Level %d/%d  -  %s" % (level, lessons.max_level(), lvl["name"]),
                cp(C_WARN, True))
    safe_addstr(stdscr, 3, col, "Building: " + PART_NAMES[min(parts, 6)], cp(C_PENDING))
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
    safe_addstr(stdscr, 17, col, "Ship parts %d/7" % parts, cp(C_ACCENT))

    center(stdscr, h - 1, "ESC to quit to menu", cp(C_PENDING))
    stdscr.refresh()


def _launch_animation(stdscr, profile):
    h, w = stdscr.getmaxyx()
    ship = build_ship(7, flames=True)
    x = max(0, (w - 14) // 2)

    stdscr.nodelay(True)
    fx.clear()
    for step in range(h + len(ship) + 2):
        stdscr.erase()
        top = h - len(ship) - step
        for i, line in enumerate(ship):
            attr = cp(C_FLAME, True) if i >= len(ship) - 2 else cp(C_ACCENT, True)
            safe_addstr(stdscr, top + i, x, line, attr)
        if step < 4:
            center(stdscr, h - 1, "%d..." % (4 - step), cp(C_WARN, True))
        else:
            center(stdscr, 0, "L I F T O F F !", cp(C_WARN, True))
            # Exhaust pours out of the engine bell as the ship climbs.
            fx.spawn("burst", top + len(ship), x + 7, n=3, scale=0.5)
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
            "You built the whole ship and launched it.",
            "",
            "Best WPM: %.1f    Best accuracy: %.1f%%" % (profile["best_wpm"], profile["best_accuracy"]),
            "",
            "The rocket resets so you can build a faster one.",
        ],
        title="MISSION COMPLETE",
    )


def play(stdscr, profile):
    """Run one level of rocket mode. Returns a session summary or None."""
    level = profile.get("rocket_level", 1)
    parts = profile.get("rocket_parts", 0)

    targets = lessons.words_for_level(level, count=8)
    idx = 0
    typed = ""
    err_flash = False
    sess = engine.Session()

    curses.curs_set(0)
    stdscr.nodelay(False)

    while idx < len(targets):
        _draw_frame(stdscr, profile, parts, level, targets, idx, typed, sess, err_flash)
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

    # Did they earn the part?
    earned = sess.accuracy >= 85.0
    if earned:
        parts += 1
        profile["rocket_parts"] = parts
        if level < lessons.max_level():
            profile["rocket_level"] = level + 1

        if parts >= 7:
            _launch_animation(stdscr, profile)
            profile["rocket_parts"] = 0
            profile["rocket_level"] = 1
        else:
            ui.message(
                stdscr,
                [
                    "%s attached!" % PART_NAMES[parts - 1],
                    "",
                    "WPM %.1f    Accuracy %.1f%%" % (sess.wpm, sess.accuracy),
                    "",
                    "Next up: " + PART_NAMES[min(parts, 6)],
                ],
                title="PART COMPLETE",
                art=build_ship(parts),
            )
    else:
        ui.message(
            stdscr,
            [
                "Accuracy %.1f%% -- you need 85%% to weld the part on." % sess.accuracy,
                "",
                "Slow down a little. Speed comes from accuracy,",
                "not the other way around.",
            ],
            title="ALMOST!",
            art=build_ship(parts),
        )

    return sess.summary()
