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
import random
import sys
from datetime import date

from core import profiles, badges, ui, lessons, adaptive, cat, engine
from core.ui import (cp, center, safe_addstr, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_BADGE, C_DEFAULT)
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


EGG = [
    "   .---.   ",
    "  /     \\  ",
    " |       | ",
    " |       | ",
    "  \\     /  ",
    "   '---'   ",
]

# Where the shell gives way, in order. Roughly a fissure down the middle
# that branches as it goes -- the last one splits the egg in half.
CRACKS = [
    (2, 5, "\\"), (2, 6, "/"), (3, 5, "/"), (3, 4, "\\"),
    (1, 5, "."), (4, 5, "V"), (2, 4, "_"), (3, 6, "_"),
    (1, 4, "\\"), (1, 6, "/"), (4, 4, "\\"), (4, 6, "/"),
]


def _draw_egg(stdscr, top, x, cracks, attr, crack_attr):
    rows = [list(r) for r in EGG]
    hot = set()
    for i, (ry, rx, ch) in enumerate(CRACKS[:cracks]):
        rows[ry][rx] = ch
        hot.add((ry, rx))
    for ry, row in enumerate(rows):
        safe_addstr(stdscr, top + ry, x, "".join(row), attr)
        for rx in range(len(row)):
            if (ry, rx) in hot:
                safe_addstr(stdscr, top + ry, x + rx, row[rx], crack_attr)


def _egg_burst(stdscr, top, x):
    for step in range(4):
        stdscr.erase()
        ch = "*" if step < 2 else "."
        for dy, dx in ((-1, 0), (1, 0), (0, -3), (0, 3),
                       (-1, -3), (-1, 3), (1, -3), (1, 3)):
            safe_addstr(stdscr, top + 3 + dy * (step + 1) // 2,
                        x + 5 + dx * (step + 1), ch, cp(C_WARN, True))
        center(stdscr, top + 3, "-" * (step + 1) * 2, cp(C_WARN, True))
        stdscr.refresh()
        curses.napms(100)


