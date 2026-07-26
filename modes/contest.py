"""
THE CONTEST LADDER -- five cups, three trials each.

A cup is one continuous run: type as many words as you can in sixty
seconds, and the three bars are read off that same run. Speed, accuracy
and endurance are three ways of looking at one performance rather than
three separate rounds, which keeps an entry short enough to be a
highlight rather than an evening.

What this mode is careful about:

- **It never compares kids.** No leaderboard, no other profile is even
  loaded. A rank says something about you and the game's bar, and cannot
  become a statement about you and your sister. Same invariant as ghost
  racing.
- **Losing costs the entry and nothing else.** No fish taken, no rank
  lost, no streak touched. The tip names the trial that missed, never the
  kid.
- **Ranks only rise.** Win the Junior Cup and have a bad month, and
  you're still a Junior.

The sixty-second burst is also free play: `daily_dash` runs the same loop
with no bars and nothing riding on it, which is what #28 asks for when it
says the trial should double as a mode.
"""

import curses
import time

from core import adaptive, cat, contests, engine, fx, scrapbook, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

ROUND_SECONDS = 60.0


def available(profile=None):
    return True


def _draw(stdscr, kitty, pose, target, typed, done, remaining, cup_row,
          msg, dash):
    h, w = stdscr.getmaxyx()
    stdscr.erase()

    title = "D A I L Y   D A S H" if dash else cup_row[1].upper()
    center(stdscr, 0, title, cp(C_TITLE, True))

    safe_addstr(stdscr, 1, 2, "Words %d" % done, cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 18, "%4.1fs left" % max(0.0, remaining),
                cp(C_WARN, True))
    if not dash:
        _key, _name, wpm_bar, acc_bar, endurance = cup_row
        safe_addstr(stdscr, 1, 34,
                    "aiming for %.0f wpm / %.0f%% / %d words"
                    % (wpm_bar, acc_bar, endurance), cp(C_PENDING))

    # A gauge, not a countdown clock. Same reasoning as the soup cooling:
    # this is time passing, not a threat.
    width = min(40, max(10, w - 30))
    filled = int(round(width * max(0.0, remaining) / ROUND_SECONDS))
    safe_addstr(stdscr, 3, max(2, (w - width - 2) // 2),
                "[" + "=" * filled + " " * (width - filled) + "]",
                cp(C_CORRECT if filled > width // 3 else C_WARN, True))

    if kitty is not None:
        kitty.draw(stdscr, 5, max(2, w // 2 - kitty.width(pose) - 14), pose)

    row = min(h - 8, 10)
    center(stdscr, row - 2, "Type!", cp(C_PENDING))
    if target:
        tx = max(0, (w - len(target)) // 2)
        ui.draw_typing_line(stdscr, row, tx, target, typed)

    if msg:
        center(stdscr, row + 3, msg, cp(C_ACCENT, True))

    center(stdscr, h - 1, "ESC to stop -- nothing is taken away",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def _burst(stdscr, profile, cup_row, dash):
    """
    The sixty-second run. Returns (summary, words_done).

    Shared by the cups and the Daily Dash -- the only difference is
    whether anything is being measured against a bar afterwards.
    """
    kitty = cat.Cat.from_profile(profile)
    sess = engine.Session()
    words = adaptive.generate_lesson(profile, 80)
    idx = 0
    typed = ""
    done = 0
    pose = "sit"
    pose_until = 0.0
    msg = ""
    species = []

    curses.curs_set(0)
    stdscr.nodelay(True)
    fx.clear()

    started = time.monotonic()
    running = True

    while running:
        now = time.monotonic()
        remaining = ROUND_SECONDS - (now - started)
        if remaining <= 0:
            break
        if pose_until and now > pose_until:
            pose, pose_until = "sit", 0.0

        target = words[idx % len(words)]
        _draw(stdscr, kitty, pose, target, typed, done, remaining, cup_row,
              msg, dash)

        while True:
            key = stdscr.getch()
            if key == -1:
                break
            if engine.is_quit(key):
                running = False
                break
            if engine.is_backspace(key):
                typed = typed[:-1]
                continue
            if not engine.is_typable(key):
                continue

            ch = chr(key)
            expected = target[len(typed)] if len(typed) < len(target) else None
            if expected is not None and ch == expected:
                typed += ch
                sess.keystroke(True, ch=expected)
                if typed == target:
                    sess.word_done()
                    done += 1
                    species.extend(scrapbook.catch_from_word(profile, target))
                    idx += 1
                    typed = ""
                    pose, pose_until = "pounce", now + 0.25
                    if done % 10 == 0:
                        fx.spawn("spark", 5, stdscr.getmaxyx()[1] // 2)
            else:
                sess.keystroke(False, ch=expected)
                msg = "backspace and fix it"

        curses.napms(33)

    stdscr.nodelay(False)
    sess.finish()
    summary = sess.summary()
    if species:
        summary["species"] = species
    return summary, done


def daily_dash(stdscr, profile):
    """Sixty seconds, no bars, nothing riding on it."""
    placeholder = ("dash", "Daily Dash", 0.0, 0.0, 0)
    summary, done = _burst(stdscr, profile, placeholder, dash=True)
    kitty = cat.Cat.from_profile(profile)
    ui.message(
        stdscr,
        ["%d words in a minute." % done,
         "",
         "%.0f wpm at %.0f%% accuracy."
         % (summary["wpm"], summary["accuracy"])],
        title="TIME!",
        art=kitty.art("overjoyed") if kitty else None,
    )
    return summary


def play(stdscr, profile):
    """One entry at the cup the kid is currently working on."""
    kitty = cat.Cat.from_profile(profile)
    name = kitty.name if kitty else "Your cat"
    cup_row = contests.next_cup(profile)

    if cup_row is None:
        ui.message(
            stdscr,
            ["You've won every cup there is.",
             "",
             "%s has run out of ribbons." % name,
             "",
             "The Daily Dash is still there whenever you want it."],
            title="ALL FIVE",
            art=kitty.art("overjoyed") if kitty else None,
        )
        return None

    left = contests.entries_left(profile)
    if left <= 0:
        # The cat asks, the game doesn't refuse. Same thing mechanically,
        # entirely different to be told.
        ui.message(
            stdscr,
            ["%s flops across the keyboard." % name,
             "",
             '"Rest those paws. There\'s always tomorrow."',
             "",
             "(back for another go then)"],
            title="THAT'S ENOUGH FOR TODAY",
            art=kitty.art("loaf") if kitty else None,
        )
        return None

    key, cup_name, wpm_bar, acc_bar, endurance = cup_row
    choice = ui.menu(
        stdscr,
        cup_name.upper(),
        ["Have a go  (%d left today)" % left, "Not right now"],
        subtitle="%.0f wpm  --  %.0f%% accurate  --  %d words in a minute"
                 % (wpm_bar, acc_bar, endurance),
        panel=cat.panel(kitty, "pounce"),
        panel_title=kitty.name if kitty else None,
    )
    if choice != 0:
        return None

    if not contests.take_entry(profile):
        return None

    summary, done = _burst(stdscr, profile, cup_row, dash=False)
    results = contests.judge(cup_row, summary["wpm"], summary["accuracy"], done)

    lines = [
        "%-10s %5.0f wpm    %s" % ("Speed", summary["wpm"],
                                   "yes" if results["sprint"] else "not yet"),
        "%-10s %5.0f%%       %s" % ("Accuracy", summary["accuracy"],
                                    "yes" if results["accuracy"] else "not yet"),
        "%-10s %5d words  %s" % ("Endurance", done,
                                 "yes" if results["endurance"] else "not yet"),
    ]

    if contests.passed(results):
        index, _row = contests.cup_by_key(key)
        ribbon = contests.award(profile, index)
        fish = contests.prize_fish(index)
        profile["fish"] = profile.get("fish", 0) + fish
        if ribbon:
            scrapbook.award_ribbon(profile, ribbon)
        summary["ribbon"] = ribbon
        ui.celebrate(
            stdscr,
            lines + ["", "%s is yours." % cup_name,
                     "%d fish, and a ribbon for the scrapbook." % fish],
            title="YOU WON THE %s" % cup_name.upper(),
            art=kitty.art("overjoyed") if kitty else None,
        )
    else:
        ui.message(
            stdscr,
            lines + ["", contests.tip_for(cup_row, results),
                     "", "Nothing was lost. Have another go tomorrow."],
            title="SO CLOSE",
            art=kitty.art("sit") if kitty else None,
        )

    return summary
