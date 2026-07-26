"""
GHOST RACE -- two cats, one keyboard, different afternoons.

You race a *recording*, never a person. Your sister's ghost runs the
timeline she actually typed, and you run yours alongside it. Nobody has to
be in the room, nobody waits for a turn, and nothing about it can go wrong
between two kids sharing one machine.

The fairness rules are the design, not decoration:

- **You choose who to race.** The game never ranks siblings, never shows a
  leaderboard, and never volunteers who is faster. It only ever answers a
  question a kid asked by picking an opponent.
- **Racing your own ghost is a first-class option**, not a consolation for
  having no siblings. On a one-kid device it's the whole mode.
- **Nothing is at stake.** No fish, no streak, no gauges, no care state --
  this is pure free play, and a loss costs exactly nothing.
- **The end screen is gracious in both directions.** Winning doesn't gloat
  and losing doesn't sting.

Ghosts only ever record an improvement, so the thing you're chasing is
always your best and never your last.
"""

import curses
import time

from core import cat, engine, fx, ghosts, profiles, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

TRACK_LEFT = 14
COUNTDOWN = 3


def available(profile=None):
    """
    Always on: the mode has to be enterable to create the first ghost.

    Somebody has to set a pace before anybody can chase one, so hiding
    this until a ghost exists would mean no ghost ever exists. What does
    hide gracefully is opponents -- a profile with no recording for a
    passage simply isn't offered (see `ghosts.opponents`).
    """
    return bool(ghosts.PASSAGES)


def _load_others():
    """Everyone on the device, from disk. Opponents are always saved."""
    try:
        return profiles.load_all()
    except Exception:
        return {}


def _cat_for(profile):
    return cat.Cat.from_profile(profile) if profile else None


def _pick_passage(stdscr, everyone):
    rows = ghosts.raceable(everyone)
    options = []
    for _key, name, _words, runners in rows:
        if runners:
            note = "%d ghost%s" % (runners, "" if runners == 1 else "s")
        else:
            note = "nobody yet -- set the pace"
        options.append("%-18s(%s)" % (name, note))
    options.append("Never mind")

    choice = ui.menu(stdscr, "P I C K   A   T R A C K", options,
                     subtitle="which words do you want to race?")
    if choice == -1 or choice >= len(rows):
        return None
    key, name, words, _ = rows[choice]
    return key, name, words


def _pick_opponent(stdscr, everyone, me, key):
    runners = ghosts.opponents(everyone, me, key)
    if not runners:
        ui.message(stdscr,
                   ["Nobody has run this track yet.",
                    "",
                    "Run it now and your time becomes the ghost",
                    "everyone else races."],
                   title="SET THE PACE")
        return ("", None)

    options = []
    for name, times, is_me in runners:
        label = "Your own best" if is_me else name
        options.append("%-18s(%.1fs)" % (label, ghosts.finish_time(times)))
    options.append("Just run it, no ghost")
    options.append("Never mind")

    choice = ui.menu(stdscr, "W H O   A R E   Y O U   R A C I N G ?", options,
                     subtitle="you pick -- nobody is ranked here")
    if choice == -1 or choice >= len(options) - 1:
        return None
    if choice == len(options) - 2:
        return ("", None)
    name, times, is_me = runners[choice]
    return ("your own best" if is_me else name, times)


