"""
PLATFORM JUMPER -- accuracy focused.

Each platform has a word on it. Type it perfectly and your character
leaps to the next one. Make a single mistake and you fall. There is no
backspace here on purpose -- this is the mode that teaches "get it
right the first time," which is the habit that actually raises WPM.

Clear 10 platforms to finish a run. Do it without falling once for the
perfect-run badge.
"""

import curses
import random

from core import cat, lessons, ui, engine, fx, shop
from core.ui import cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT, C_WRONG, C_PENDING, C_ACCENT

RUN_LENGTH = 10
LIVES = 3
SLOT_W = 16
VISIBLE = 5

HERO = [" o ", "/|\\", "/ \\"]
HERO_JUMP = ["\\o/", " | ", "/ \\"]
HERO_FALL = ["\\o/", "/|\\", " ^ "]

# The jumper has three frames. A kid with a hatched cat gets their own cat
# in the role; anyone else keeps the stick figure, so legacy profiles are
# untouched. Poses come from the existing set -- no new art needed.
CAT_POSES = {"stand": "sit", "leap": "pounce", "fall": "wary"}
LEGACY_ART = {"stand": HERO, "leap": HERO_JUMP, "fall": HERO_FALL}


def _draw_hero(win, kitty, pose, hx, hy):
    """
    Paint the jumper with its feet on (hy, hx).

    Both art paths anchor by their bottom row, which is what keeps the cat
    standing on the platform rather than sunk into it: the stick figure is
    3 rows, a kitten 4 and an adult 5.
    """
    x = int(hx)
    if kitty is not None:
        rows = kitty.height(CAT_POSES[pose])
        kitty.draw(win, int(hy) - rows + 1, x, CAT_POSES[pose])
        return
    art = LEGACY_ART[pose]
    for i, line in enumerate(art):
        safe_addstr(win, int(hy) + i - (len(art) - 1), x, line, cp(C_WARN, True))


def _platform_height(i, seed):
    """Deterministic per-run height so the world doesn't shimmer."""
    rng = random.Random(seed * 1000 + i)
    return rng.choice([0, 1, 2, 2, 3, 4])


def _layout(stdscr):
    h, w = stdscr.getmaxyx()
    base_row = h - 4
    return h, w, base_row


