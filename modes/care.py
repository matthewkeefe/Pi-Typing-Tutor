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
import time

from core import cat, engine, fx, lessons, shop, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG, C_DEFAULT)
from modes import feed

BOARD_BONUS = 10     # fish for looking after everything
COMEBACK_BONUS = 15  # extra, on the first full day back after a wary spell

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


# --- the wary cat: winning it back -----------------------------------
#
# After days alone the cat sits back and watches before it lets you get
# on with things. This is honest pet education -- real cats are exactly
# like this -- but the research is unambiguous that punishment dynamics
# hit kids harder than adults, and that the comeback moment is precisely
# where a lapsed kid quits for good. So the rules are strict:
#
#   * A swat costs SECONDS. Nothing in this section may deduct lives,
#     score, fish, streaks, gauges or any progress -- and it doesn't:
#     the only profile writes here are the wary flags themselves.
#   * It is always winnable. The distance is hard-capped, and the bar for
#     calming the cat drops every attempt until anyone clears it.
#   * The cat is wary, never hostile. "Not yet, slow down" -- not "no".

WARY_START_DISTANCE = 4
WARY_MAX_DISTANCE = 6        # hard cap, so it can never run away from you
WARY_BASE_EVENNESS = 0.45    # steadiness needed at the first attempt...
WARY_MERCY = 0.06            # ...falling this much per attempt, forever

CALM_PHRASES = ["easy now", "hello you", "it's me", "good cat", "no rush"]


def _wary_scene(stdscr, kitty, distance, target, typed, swatted, note):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    center(stdscr, 0, "S L O W L Y   N O W", cp(C_TITLE, True))
    center(stdscr, 1, "type gently and evenly -- %s is deciding about you"
           % (kitty.name if kitty else "the cat"), cp(C_PENDING))

    # The cat literally sits further away the warier it is.
    floor_row = 9
    cat_x = max(2, w // 2 - 6 + distance * 5)
    safe_addstr(stdscr, floor_row, 2, "." * max(0, w - 4), cp(C_PENDING))
    if kitty:
        pose = "swat" if swatted else ("wary" if distance else "overjoyed")
        # Drawn after the floor so it stands on the ground, not under it.
        kitty.draw(stdscr, floor_row - kitty.height(pose), cat_x, pose)

    bar = "  ".join("." * distance) or "(right here)"
    center(stdscr, floor_row + 2, bar, cp(C_WARN))
    center(stdscr, floor_row + 3, note, cp(C_ACCENT, True) if note else 0)

    tx = max(0, (w - len(target)) // 2)
    ui.draw_typing_line(stdscr, floor_row + 6, tx, target, typed)
    center(stdscr, h - 1, "nothing here can go wrong -- ESC to step away",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def win_it_back(stdscr, profile):
    """
    Coax a wary cat back. Always succeeds eventually; the only currency
    is patience.

    Deliberately returns nothing and records no session: the beat is a
    warm-up, not practice for credit, which keeps the "costs seconds
    only" guarantee true by construction rather than by care.
    """
    kitty = cat.Cat.from_profile(profile)
    rng = random.Random()
    distance = WARY_START_DISTANCE
    attempts = 0
    swatted = False
    note = "%s is keeping %s distance." % (
        kitty.name if kitty else "The cat", kitty.their if kitty else "their")

    curses.curs_set(0)
    stdscr.nodelay(False)
    fx.clear()

    while distance > 0:
        target = rng.choice(CALM_PHRASES)
        typed = ""
        clean = True
        marks = []
        last = None

        while typed != target:
            _wary_scene(stdscr, kitty, distance, target, typed, swatted, note)
            key = stdscr.getch()
            if engine.is_quit(key):
                return False          # stepping away costs nothing at all
            if engine.is_backspace(key):
                typed = typed[:-1]
                continue
            if not engine.is_typable(key):
                continue

            now = time.monotonic()
            if last is not None:
                marks.append((now - last) * 1000.0)
            last = now

            expected = target[len(typed)]
            if chr(key) == expected:
                typed += chr(key)
                swatted = False
            else:
                clean = False

        attempts += 1
        # The bar drops every time, so however this is going, it resolves.
        needed = max(0.0, WARY_BASE_EVENNESS - attempts * WARY_MERCY)
        steady = engine.evenness(marks) >= needed

        if clean and steady:
            distance -= 1
            swatted = False
            note = ("%s comes a little closer."
                    % (kitty.name if kitty else "The cat")) if distance else ""
        else:
            # A swat is a warning, not a punishment: it adds a few
            # keystrokes and takes nothing.
            distance = min(WARY_MAX_DISTANCE, distance + 1)
            swatted = True
            note = "*swat* -- not yet. Slower."
            h, w = stdscr.getmaxyx()
            fx.spawn("bang", 5, max(2, w // 2 - 6 + distance * 5))

    cat.mark_wary_won(profile)
    if kitty:
        for _ in range(3):
            fx.spawn("purr", 4, stdscr.getmaxyx()[1] // 2)
    ui.message(
        stdscr,
        ["%s bumps %s head against your hand." % (
            kitty.name if kitty else "The cat",
            kitty.their if kitty else "their"),
         "",
         "Friends again. That's all it wanted."],
        title="PURRRR",
        art=kitty.art("overjoyed") if kitty else None,
    )
    fx.clear()
    return True


# --- the board -------------------------------------------------------


TASK_RUNNERS = {"water": water, "pets": pets, "clean": clean}


def _board_painter(profile, kitty):
    # `idx` is the highlighted row, which this painter doesn't need -- but
    # ui.menu passes it to every draw_extra, so the signature has to take
    # it. Phase 5 added the argument for the shop painter and this one was
    # never updated, which crashed the care board on entry for four
    # phases. See tests/test_painters.py, which now checks all three.
    def paint(win, idx=0):
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
        was_wary = cat.wary_active(profile)

        # The two tasks that need the cat's cooperation are the two it
        # holds back from. Food, water and the litter box happen whatever
        # it thinks of you -- being wary never blocks care.
        if task in ("pets", "play") and cat.needs_win_back(profile):
            if not win_it_back(stdscr, profile):
                continue

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
            bonus = BOARD_BONUS
            lines = ["Food, water, pets, play and a clean box.",
                     "",
                     "%s is delighted with you." % name]
            title = "%s IS ALL SET" % name.upper()

            if was_wary:
                # A comeback day has to end WARMER than a normal day --
                # this is exactly the moment a lapsed kid decides whether
                # to come back tomorrow. Unconditional, and additive only.
                cat.clear_wary(profile)
                bonus += COMEBACK_BONUS
                lines = ["%s missed you." % name,
                         "",
                         "Everything's looked after, and it's curled up",
                         "on your feet like nothing ever happened."]
                title = "WELCOME BACK"

            profile["fish"] = profile.get("fish", 0) + bonus
            after_task("care-bonus", None)
            ui.celebrate(
                stdscr,
                lines + ["", "+%d fish   --   everything's open now" % bonus],
                title=title,
                art=kitty.art("overjoyed") if kitty else None,
            )
            return
