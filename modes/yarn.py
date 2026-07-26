"""
YARN CHASE -- accuracy, with nothing to lose.

Platform Jumper's engine, reskinned and defanged. A word appears; type it
perfectly and you flick the yarn, and the cat pounces on it in an arc. Miss
a letter and the yarn simply wiggles away: the streak resets and that is the
entire consequence. No lives, no falls, no score to protect.

That is the point of the mode. Platform Jumper teaches "get it right the
first time" by making mistakes cost something; this one teaches the same
habit to the kid who finds that pressure unpleasant, by making a perfect
word feel good rather than making an imperfect one feel bad. There is no
backspace here either -- a slip ends the word, it just doesn't end anything
else.

Words come from `adaptive.generate_lesson`, and every keystroke is reported
with its expected character, so this feeds the weak-key engine like Feed
does.
"""

import curses

from core import adaptive, cat, engine, fx, shop, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

FLICKS = 10           # words per round
REST_X = 6            # where the cat waits, in columns from the left

# The toy the cat is chasing. Owning a toy swaps the art -- the variant
# hook #18 asks for, and the first place shop purchases show up inside a
# game rather than on the menu. Order matters: the first owned toy wins.
TOY_ART = [
    ("feather_wand", ["/", "*"], "feather"),
    ("crinkle_tunnel", ["(", "=", ")"], "crinkle ball"),
    ("red_dot", ["."], "red dot"),
    ("cardboard_box", ["[", "#", "]"], "box scrap"),
    ("yarn_ball", ["(", "@", ")"], "yarn ball"),
]
DEFAULT_TOY = (["(", "@", ")"], "yarn ball")


def toy_for(profile):
    """(art, name) for the toy this kid's cat chases."""
    for item_id, art, name in TOY_ART:
        if shop.owns(profile, item_id):
            return art, name
    return DEFAULT_TOY


def _toy_str(art):
    return "".join(art)