def _draw_world(stdscr, words, current, seed, hero_pos, hero_pose, kitty,
                lives, streak, typed, msg=None):
    h, w, base_row = _layout(stdscr)
    stdscr.erase()

    center(stdscr, 0, "P L A T F O R M   J U M P E R", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Platform %d/%d" % (min(current + 1, RUN_LENGTH), RUN_LENGTH),
                cp(C_WARN, True))
    safe_addstr(stdscr, 1, 22, "Streak %d" % streak, cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 38, "Lives " + "<3 " * max(0, lives), cp(C_WRONG, True))

    cam = max(0, current - 1)

    for i in range(cam, min(len(words), cam + VISIBLE)):
        px = 4 + (i - cam) * SLOT_W
        py = base_row - _platform_height(i, seed)
        done = i < current
        attr = cp(C_CORRECT) if done else cp(C_PENDING, True)
        safe_addstr(stdscr, py, px, "=" * (SLOT_W - 4), attr)
        label = words[i]
        if done:
            safe_addstr(stdscr, py - 1, px, label[: SLOT_W - 4], cp(C_CORRECT))
        elif i > current:
            safe_addstr(stdscr, py - 1, px, label[: SLOT_W - 4], cp(C_PENDING))

    # The word you're currently typing, big and centered up top
    target = words[current] if current < len(words) else ""
    if target:
        center(stdscr, 4, "JUMP TO:", cp(C_PENDING))
        x = max(0, (w - len(target)) // 2)
        ui.draw_typing_line(stdscr, 5, x, target, typed)

    hx, hy = hero_pos
    _draw_hero(stdscr, kitty, hero_pose, hx, hy)

    safe_addstr(stdscr, base_row + 2, 0, "~" * max(0, w - 1), cp(C_PENDING))

    if msg:
        center(stdscr, 7, msg, cp(C_WRONG, True))

    center(stdscr, h - 1, "no backspace -- type it right the first time   -   ESC to quit",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def _hero_anchor(index, current, seed, stdscr):
    h, w, base_row = _layout(stdscr)
    cam = max(0, current - 1)
    px = 4 + (index - cam) * SLOT_W
    py = base_row - _platform_height(index, seed)
    return px + 2, py


def _animate_jump(stdscr, words, frm, to, seed, lives, streak, draw):
    x0, y0 = _hero_anchor(frm, to, seed, stdscr)
    x1, y1 = _hero_anchor(to, to, seed, stdscr)
    steps = 12
    for s in range(steps + 1):
        t = s / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t - 6 * (t - t * t) * 2  # parabolic arc
        if s == steps:
            fx.spawn("puff", y1 + 1, x1)   # dust on a stuck landing
        draw((x, y), "leap" if s < steps else "stand")
        curses.napms(28)
    for _ in range(6):                      # let the dust settle
        draw((x1, y1), "stand")
        curses.napms(28)


def _animate_fall(stdscr, pos, draw):
    h, w, base_row = _layout(stdscr)
    x, y = pos
    while y < base_row + 3:
        y += 1.4
        draw((x, y), "fall")
        curses.napms(35)


def play(stdscr, profile):
    level = profile.get("rocket_level", 1)
    seed = random.randrange(10000)
    words = [lessons.random_word(level) for _ in range(RUN_LENGTH + 1)]
    kitty = cat.Cat.from_profile(profile)   # None for a profile with no cat

    current = 0
    typed = ""
    lives = LIVES
    streak = 0
    best_streak = 0
    falls = 0
    sess = engine.Session()

    curses.curs_set(0)
    stdscr.nodelay(False)
    fx.clear()

    while current < RUN_LENGTH and lives > 0:
        pos = _hero_anchor(current, current, seed, stdscr)

        def draw(p=pos, pose="stand", msg=None):
            _draw_world(stdscr, words, current, seed, p, pose, kitty,
                        lives, streak, typed, msg)

        draw()
        key = stdscr.getch()

        if engine.is_quit(key):
            break
        if not engine.is_typable(key):
            continue

        ch = chr(key)
        target = words[current]

        if ch == target[len(typed)]:
            typed += ch
            sess.keystroke(True)

            if typed == target:
                sess.word_done()
                streak += 1
                best_streak = max(best_streak, streak)
                nxt = current + 1

                def jdraw(p, pose):
                    _draw_world(stdscr, words, current, seed, p, pose, kitty,
                                lives, streak, "")

                _animate_jump(stdscr, words, current, nxt, seed, lives, streak, jdraw)
                current = nxt
                typed = ""
        elif shop.take_effect(profile, shop.EFFECT_SHIELD):
            # The treat forgives exactly one slip: the cat wobbles, the
            # kid keeps their footing, and the word carries on. It never
            # types the letter for them.
            sess.keystroke(False)
            draw(pos, "leap", "The treat saved you! Keep going.")
            curses.napms(700)
        else:
            sess.keystroke(False)
            falls += 1
            lives -= 1
            streak = 0

            def fdraw(p, pose):
                _draw_world(stdscr, words, current, seed, p, pose, kitty,
                            lives, streak, typed,
                            msg="You slipped! It was '%s'" % target)

            _animate_fall(stdscr, pos, fdraw)
            typed = ""
            if lives > 0:
                ui.message(
                    stdscr,
                    ["You fell, but you climb back up.",
                     "",
                     "Lives left: %d" % lives,
                     "",
                     "Read the whole word before you start typing."],
                    title="SPLASH!",
                )

    sess.finish()

    cleared = current
    perfect = falls == 0 and cleared >= RUN_LENGTH

    if best_streak > profile.get("platformer_best_streak", 0):
        profile["platformer_best_streak"] = best_streak
    if perfect:
        profile["platformer_perfect_runs"] = profile.get("platformer_perfect_runs", 0) + 1

    if perfect:
        title = "PERFECT RUN!"
        lines = ["You cleared all %d platforms without falling once." % RUN_LENGTH]
    elif cleared >= RUN_LENGTH:
        title = "YOU MADE IT!"
        lines = ["Cleared all %d platforms with %d fall(s)." % (RUN_LENGTH, falls)]
    else:
        title = "RUN OVER"
        lines = ["You cleared %d of %d platforms." % (cleared, RUN_LENGTH)]

    lines += [
        "",
        "Best streak: %d" % best_streak,
        "Accuracy: %.1f%%" % sess.accuracy,
        "WPM: %.1f" % sess.wpm,
    ]
    # The kid's cat takes the bow too -- overjoyed if the run went well,
    # sitting if it didn't. Same fallback as the jumper itself.
    if kitty is not None:
        art = kitty.art("overjoyed" if cleared >= RUN_LENGTH else "sit")
    else:
        art = HERO_JUMP
    ui.message(stdscr, lines, title=title, art=art)

    return sess.summary()
