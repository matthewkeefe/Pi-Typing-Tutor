"""
FEED -- the Food care task, and the pedagogical payload of the whole game.

Underneath the fishing costume this is the adaptive weak-key drill: words
come from `adaptive.generate_lesson`, so every one of them is built from
the letters this kid has unlocked and carries the letter they're worst at.
Type a word, a fish arcs across the screen into the bowl.

Mistakes have to be backspaced (the rocket-mode convention) because the
point of this drill is clean keystrokes on hard keys, not speed.
"""

import curses

from core import adaptive, cat, engine, fx, scrapbook, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

WORDS = 18
FISH = "><>"

BOWL = [
    " \\       / ",
    "  \\_____/  ",
]
BOWL_W = 11


def _bowl_rows(caught, total):
    """The bowl with its water line rising as fish go in."""
    rows = list(BOWL)
    if caught:
        depth = min(3, 1 + (2 * caught) // max(1, total))
        rows[0] = " \\ " + ("~" * (depth + 2)).center(5, " ") + " / "
    return rows


def _draw_scene(stdscr, profile, kitty, pose, target, typed, caught, err, fish_x):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    center(stdscr, 0, "F I S H I N G   T I M E", cp(C_TITLE, True))

    name = kitty.name if kitty else "your cat"
    bowl_x = max(2, w // 2 - 24)
    cat_y = 3

    if kitty:
        kitty.draw(stdscr, cat_y, bowl_x, pose)
        bowl_top = cat_y + kitty.height(pose)
    else:
        bowl_top = cat_y + 5
    for i, row in enumerate(_bowl_rows(caught, WORDS)):
        safe_addstr(stdscr, bowl_top + i, bowl_x, row, cp(C_PENDING, True))

    safe_addstr(stdscr, cat_y, bowl_x + 16, "%s's bowl" % name, cp(C_ACCENT, True))
    safe_addstr(stdscr, cat_y + 2, bowl_x + 16,
                "%d of %d fish" % (caught, WORDS), cp(C_WARN, True))
    bar = min(28, max(10, w - bowl_x - 20))
    filled = int(bar * caught / WORDS)
    safe_addstr(stdscr, cat_y + 3, bowl_x + 16,
                "[" + "#" * filled + "." * (bar - filled) + "]", cp(C_CORRECT, True))

    # the fish in flight, mid-arc between the word and the bowl
    if fish_x is not None:
        safe_addstr(stdscr, bowl_top - 1, max(0, fish_x), FISH, cp(C_WARN, True))

    row = min(h - 6, 13)
    center(stdscr, row - 2, "Type the word to hook a fish", cp(C_PENDING))
    tx = max(0, (w - len(target)) // 2)
    ui.draw_typing_line(stdscr, row, tx, target, typed)
    if err:
        center(stdscr, row + 2, "backspace and try that one again", cp(C_WRONG))

    center(stdscr, h - 1, "ESC to stop -- fish you caught are yours", cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def _fly_fish(stdscr, profile, kitty, target, caught, from_x, to_x):
    """Six frames of fish arcing into the bowl. Cheap, and it reads."""
    steps = 6
    for i in range(steps):
        x = int(from_x + (to_x - from_x) * (i + 1) / steps)
        pose = "pounce" if i < steps - 2 else "overjoyed"
        if i == steps - 1:
            fx.spawn("splash", 9, x)   # it lands in the water
        _draw_scene(stdscr, profile, kitty, pose, target, target, caught, False, x)
        curses.napms(45)
    for _ in range(4):                 # watch the splash come down
        _draw_scene(stdscr, profile, kitty, "sit", target, target, caught, False, None)
        curses.napms(28)


def play(stdscr, profile):
    kitty = cat.Cat.from_profile(profile)
    words = adaptive.generate_lesson(profile, WORDS)
    sess = engine.Session()

    idx = 0
    typed = ""
    err = False
    caught = 0
    new_species = []

    curses.curs_set(0)
    stdscr.nodelay(False)
    fx.clear()

    while idx < len(words):
        target = words[idx]
        _draw_scene(stdscr, profile, kitty, "sit", target, typed, caught, err, None)
        key = stdscr.getch()

        if engine.is_quit(key):
            break
        if engine.is_backspace(key):
            typed = typed[:-1]
            err = False
            continue
        if not engine.is_typable(key):
            continue

        ch = chr(key)
        expected = target[len(typed)] if len(typed) < len(target) else None
        if expected is not None and ch == expected:
            typed += ch
            sess.keystroke(True, ch=expected)
            err = False
        else:
            sess.keystroke(False, ch=expected)
            err = True
            if len(typed) < len(target):
                typed += ch  # show the wrong letter so they can see it

        if typed == target:
            sess.word_done()
            caught += 1
            # A word containing a letter whose species is still a
            # silhouette hooks it. No roll: rarity is English, not a dice
            # table -- see core/scrapbook.py.
            new_species.extend(scrapbook.catch_from_word(profile, target))
            h, w = stdscr.getmaxyx()
            _fly_fish(stdscr, profile, kitty, target, caught,
                      (w - len(target)) // 2, max(2, w // 2 - 24) + 4)
            idx += 1
            typed = ""
            err = False

    sess.finish()
    stdscr.nodelay(False)

    if caught:
        cat.stamp_care(profile, "food")

    name = kitty.name if kitty else "Your cat"
    if caught >= WORDS:
        lines = ["%s cleaned the whole bowl." % name, "",
                 "%d fish, %.0f%% accurate" % (caught, sess.accuracy)]
        title = "WHAT A CATCH"
    elif caught:
        lines = ["%s got %d fish. Good enough for now!" % (name, caught), "",
                 "They're in the bowl -- nothing gets thrown back."]
        title = "NICE FISHING"
    else:
        lines = ["No fish this time.", "", "%s doesn't mind. Come back soon." % name]
        title = "MAYBE LATER"

    ui.message(stdscr, lines, title=title,
               art=kitty.portrait_art("overjoyed") if kitty and caught else None)
    summary = sess.summary()
    if new_species:
        summary["species"] = new_species
    return summary