def _draw(stdscr, words, index, typed, my_cat, their_cat, their_name,
          their_done, elapsed, msg, countdown=None):
    h, w = stdscr.getmaxyx()
    stdscr.erase()

    center(stdscr, 0, "G H O S T   R A C E", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Word %d of %d" % (min(index + 1, len(words)),
                                                 len(words)), cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 24, "%.1fs" % elapsed, cp(C_WARN, True))

    track_w = max(10, w - TRACK_LEFT - 6)
    total = max(1, len(words))

    def lane(row, label, done, kitty, attr):
        safe_addstr(stdscr, row, 2, label[:TRACK_LEFT - 2], attr)
        safe_addstr(stdscr, row + 1, TRACK_LEFT - 1, "." * track_w,
                    cp(C_PENDING))
        x = TRACK_LEFT - 1 + int(track_w * min(1.0, done / total))
        if kitty is not None:
            kitty.draw(stdscr, row + 1 - kitty.height("pounce") + 1,
                       min(x, w - kitty.width("pounce") - 1), "pounce")
        else:
            safe_addstr(stdscr, row + 1, min(x, w - 4), "(_)", attr)
        safe_addstr(stdscr, row + 1, w - 5, "%d/%d" % (done, total),
                    cp(C_PENDING))

    lane(4, "You", index, my_cat, cp(C_CORRECT, True))
    if their_cat is not None or their_name:
        lane(10, their_name or "ghost", their_done, their_cat,
             cp(C_WARN, True))

    row = min(h - 6, 16)
    if countdown is not None:
        center(stdscr, row, "Ready... %d" % countdown, cp(C_WARN, True))
    else:
        target = words[index] if index < len(words) else ""
        if target:
            center(stdscr, row - 2, "Type it:", cp(C_PENDING))
            tx = max(0, (w - len(target)) // 2)
            ui.draw_typing_line(stdscr, row, tx, target, typed)

    if msg:
        center(stdscr, row + 3, msg, cp(C_ACCENT, True))

    center(stdscr, h - 1, "ESC to stop -- nothing is at stake here",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def play(stdscr, profile):
    everyone = _load_others()
    me = profile.get("name", "")
    # The in-memory profile is fresher than disk for the kid playing.
    everyone[me] = profile

    picked = _pick_passage(stdscr, everyone)
    if not picked:
        return None
    key, track_name, words = picked

    chosen = _pick_opponent(stdscr, everyone, me, key)
    if chosen is None:
        return None
    their_name, their_times = chosen

    my_cat = _cat_for(profile)
    their_cat = None
    if their_name and their_name != "your own best":
        their_cat = _cat_for(everyone.get(their_name))
    elif their_name:
        their_cat = my_cat

    sess = engine.Session()
    index = 0
    typed = ""
    splits = []
    msg = ""

    curses.curs_set(0)
    fx.clear()

    # Countdown, so the clock never starts while a kid is still reading.
    stdscr.nodelay(True)
    for n in range(COUNTDOWN, 0, -1):
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            _draw(stdscr, words, 0, "", my_cat, their_cat, their_name, 0,
                  0.0, "", countdown=n)
            if engine.is_quit(stdscr.getch()):
                stdscr.nodelay(False)
                return None
            curses.napms(33)

    started = time.monotonic()
    quit_early = False

    while index < len(words):
        now = time.monotonic()
        elapsed = now - started
        their_done = ghosts.position(their_times, elapsed) if their_times else 0

        _draw(stdscr, words, index, typed, my_cat, their_cat, their_name,
              their_done, elapsed, msg)

        while True:
            key_in = stdscr.getch()
            if key_in == -1:
                break
            if engine.is_quit(key_in):
                quit_early = True
                break
            if engine.is_backspace(key_in):
                typed = typed[:-1]
                continue
            if not engine.is_typable(key_in):
                continue

            ch = chr(key_in)
            target = words[index]
            expected = target[len(typed)] if len(typed) < len(target) else None
            if expected is not None and ch == expected:
                typed += ch
                sess.keystroke(True, ch=expected)
                if typed == target:
                    sess.word_done()
                    splits.append(time.monotonic() - started)
                    index += 1
                    typed = ""
                    fx.spawn("spark", 5, TRACK_LEFT + index * 3)
            else:
                sess.keystroke(False, ch=expected)
                msg = "keep going -- backspace to fix"

        if quit_early:
            break

        curses.napms(33)

    stdscr.nodelay(False)
    sess.finish()

    if quit_early or index < len(words):
        ui.message(stdscr, ["Race stopped -- no harm done.", "",
                            "Nothing here was riding on it."],
                   title="MAYBE LATER")
        return sess.summary()

    my_time = splits[-1] if splits else 0.0
    improved = ghosts.record(profile, key, splits)

    lines = ["%s -- %.1f seconds" % (track_name, my_time)]
    if their_times:
        theirs = ghosts.finish_time(their_times)
        margin = abs(my_time - theirs)
        if my_time < theirs:
            title = "YOU WON!"
            lines += ["", "%s finished in %.1fs." % (their_name, theirs),
                      "You were %.1fs quicker." % margin]
        elif margin < 1.0:
            title = "SO CLOSE!"
            lines += ["", "%s finished in %.1fs." % (their_name, theirs),
                      "Less than a second in it. Rematch tomorrow?"]
        else:
            title = "GOOD RACE"
            lines += ["", "%s finished in %.1fs." % (their_name, theirs),
                      "Rematch tomorrow?"]
    else:
        title = "PACE SET"
        lines += ["", "You're the ghost now -- that's the time to beat."]

    if improved:
        lines += ["", "That's your best run on this track."]

    ui.message(stdscr, lines, title=title,
               art=my_cat.art("overjoyed") if my_cat else None)
    return sess.summary()
