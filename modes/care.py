"""
The care board and the Water / Pets / Clean micro-activities.

The board is a chore chart with a curriculum hidden inside it: each verb
trains a different micro-skill, and doing all five is the day's
distributed-practice dose, which the research says is the single most
learning-effective structure the game can have.

The kid picks the ORDER. That's not decoration -- autonomy inside
structure is the lever the gamification meta-analyses actually found for
this age group, so the board never tells anyone what to do next.

Nothing in here can be failed. No lives, no timers, no score penalties,
no game-overs. The worst outcome available is stopping early, and
whatever was done still counts.
"""

import curses
import random

from core import cat, engine, lessons, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG, C_DEFAULT)
from modes import feed

BOARD_BONUS = 10  # fish for looking after everything

PURR_PHRASES = [
    "such a good cat",
    "you are a very good cat",
    "who is a soft cat",
    "the best cat in the house",
]
PURR_REPEATS = 3
WATER_WORDS = 10
WATER_MAX_LEN = 7   # a restarting word must never become a wall to climb
CLEAN_LINES = 4


# --- a shared, unfailable typing loop --------------------------------


def _run_units(stdscr, profile, units, draw, restart_on_error=True):
    """
    Type each unit in turn. `draw(stdscr, ctx)` paints the scene.

    `restart_on_error` is the Water rule: a mistake sloshes the bowl and
    that word starts over. It costs seconds and nothing else -- there is
    no state anywhere in here that a mistake can subtract from.

    Returns (session, units_completed).
    """
    sess = engine.Session()
    idx, typed, err = 0, "", False

    curses.curs_set(0)
    stdscr.nodelay(False)
    while idx < len(units):
        target = units[idx]
        draw(stdscr, {"sess": sess, "idx": idx, "total": len(units),
                      "target": target, "typed": typed, "err": err})
        key = stdscr.getch()

        if engine.is_quit(key):
            break
        if engine.is_backspace(key):
            typed, err = typed[:-1], False
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
            if restart_on_error:
                typed = ""
            elif len(typed) < len(target):
                typed += ch

        if typed == target:
            sess.word_done()
            idx += 1
            typed, err = "", False

    sess.finish()
    return sess, idx


def _scene_header(stdscr, title, kitty, pose, subtitle):
    """
    Title, one line of guidance, and the cat watching from the left. The
    cat sits below the subtitle row on purpose -- it used to get its face
    written over by longer hints.
    """
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    center(stdscr, 0, title, cp(C_TITLE, True))
    center(stdscr, 1, subtitle, cp(C_PENDING))
    if kitty:
        kitty.draw(stdscr, 3, 6, pose)
    return h, w