def _draw_scene(stdscr, kitty, pose, toy_art, toy_name, target, typed,
                flicks, streak, cat_pos, toy_x, msg=None, wrong=False):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    center(stdscr, 0, "Y A R N   C H A S E", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Flick %d/%d" % (min(flicks + 1, FLICKS), FLICKS),
                cp(C_WARN, True))
    safe_addstr(stdscr, 1, 22, "Streak %d" % streak, cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 38, "chasing the %s" % toy_name, cp(C_PENDING))

    floor = h - 5
    cx, cy = cat_pos

    # The toy sits on the floor line; the cat pounces up to meet it.
    toy = _toy_str(toy_art)
    safe_addstr(stdscr, floor, max(0, int(toy_x)), toy,
                cp(C_WRONG if wrong else C_ACCENT, True))

    if kitty is not None:
        rows = kitty.height(pose)
        kitty.draw(stdscr, int(cy) - rows + 1, max(0, int(cx)), pose)
    else:
        # No cat hatched yet: a paw stands in, so the mode still plays.
        safe_addstr(stdscr, int(cy), max(0, int(cx)), "(_)", cp(C_WARN, True))

    safe_addstr(stdscr, floor + 1, 0, "~" * max(0, w - 1), cp(C_PENDING))

    row = min(h - 8, 8)
    center(stdscr, row - 2, "Type it perfectly to flick the %s" % toy_name,
           cp(C_PENDING))
    if target:
        tx = max(0, (w - len(target)) // 2)
        ui.draw_typing_line(stdscr, row, tx, target, typed)

    if msg:
        center(stdscr, row + 2, msg, cp(C_WRONG if wrong else C_CORRECT, True))

    center(stdscr, h - 1,
           "a slip only resets the streak -- nothing is ever lost   -   ESC to stop",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def _pounce(draw, floor, from_x, to_x):
    """The cat arcs onto the toy. Mirrors the platformer's jump curve."""
    steps = 12
    for s in range(steps + 1):
        t = s / steps
        x = from_x + (to_x - from_x) * t
        y = floor - 5 * (t - t * t) * 2      # parabola, feet back down at t=1
        pose = "pounce" if s < steps else "overjoyed"
        if s == steps:
            fx.spawn("spark", floor - 1, to_x)
        draw(pose, (x, y))
        curses.napms(26)
    for _ in range(6):
        draw("overjoyed", (to_x, floor))
        curses.napms(30)


def _wiggle_away(draw, floor, cat_x, toy_x, toy_name, word):
    """
    The toy skitters off. The cat watches it go and that is the whole
    consequence -- but the word is shown, because the kid who missed it is
    exactly the kid who needs to see how it was spelled.
    """
    x = toy_x
    for _ in range(10):
        x += 2.0
        draw("wary", (cat_x, floor), toy_x=x, wrong=True,
             msg="the %s got away -- it was '%s'" % (toy_name, word))
        curses.napms(34)


def play(stdscr, profile):
    kitty = cat.Cat.from_profile(profile)
    toy_art, toy_name = toy_for(profile)
    words = adaptive.generate_lesson(profile, FLICKS)
    sess = engine.Session()

    flicks = 0
    caught = 0
    typed = ""
    streak = 0
    best_streak = 0
    misses = 0

    curses.curs_set(0)
    stdscr.nodelay(False)
    fx.clear()

    h, w = stdscr.getmaxyx()
    floor = h - 5
    toy_home = max(REST_X + 14, w - 22)

    while flicks < FLICKS:
        target = words[flicks % len(words)]

        def draw(pose="sit", pos=None, toy_x=toy_home, msg=None, wrong=False,
                 _t=target):
            _draw_scene(stdscr, kitty, pose, toy_art, toy_name, _t, typed,
                        flicks, streak, pos or (REST_X, floor), toy_x,
                        msg=msg, wrong=wrong)

        draw()
        key = stdscr.getch()

        if engine.is_quit(key):
            break
        if not engine.is_typable(key):
            continue

        ch = chr(key)
        expected = target[len(typed)] if len(typed) < len(target) else None

        if expected is not None and ch == expected:
            typed += ch
            sess.keystroke(True, ch=expected)

            if typed == target:
                sess.word_done()
                caught += 1
                streak += 1
                best_streak = max(best_streak, streak)
                _pounce(draw, floor, REST_X, toy_home)
                flicks += 1
                typed = ""
        else:
            # One wrong key ends the word. The streak is the only casualty:
            # no lives, no fish taken back, and the round keeps its length.
            sess.keystroke(False, ch=expected)
            misses += 1
            streak = 0
            _wiggle_away(draw, floor, REST_X, toy_home, toy_name, target)
            flicks += 1
            typed = ""

    sess.finish()
    stdscr.nodelay(False)

    perfect = misses == 0 and flicks >= FLICKS
    if best_streak > profile.get("yarn_best_streak", 0):
        profile["yarn_best_streak"] = best_streak
    if perfect:
        profile["yarn_perfect_rounds"] = profile.get("yarn_perfect_rounds", 0) + 1

    name = kitty.name if kitty else "Your cat"
    if perfect:
        title = "PERFECT CHASE!"
        lines = ["%s caught the %s every single time." % (name, toy_name)]
    elif caught:
        title = "GOOD CHASING"
        lines = ["%s caught the %s %d time%s."
                 % (name, toy_name, caught, "" if caught == 1 else "s")]
    else:
        title = "MAYBE LATER"
        lines = ["The %s won this round." % toy_name, "",
                 "%s had fun anyway." % name]

    lines += [
        "",
        "Best streak: %d" % best_streak,
        "Accuracy: %.1f%%" % sess.accuracy,
        "WPM: %.1f" % sess.wpm,
    ]

    ui.message(stdscr, lines, title=title,
               art=kitty.portrait_art("overjoyed" if caught else "sit") if kitty else None)
    return sess.summary()
