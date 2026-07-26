#!/usr/bin/env python3
"""
Typing Tutor -- offline, gamified typing practice for kids.

Stdlib only. Designed to be PID 1's only job on a Buildroot Pi image
with wifi compiled out of the kernel, but it runs fine on any Linux
terminal.

    python3 main.py

Data lives in ./data/profiles.json (override with $TYPING_TUTOR_DATA).
"""

import curses
import sys

from core import profiles, badges, ui, lessons
from core.ui import cp, center, safe_addstr, C_TITLE, C_WARN, C_CORRECT, C_PENDING, C_ACCENT, C_BADGE
from modes import rocket, dino, platformer, memorize

BANNER = [
    " _____ _   _ ____  _____   _ _   _ ",
    "|_   _| | | |  _ \\| ____| | | | | |",
    "  | | | |_| | |_) |  _|   | | |_| |",
    "  | | |  _  |  __/| |___  |_|  _  |",
    "  |_| |_| |_|_|   |_____| (_) |_| |",
]

TITLE_ART = [
    "  ___________  ______  _   _  _____ ",
    " |_   _| ___ \\ | ___ \\| | | ||  ___|",
    "   | | | |_/ / | |_/ /| | | || |__  ",
    "   | | |  __/  |  __/ | | | ||  __| ",
    "   | | | |     | |    | |_| || |___ ",
    "   \\_/ \\_|     \\_|     \\___/ \\____/ ",
]


def pick_profile(stdscr, all_profiles):
    while True:
        names = sorted(all_profiles.keys())
        options = names + ["+ New player"]
        if names:
            options.append("Delete a player")
        options.append("Quit")

        choice = ui.menu(
            stdscr,
            "Who's typing?",
            options,
            subtitle="pick your name",
            art=TITLE_ART,
            footer="up/down to move   ENTER to pick",
        )
        if choice == -1:
            return None

        if choice < len(names):
            return names[choice]

        picked = options[choice]
        if picked == "+ New player":
            name = ui.ask_text(stdscr, "What's your name?", maxlen=14)
            if name:
                profiles.get_or_create(all_profiles, name)
                profiles.save_all(all_profiles)
                return name
        elif picked == "Delete a player":
            d = ui.menu(stdscr, "Delete which player?", names + ["cancel"])
            if d != -1 and d < len(names):
                confirm = ui.menu(
                    stdscr,
                    "Really delete %s?" % names[d],
                    ["No, keep it", "Yes, delete forever"],
                    subtitle="this erases their badges and progress",
                )
                if confirm == 1:
                    del all_profiles[names[d]]
                    profiles.save_all(all_profiles)
        elif picked == "Quit":
            return None


def show_badges(stdscr, profile):
    earned = set(profile.get("badges", []))
    idx = 0
    per_page = 8
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        center(stdscr, 0, "%s's BADGES  --  %d of %d" % (profile["name"], len(earned), len(badges.BADGES)),
               cp(C_TITLE, True))

        page = badges.BADGES[idx:idx + per_page]
        for i, b in enumerate(page):
            have = b["id"] in earned
            attr = cp(C_BADGE, True) if have else cp(C_PENDING)
            icon = b["icon"] if have else "[ ]"
            line = "%-7s %-18s %s" % (icon, b["name"], b["desc"] if have else "???")
            safe_addstr(stdscr, 3 + i, 4, line, attr)

        more = idx + per_page < len(badges.BADGES)
        center(stdscr, h - 2,
               ("more below - press SPACE   " if more else "") + "q to go back",
               cp(C_PENDING))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), 27):
            return
        if key == ord(" "):
            idx = idx + per_page if more else 0


def show_stats(stdscr, profile):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    center(stdscr, 0, "%s's STATS" % profile["name"], cp(C_TITLE, True))

    mins = profile["total_seconds"] / 60.0
    rows = [
        ("Day streak", "%d days (best %d)" % (profile["current_streak"], profile["longest_streak"])),
        ("Days practiced", "%d" % profile["days_played"]),
        ("Time typing", "%.0f minutes" % mins),
        ("Words typed", "%d" % profile["total_words"]),
        ("Best WPM", "%.1f" % profile["best_wpm"]),
        ("Best accuracy", "%.1f%%" % profile["best_accuracy"]),
        ("", ""),
        ("Rocket", "level %d, %d/7 parts" % (profile["rocket_level"], profile["rocket_parts"])),
        ("Dino high score", "%d" % profile["dino_high_score"]),
        ("Platform streak", "%d (perfect runs: %d)" % (profile["platformer_best_streak"],
                                                       profile["platformer_perfect_runs"])),
        ("Memorized", "%d passages" % profile["memorize_completions"]),
        ("Badges", "%d of %d" % (len(profile["badges"]), len(badges.BADGES))),
    ]
    for i, (label, val) in enumerate(rows):
        if not label:
            continue
        safe_addstr(stdscr, 3 + i, 6, "%-18s" % label, cp(C_PENDING))
        safe_addstr(stdscr, 3 + i, 26, val, cp(C_WARN, True))

    # last 10 sessions, so they can see the trend
    hist = profile.get("history", [])[-10:]
    if hist:
        safe_addstr(stdscr, 3, 52, "Recent runs", cp(C_ACCENT, True))
        for i, run in enumerate(hist):
            safe_addstr(stdscr, 5 + i, 52,
                        "%-10s %4.0f wpm %3.0f%%" % (run["mode"][:10], run["wpm"], run["accuracy"]),
                        cp(C_CORRECT))

    center(stdscr, h - 2, "press any key", cp(C_PENDING))
    stdscr.refresh()
    stdscr.getch()