def _type_line(stdscr, ctx, row):
    h, w = stdscr.getmaxyx()
    target, typed = ctx["target"], ctx["typed"]
    ui.draw_typing_line(stdscr, row, max(0, (w - len(target)) // 2), target, typed)


# --- Water: accuracy first -------------------------------------------


def water(stdscr, profile):
    """
    Fill the bowl without spilling. Errors slosh and the word restarts;
    slow is explicitly fine, so there is no timer anywhere on screen.
    """
    kitty = cat.Cat.from_profile(profile)
    rng = random.Random()
    sentences = rng.sample(lessons.get_level(7)["words"], 3)
    # A mistake restarts the word, which is the drill -- but on a long
    # word that turns into a wall for exactly the kid who needs this
    # exercise most. Keep the words short and the wall never builds.
    words = [w for w in " ".join(sentences).split() if len(w) <= WATER_MAX_LEN]
    units = words[:WATER_WORDS]

    def draw(stdscr, ctx):
        h, w = _scene_header(stdscr, "W A T E R   B O W L", kitty,
                             "swat" if ctx["err"] else "sit",
                             "type it exactly -- take all the time you like")
        level = ctx["idx"]
        bx = max(2, w // 2 - 6)
        for i in range(5):
            depth = 5 - i
            wet = level * 5 >= depth * len(units)
            safe_addstr(stdscr, 9 + i, bx,
                        "|" + ("~~~~~~~~~" if wet else "         ") + "|",
                        cp(C_PENDING, True) if wet else cp(C_DEFAULT))
        safe_addstr(stdscr, 14, bx, "'---------'", cp(C_DEFAULT))
        center(stdscr, 16, "%d of %d poured" % (level, len(units)), cp(C_WARN))
        _type_line(stdscr, ctx, 18)
        if ctx["err"]:
            center(stdscr, 20, "*slosh* -- that word again, nice and slow",
                   cp(C_WRONG, True))
        center(stdscr, h - 1, "ESC to stop", cp(C_PENDING))
        stdscr.refresh()

    sess, done = _run_units(stdscr, profile, units, draw, restart_on_error=True)
    if done:
        cat.stamp_care(profile, "water")
    _wrap_up(stdscr, kitty, done, len(units),
             "FRESH WATER", "The bowl is full and not a drop spilled.",
             "Some water in the bowl is still water in the bowl.")
    return sess.summary()


# --- Pets: rhythm and evenness ---------------------------------------


def _purr(score):
    return "p" + "u" + "r" * (2 + int(score * 10)) + "..."


def pets(stdscr, profile):
    """
    Purr rhythm: steady, even keystrokes make a bigger purr. There is no
    fail state and no threshold -- the purr is the whole score, and it is
    never described as too small.
    """
    kitty = cat.Cat.from_profile(profile)
    rng = random.Random()
    phrase = rng.choice(PURR_PHRASES)
    units = [phrase] * PURR_REPEATS

    def draw(stdscr, ctx):
        score = engine.evenness(ctx["sess"].intervals)
        h, w = _scene_header(stdscr, "P E T   T H E   C A T", kitty,
                             "loaf" if score < 0.5 else "overjoyed",
                             "type it smoothly -- an even rhythm purrs loudest")
        center(stdscr, 10, _purr(score), cp(C_ACCENT, True))
        center(stdscr, 12, "round %d of %d" % (ctx["idx"] + 1, ctx["total"]),
               cp(C_WARN))
        _type_line(stdscr, ctx, 15)
        center(stdscr, 17, "no rush and no wrong answers here", cp(C_PENDING))
        center(stdscr, h - 1, "ESC to stop", cp(C_PENDING))
        stdscr.refresh()

    sess, done = _run_units(stdscr, profile, units, draw, restart_on_error=False)
    if done:
        cat.stamp_care(profile, "pets")

    score = engine.evenness(sess.intervals)
    name = kitty.name if kitty else "Your cat"
    ui.message(
        stdscr,
        ["%s %s" % (name, _purr(score)), "",
         "Steady hands make a happy cat." if score >= 0.5
         else "Every purr counts. Smooth and slow next time."],
        title="PURRRR",
        art=kitty.art("overjoyed") if kitty else None,
    )
    return sess.summary()


# --- Clean: the keys nobody practises --------------------------------


SCOOP = ["  \\_/  ", "  \\@/  ", "  \\_/  "]


def _clean_units(rng, n=CLEAN_LINES):
    digits, punct = "1234567890", ",.!?"
    lines = []
    for _ in range(n):
        parts = ["".join(rng.choice(digits) for _ in range(rng.randint(1, 3)))
                 + rng.choice(punct) for _ in range(3)]
        lines.append(" ".join(parts))
    return lines


def clean(stdscr, profile):
    """The unglamorous keys for the unglamorous job: numbers and punctuation."""
    kitty = cat.Cat.from_profile(profile)
    units = _clean_units(random.Random())

    def draw(stdscr, ctx):
        h, w = _scene_header(stdscr, "L I T T E R   D U T Y", kitty, "sit",
                             "numbers and punctuation -- nobody's favourite, "
                             "but somebody's job")
        bx = max(2, w // 2 - 5)
        left = ctx["total"] - ctx["idx"]
        safe_addstr(stdscr, 9, bx, ".---------.", cp(C_DEFAULT))
        for i in range(3):
            grit = ("." * left).ljust(9)[:9] if i == 2 else " " * 9
            safe_addstr(stdscr, 10 + i, bx, "|" + grit + "|", cp(C_WARN))
        safe_addstr(stdscr, 13, bx, "'---------'", cp(C_DEFAULT))
        safe_addstr(stdscr, 10, bx + 13, SCOOP[ctx["idx"] % len(SCOOP)],
                    cp(C_PENDING, True))
        center(stdscr, 15, "%d of %d scoops" % (ctx["idx"], ctx["total"]), cp(C_WARN))
        _type_line(stdscr, ctx, 17)
        center(stdscr, h - 1, "ESC to stop", cp(C_PENDING))
        stdscr.refresh()

    sess, done = _run_units(stdscr, profile, units, draw, restart_on_error=False)
    if done:
        cat.stamp_care(profile, "clean")
    _wrap_up(stdscr, kitty, done, len(units),
             "ALL CLEAN", "Spotless. The cat inspects it and approves.",
             "Every scoop helps.")
    return sess.summary()


def _wrap_up(stdscr, kitty, done, total, title, full_line, partial_line):
    if not done:
        return
    ui.message(
        stdscr,
        [full_line if done >= total else partial_line],
        title=title,
        art=kitty.art("overjoyed") if kitty else None,
    )


# --- the board -------------------------------------------------------


TASK_RUNNERS = {"water": water, "pets": pets, "clean": clean}


def _board_painter(profile, kitty):
    def paint(win):
        h, w = win.getmaxyx()
        levels = cat.gauges(profile)
        top = min(h - 6, 15)  # below ui.menu's footer row, not on top of it
        safe_addstr(win, top - 1, 8, "how %s is doing" % (kitty.name if kitty else "your cat"),
                    cp(C_ACCENT, True))
        for i, task in enumerate(cat.CARE_TASKS):
            level = levels[task]
            attr = cp(C_CORRECT, True) if level >= 1.0 else cp(C_WARN)
            safe_addstr(win, top + i, 8, "%-6s %s" % (
                cat.CARE_LABELS[task], cat.gauge_bar(level)), attr)
        if kitty:
            pose = cat.mood_pose(cat.mood(profile))
            kitty.draw(win, top - 1, max(0, w - kitty.width(pose) - 6), pose)
    return paint


def board(stdscr, profile, play_slot, after_task):
    """
    The care hub. `play_slot(stdscr, profile)` runs the kid's chosen game
    for the Play task; `after_task(task, summary)` does the bookkeeping
    (fish, adaptive merge, badges, save) and owns the popups.
    """
    kitty = cat.Cat.from_profile(profile)
    name = kitty.name if kitty else "your cat"

    while True:
        left = cat.tasks_left_today(profile)
        # Every row is padded to the same width: ui.menu centres each label
        # on its own, so ragged lengths make a checklist visibly wobble.
        options = []
        for task in cat.CARE_TASKS:
            mark = " " if task in left else "x"
            options.append("[%s] %-6s %-24s" % (mark, cat.CARE_LABELS[task],
                                                cat.CARE_BLURBS[task]))
        options.append("Back to the menu".center(len(options[0])))

        choice = ui.menu(
            stdscr,
            "%s'S CARE BOARD" % name.upper(),
            options,
            subtitle=("all done for today!" if not left
                      else "%d to go -- do them in any order you like" % len(left)),
            footer="up/down to move   ENTER to pick   ESC to go back",
            draw_extra=_board_painter(profile, kitty),
        )
        if choice == -1 or choice >= len(cat.CARE_TASKS):
            return

        task = cat.CARE_TASKS[choice]
        was_done = cat.care_done_today(profile)

        if task == "food":
            summary = feed.play(stdscr, profile)
        elif task == "play":
            summary = play_slot(stdscr, profile)
            if summary:
                cat.stamp_care(profile, "play")
        else:
            summary = TASK_RUNNERS[task](stdscr, profile)

        after_task(task, summary)

        if not was_done and cat.care_done_today(profile):
            profile["fish"] = profile.get("fish", 0) + BOARD_BONUS
            after_task("care-bonus", None)
            ui.message(
                stdscr,
                ["Food, water, pets, play and a clean box.",
                 "",
                 "%s is delighted with you." % name,
                 "",
                 "+%d fish   --   everything's open now" % BOARD_BONUS],
                title="%s IS ALL SET" % name.upper(),
                art=kitty.art("overjoyed") if kitty else None,
            )
            return