def hatch_ceremony(stdscr, profile):
    """
    Profile creation, rewritten as the game's thesis: typing makes things
    happen. Their very first keystrokes crack the shell.

    It never traps a kid -- ESC skips straight to the reveal, wrong keys
    only wobble the egg, and the cat is theirs either way. Siblings are
    waiting for the keyboard, so the whole thing is well under a minute.
    """
    rng = random.Random()
    seed = cat.new_seed(rng)
    target = " ".join(rng.sample(lessons.get_level(1)["words"], 3))
    typed = ""
    wobble_until = 0
    frame = 0

    stdscr.nodelay(True)
    try:
        while len(typed) < len(target):
            h, w = stdscr.getmaxyx()
            top = max(2, h // 2 - 7)
            sway = (0, 1, 0, -1)[(frame // 6) % 4]
            if frame < wobble_until:
                sway += 1 if frame % 2 else -1
            x = max(0, (w - len(EGG[0])) // 2 + sway)

            stdscr.erase()
            center(stdscr, top - 1, "SOMETHING IS IN HERE", cp(C_TITLE, True))
            cracks = int(len(CRACKS) * len(typed) / max(1, len(target)))
            _draw_egg(stdscr, top, x, cracks, cp(C_DEFAULT, True), cp(C_WARN, True))

            center(stdscr, top + 8, "Type this to crack the shell:", cp(C_PENDING))
            tx = max(0, (w - len(target)) // 2)
            ui.draw_typing_line(stdscr, top + 9, tx, target, typed)
            center(stdscr, min(h - 2, top + 12), "ESC to skip ahead", cp(C_PENDING))
            stdscr.refresh()

            key = stdscr.getch()
            if key == -1:
                curses.napms(45)
                frame += 1
                continue
            if engine.is_quit(key):
                break
            if not engine.is_typable(key):
                continue
            if chr(key) == target[len(typed)]:
                typed += chr(key)
            else:
                wobble_until = frame + 8  # a miss rocks the egg, never hurts it
    finally:
        stdscr.nodelay(False)

    h, w = stdscr.getmaxyx()
    _egg_burst(stdscr, max(2, h // 2 - 7), max(0, (w - len(EGG[0])) // 2))

    kitten = cat.Cat(seed, growth=0)
    ui.message(
        stdscr,
        ["A kitten!", "", kitten.describe("It")],
        title="IT HATCHED",
        art=kitten.art("overjoyed", growth=0),
    )

    name = ui.ask_text(stdscr, "What will you call your cat?", maxlen=12)
    kitten.name = name or "Kitty"
    profile["cat"] = cat.blank_cat_data(seed, kitten.name, date.today().isoformat())

    stdscr.erase()
    h, w = stdscr.getmaxyx()
    top = max(2, h // 2 - 4)
    art_w = kitten.width("sit", 0)
    cat_x = max(0, (w - art_w) // 2)
    kitten.draw(stdscr, top + 3, cat_x, "sit", growth=0)

    greeting = "Hi %s! I'm %s." % (profile["name"], kitten.name)
    tail_x = 3
    ui.speech_bubble(stdscr, top,
                     max(0, min(w - len(greeting) - 4,
                                cat_x + art_w // 2 - tail_x)),
                     [greeting], cp(C_ACCENT, True), tail_x=tail_x)
    center(stdscr, min(h - 2, top + 10), "press any key", cp(C_PENDING))
    stdscr.refresh()
    stdscr.getch()
    return profile["cat"]


def offer_hatch(stdscr, all_profiles, profile):
    """
    A save from before the cat existed. Offer, never impose -- and only
    once per login, because nagging is the exact pattern we ruled out.
    """
    choice = ui.menu(
        stdscr,
        "There's an egg here with your name on it",
        ["Hatch it!", "Not right now"],
        subtitle="%s, do you want a cat?" % profile["name"],
    )
    if choice == 0:
        hatch_ceremony(stdscr, profile)
        profiles.save_all(all_profiles)


def pick_profile(stdscr, all_profiles):
    while True:
        names = sorted(all_profiles.keys())
        options = names + ["+ New player"]
        if names:
            options.append("Delete a player")
        options.append("Quit")

        # Cats double as profile icons -- on a shared device the glyph is
        # how a kid spots their own row before they can read the names.
        icons = []
        for n in names:
            c = cat.Cat.from_profile(all_profiles[n])
            icons.append((c.glyph(), c.body_attr) if c else None)
        icons += [None] * (len(options) - len(names))

        choice = ui.menu(
            stdscr,
            "Who's typing?",
            options,
            subtitle="pick your name",
            art=TITLE_ART,
            footer="up/down to move   ENTER to pick",
            option_icons=icons,
        )
        if choice == -1:
            return None

        if choice < len(names):
            return names[choice]

        picked = options[choice]
        if picked == "+ New player":
            name = ui.ask_text(stdscr, "What's your name?", maxlen=14)
            if name:
                profile = profiles.get_or_create(all_profiles, name)
                if not profile.get("cat"):
                    hatch_ceremony(stdscr, profile)
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


KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def draw_keyboard(stdscr, top, profile):
    """
    The heatmap: the kid's own keyboard, greening up as they master it.
    Cheapest, loudest "look how much better you are" display we have.
    """
    unlocked = adaptive.alphabet(profile)
    focus = adaptive.focus_letter(profile)
    x0 = 6

    head = "YOUR KEYBOARD"
    safe_addstr(stdscr, top, x0, head, cp(C_ACCENT, True))
    safe_addstr(stdscr, top, x0 + 17,
                "%d of 26 letters unlocked" % len(unlocked), cp(C_PENDING))
    if focus:
        safe_addstr(stdscr, top, x0 + 46,
                    "working on: %s" % focus.upper(), cp(C_WARN, True))

    attrs = {
        "green": cp(C_CORRECT, True),
        "learning": cp(C_WARN, True),
        "locked": cp(C_PENDING) | curses.A_DIM,
    }
    for r, row in enumerate(KEY_ROWS):
        for i, ch in enumerate(row):
            attr = attrs[adaptive.key_state(profile, ch)]
            if ch == focus:
                attr |= curses.A_REVERSE
            safe_addstr(stdscr, top + 1 + r, x0 + r + i * 2, ch.upper(), attr)

    legend = top + 1 + len(KEY_ROWS)
    safe_addstr(stdscr, legend, x0, "green = mastered", cp(C_CORRECT))
    safe_addstr(stdscr, legend, x0 + 20, "yellow = learning", cp(C_WARN))
    safe_addstr(stdscr, legend, x0 + 42, "blue = not yet", cp(C_PENDING))


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

    draw_keyboard(stdscr, min(h - 7, 16), profile)

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


def announce_letters(stdscr, profile, letters):
    """
    A new letter is information, not a prize: it says "the ones you had
    are solid, here's the next one." No score, no payout.
    """
    for ch in letters:
        ui.message(
            stdscr,
            [
                "Every letter you had went green,",
                "so your keyboard just grew one more.",
                "",
                "%d of 26 letters unlocked" % len(adaptive.alphabet(profile)),
            ],
            title="NEW LETTER: %s" % ch.upper(),
            art=["", "   [ %s ]   " % ch.upper(), ""],
        )


def after_session(stdscr, all_profiles, profile, mode_name, summary):
    progress = {"green": [], "unlocked": []}
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
        progress = adaptive.merge_keys(profile, summary.get("keys"))
    fresh = badges.check_new(profile)
    profiles.save_all(all_profiles)
    announce_letters(stdscr, profile, progress["unlocked"])
    if fresh:
        celebrate_badges(stdscr, fresh)


POSE_TICKS = 36   # ~4s at the menu's 110ms idle tick
BUBBLE_MAX = 14   # keeps the bubble clear of the centred menu labels


def menu_cat_painter(profile):
    """
    The cat living in the corner of the menu. Returns a `draw_extra` for
    ui.menu, or None for a profile with no cat -- in which case the menu
    is exactly the menu it always was.
    """
    c = cat.Cat.from_profile(profile)
    if c is None:
        return None
    state = {"pose": "sit", "line": "Hi, %s!" % profile["name"], "ticks": 0}

    def paint(win):
        h, w = win.getmaxyx()
        state["ticks"] += 1
        if state["ticks"] % POSE_TICKS == 0:
            state["pose"] = c.next_idle()
            state["line"] = c.says(state["pose"])

        pose = state["pose"]
        art_w, art_h = c.width(pose), c.height(pose)
        x = max(0, w - art_w - 4)
        y = max(0, h - art_h - 1)

        # The bubble sits three rows up, beside the short menu labels
        # rather than the long ones, and is capped so a long name can't
        # push it left into them.
        line = state["line"][:BUBBLE_MAX]
        bubble_w = len(line) + 4
        bx = max(0, w - bubble_w - 2)
        ui.speech_bubble(win, max(0, y - 3), bx, [line],
                         cp(C_ACCENT), tail_x=max(1, bubble_w - 5))
        c.draw(win, y, x, pose)

    return paint


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
    if not profile.get("cat"):
        offer_hatch(stdscr, all_profiles, profile)

    paint_cat = menu_cat_painter(profile)

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
            draw_extra=paint_cat,
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