def celebrate_badges(stdscr, new_badges):
    for b in new_badges:
        ui.message(
            stdscr,
            [b["name"], "", b["desc"]],
            title="NEW BADGE UNLOCKED",
            art=["", "    " + b["icon"] + "    ", ""],
        )


def after_session(stdscr, all_profiles, profile, mode_name, summary):
    if summary:
        profiles.record_session(
            profile,
            mode_name,
            summary["wpm"],
            summary["accuracy"],
            summary["words"],
            summary["chars"],
            summary["seconds"],
        )
    fresh = badges.check_new(profile)
    profiles.save_all(all_profiles)
    if fresh:
        celebrate_badges(stdscr, fresh)


def main_menu(stdscr, all_profiles, profile):
    first_today = profiles.touch_day(profile)
    fresh = badges.check_new(profile)
    profiles.save_all(all_profiles)

    if first_today and profile["current_streak"] > 1:
        ui.message(
            stdscr,
            ["Day %d in a row. Keep it going!" % profile["current_streak"]],
            title="WELCOME BACK, %s" % profile["name"].upper(),
        )
    if fresh:
        celebrate_badges(stdscr, fresh)

    while True:
        lvl = lessons.get_level(profile["rocket_level"])
        sub = "streak %d days  |  best %.0f wpm  |  %d badges" % (
            profile["current_streak"], profile["best_wpm"], len(profile["badges"])
        )
        choice = ui.menu(
            stdscr,
            "%s  --  Level %d: %s" % (profile["name"], profile["rocket_level"], lvl["name"]),
            [
                "Rocket Builder      (levels, build a ship)",
                "Dino Chomp          (endless, high score)",
                "Platform Jumper     (accuracy, don't fall)",
                "Memorize            (learn it by heart)",
                "My Badges",
                "My Stats",
                "Switch player",
                "Quit",
            ],
            subtitle=sub,
            art=TITLE_ART,
        )

        if choice in (-1, 7):
            return "quit"
        if choice == 6:
            return "switch"
        if choice == 4:
            show_badges(stdscr, profile)
            continue
        if choice == 5:
            show_stats(stdscr, profile)
            continue

        mode = [rocket, dino, platformer, memorize][choice]
        name = ["rocket", "dino", "platform", "memorize"][choice]
        try:
            summary = mode.play(stdscr, profile)
        except curses.error:
            ui.message(stdscr,
                       ["Your terminal is too small for that mode.",
                        "Try making the window bigger (80x24 minimum)."],
                       title="OOPS")
            summary = None
        after_session(stdscr, all_profiles, profile, name, summary)


MIN_COLS, MIN_ROWS = 80, 24


def require_size(stdscr):
    """
    The layouts assume 80x24. Rather than silently rendering something
    cramped, ask for a bigger window and redraw as they drag it. They
    can override with ENTER if they really want to squeeze.
    """
    while True:
        h, w = stdscr.getmaxyx()
        if w >= MIN_COLS and h >= MIN_ROWS:
            return
        stdscr.erase()
        center(stdscr, max(0, h // 2 - 3), "Window is a bit small", cp(C_WARN, True))
        center(stdscr, max(0, h // 2 - 1),
               "Need %dx%d, this one is %dx%d" % (MIN_COLS, MIN_ROWS, w, h),
               cp(C_PENDING))
        center(stdscr, max(0, h // 2 + 1), "Drag the window bigger, or", cp(C_PENDING))
        center(stdscr, max(0, h // 2 + 2), "shrink the font (Cmd -- on a Mac)", cp(C_PENDING))
        center(stdscr, max(0, h // 2 + 4), "ENTER to use it anyway   q to quit", cp(C_PENDING))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            return
        if key in (ord("q"), 27):
            raise SystemExit(0)
        # KEY_RESIZE and anything else just loops and redraws


def run(stdscr):
    ui.init_colors()
    curses.curs_set(0)
    stdscr.keypad(True)

    # Without this, curses waits ~1s after ESC to see if it's the start
    # of an arrow-key sequence, which makes quitting feel broken.
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)

    require_size(stdscr)

    all_profiles = profiles.load_all()

    while True:
        name = pick_profile(stdscr, all_profiles)
        if name is None:
            return
        profile = profiles.get_or_create(all_profiles, name)
        result = main_menu(stdscr, all_profiles, profile)
        profiles.save_all(all_profiles)
        if result == "quit":
            return


def main():
    if sys.version_info < (3, 6):
        print("Needs Python 3.6+")
        return 1
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
