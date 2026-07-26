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

from core import (profiles, badges, ui, lessons, adaptive, cat, engine, fx,
                  shop, scrapbook, milestones, rituals, contests,
                  stasis, graduation)
from core.ui import (cp, center, safe_addstr, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_BADGE, C_DEFAULT)
from modes import (rocket, dino, platformer, memorize, care, yarn, soup,
                   pantry, mystery, quiz, race, contest, dash)

# The free-play arcade: (module, history name, label, blurb).
# play_slot builds the care board's Play choices from this same list, so a
# mode added here shows up in both places.
ARCADE = [
    (rocket, "rocket", "Rocket Builder", "levels, build a ship"),
    (dino, "dino", "Dino Chomp", "endless, high score"),
    (platformer, "platform", "Platform Jumper", "accuracy, don't fall"),
    (yarn, "yarn", "Yarn Chase", "accuracy, nothing to lose"),
    (pantry, "pantry", "Pantry Defense", "endless, defend the bowl"),
    (soup, "soup", "Alphabet Soup", "make words, beat the cooling"),
    (mystery, "mystery", "Mystery Word", "guess it, then spell it"),
    (quiz, "quiz", "Whisker Quiz", "the cat asks, you answer"),
    (race, "race", "Ghost Race", "race a recorded run"),
    (contest, "contest", "Contest Cups", "five cups, three trials each"),
    (dash, "dash", "Daily Dash", "sixty seconds, no stakes"),
    (memorize, "memorize", "Memorize", "learn it by heart"),
]

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
    """The shell letting go, as particles rather than three canned frames."""
    fx.clear()
    fx.spawn("burst", top + 3, x + 5, n=26)
    for _ in range(22):
        stdscr.erase()
        center(stdscr, top + 3, "-" * 6, cp(C_WARN, True))
        fx.tick(fx.FRAME)
        fx.draw(stdscr)
        stdscr.refresh()
        curses.napms(33)
    fx.clear()


def hatch_ceremony(stdscr, profile, parent=None, keep_existing=False):
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

    kitten = cat.Cat(seed, growth=0, parent=parent)
    ui.message(
        stdscr,
        ["A kitten!", "", kitten.describe_full()],
        title="IT HATCHED",
        art=kitten.art("overjoyed", growth=0),
    )

    name = ui.ask_text(stdscr, "What will you call your cat?", maxlen=12)
    kitten.name = name or "Kitty"
    data = cat.blank_cat_data(seed, kitten.name, date.today().isoformat(),
                              parent=parent)
    if keep_existing:
        # The cat they already have is shelved into stasis, never
        # replaced. add_cat is the only path that puts a second cat on a
        # profile, and it never drops the first.
        stasis.add_cat(profile, data)
    else:
        profile["cat"] = data

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
        "steady": cp(C_ACCENT, True),
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
    safe_addstr(stdscr, legend, x0, "green = fast", cp(C_CORRECT))
    safe_addstr(stdscr, legend, x0 + 15, "cyan = steady", cp(C_ACCENT))
    safe_addstr(stdscr, legend, x0 + 31, "yellow = learning", cp(C_WARN))
    safe_addstr(stdscr, legend, x0 + 52, "blue = not yet", cp(C_PENDING))


def show_stats(stdscr, profile):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    center(stdscr, 0, "%s's STATS" % profile["name"], cp(C_TITLE, True))

    mins = profile["total_seconds"] / 60.0

    # Milestone tracks fold into the lines that already showed the same
    # totals rather than repeating them underneath. Two "Words typed"
    # rows on one screen is how a stats page starts becoming a wall.
    track = {}
    for label, current, threshold in milestones.summary(profile):
        track[label] = ("%d" % current if threshold is None
                        else "%d  (next at %d)" % (current, threshold))

    rows = [
        ("Day streak", "%d days (best %d)" % (profile["current_streak"], profile["longest_streak"])),
        ("Days shown up", track.get("Days shown up", "%d" % profile["days_played"])),
        ("Time typing", "%.0f minutes" % mins),
        ("Words typed", track.get("Words typed", "%d" % profile["total_words"])),
        ("Letters mastered", track.get("Letters mastered", "0")),
        ("Scrapbook filled", track.get("Scrapbook filled", "0")),
        ("Best WPM", "%.1f" % profile["best_wpm"]),
        ("Best accuracy", "%.1f%%" % profile["best_accuracy"]),
        ("", ""),
    ]

    # Growth, and what the next stage is waiting on. Shown as two plain
    # counts rather than a bar: the point is that it arrives on its own
    # schedule, not that there's a meter to fill.
    # Graduation, but only once it's plausibly near. Before that it is
    # noise, and worse, it turns the whole game into a progress bar
    # pointed at one number (#34).
    if graduation.worth_showing(profile):
        green, total, median, goal = graduation.progress(profile)
        if graduation.graduated(profile):
            rows.append(("Graduated", "yes -- %s" % profile["graduated"]))
        else:
            rows.append(("Letters at speed", "%d of %d" % (green, total)))
            rows.append(("Recent pace", "-- of %.0f wpm" % goal
                         if median is None
                         else "%.0f of %.0f wpm" % (median, goal)))
        rows.append(("", ""))

    kitty_stage = cat.Cat.from_profile(profile)
    if kitty_stage is not None:
        stage = cat.GROWTH_STAGES[cat.growth(profile)]
        rows.append(("%s is a" % kitty_stage.name, cat.GROWTH_WORDS[stage]))
        nxt = cat.growth_progress(profile)
        if nxt:
            days, need_days, letters, need_letters = nxt
            rows.append(("Growing up needs",
                         "%d/%d days  and  %d/%d letters"
                         % (days, need_days, letters, need_letters)))
        rows.append(("", ""))

    rows += [
        ("Rocket", "level %d, %d/7 parts" % (profile["rocket_level"], profile["rocket_parts"])),
        ("Dino high score", "%d" % profile["dino_high_score"]),
        ("Platform streak", "%d (perfect runs: %d)" % (profile["platformer_best_streak"],
                                                       profile["platformer_perfect_runs"])),
        ("Yarn streak", "%d (perfect rounds: %d)" % (profile["yarn_best_streak"],
                                                     profile["yarn_perfect_rounds"])),
        ("Pantry high score", "%d" % profile["pantry_high_score"]),
        ("Quiz answers right", "%d" % profile["quiz_right"]),
        ("Dishes opened", "%d" % profile["mystery_opened"]),
        ("Soup words found", "%d (best score: %d)" % (profile["soup_words_found"],
                                                      profile["soup_best_score"])),
        ("Memorized", "%d passages" % profile["memorize_completions"]),
        ("Cups won", "%d of %d" % (contests.rank(profile), len(contests.CUPS))),
        ("Badges", "%d of %d" % (len(profile["badges"]), len(badges.BADGES))),
    ]
    # The heatmap is the competence lever, so it stays pinned to the
    # bottom on every page. Everything else pages above it: this screen
    # has been over capacity since Phase 6 started adding modes, and the
    # recent-runs column was quietly being drawn over.
    key_top = max(6, h - 7)
    room = max(3, key_top - 4)
    pages = [rows[i:i + room] for i in range(0, len(rows), room)] or [[]]
    page = 0

    while True:
        stdscr.erase()
        center(stdscr, 0, "%s's STATS" % profile["name"], cp(C_TITLE, True))
        if len(pages) > 1:
            safe_addstr(stdscr, 1, max(30, w - 26),
                        "page %d of %d" % (page + 1, len(pages)),
                        cp(C_PENDING))

        for i, (label, val) in enumerate(pages[page]):
            if not label:
                continue
            safe_addstr(stdscr, 3 + i, 6, "%-18s" % label, cp(C_PENDING))
            safe_addstr(stdscr, 3 + i, 26, val, cp(C_WARN, True))

        # Recent runs share the first page's right-hand column.
        hist = profile.get("history", [])[-min(10, room - 2):]
        if hist and page == 0:
            safe_addstr(stdscr, 3, 52, "Recent runs", cp(C_ACCENT, True))
            for i, run in enumerate(hist):
                safe_addstr(stdscr, 5 + i, 52,
                            "%-10s %4.0f wpm %3.0f%%"
                            % (run["mode"][:10], run["wpm"], run["accuracy"]),
                            cp(C_CORRECT))

        draw_keyboard(stdscr, key_top, profile)
        center(stdscr, h - 1,
               "left/right for more   -   any other key to close"
               if len(pages) > 1 else "press any key", cp(C_PENDING))
        stdscr.refresh()

        key = stdscr.getch()
        if len(pages) > 1 and key in (curses.KEY_RIGHT, ord("l"), ord(" ")):
            page = (page + 1) % len(pages)
        elif len(pages) > 1 and key in (curses.KEY_LEFT, ord("h")):
            page = (page - 1) % len(pages)
        else:
            return


def celebrate_badges(stdscr, new_badges):
    for b in new_badges:
        ui.celebrate(
            stdscr,
            [b["name"], "", b["desc"]],
            "NEW BADGE UNLOCKED",
            art=["", "    " + b["icon"] + "    ", ""],
        )


def announce_letters(stdscr, profile, letters):
    """
    New letters are information, not a prize: "the ones you had are
    solid, here are the next ones." No score, no payout.

    One popup for the whole batch. A strong session can be worth three
    letters now, and three popups in a row would turn the best moment in
    the game into something to click through.

    The copy no longer says "every letter went green" -- that stopped
    being true when unlocking moved to the accuracy gate. Green means
    40 wpm and is the win condition; this is the gentler bar, and saying
    otherwise would teach a kid the wrong thing about their own heatmap.
    """
    if not letters:
        return
    shown = " ".join(ch.upper() for ch in letters)
    if len(letters) == 1:
        title = "NEW LETTER: %s" % shown
        lead = ["You've got the ones you had,",
                "so your keyboard just grew."]
    else:
        title = "%d NEW LETTERS" % len(letters)
        lead = ["You've got the ones you had, easily --",
                "so your keyboard grew by %d." % len(letters)]

    ui.celebrate(
        stdscr,
        lead + ["",
                "%d of 26 letters unlocked"
                % len(adaptive.alphabet(profile))],
        title,
        art=["", "   [ %s ]   " % shown, ""],
    )


def celebrate_tricks(stdscr, profile, letters):
    """
    A key went green, so the cat learned something. This is the research's
    "perceived competence" lever wearing a cat suit -- the popup names the
    skill the kid actually gained, and the trick is kept forever.
    """
    kitty = cat.Cat.from_profile(profile)
    if not kitty:
        return
    for letter in letters:
        trick = cat.learn_trick(profile, letter)
        if not trick:
            continue
        ui.celebrate(
            stdscr,
            ["%s learned %s!" % (kitty.name, trick.upper()),
             "",
             "(your %s key went green)" % letter.upper()],
            "NEW TRICK",
            art=kitty.art("pounce"),
        )


def celebrate_milestones(stdscr, profile, fresh):
    """
    Unlocked-by-accumulation items. Informational, never a payout.

    A returning kid can trip several at once the first time this runs --
    that is the retroactive credit working -- so they come one at a time
    but the copy never counts them or ranks them. Each one names what was
    accumulated, not how well anything was done.
    """
    kitty = cat.Cat.from_profile(profile)
    for item_id, blurb in fresh:
        item = shop.BY_ID.get(item_id)
        if not item:
            continue
        ui.celebrate(
            stdscr,
            ["%s -- for %s." % (item["name"], blurb),
             "",
             "Not for sale. This one only comes from",
             "turning up and doing the work.",
             "",
             '"%s"' % item["says"]],
            title="YOU EARNED SOMETHING",
            art=kitty.art("overjoyed") if kitty else None,
        )


def show_up_gift(stdscr, all_profiles, profile, first_today):
    """
    The cat brings something in, for turning up. Deferred out of Phase 3
    (issue #9) because there was nowhere to put a feather until the
    Scrapbook existed.

    For SHOWING UP, not for performing -- it fires on the first login of
    a day and knows nothing about speed, accuracy or streaks. A kid
    returning after a month away gets the same warm hello as one who was
    here yesterday (guard 2: absence freezes, it never reverses).

    Once every gift has been found it stops rather than repeating, which
    is the honest end of a collection. #30 adds the escalation.
    """
    if not first_today:
        return
    kitty = cat.Cat.from_profile(profile)
    if kitty is None:
        return

    have = set(scrapbook.found_gifts(profile))
    remaining = [g for g in scrapbook.GIFT_IDS if g not in have]
    if not remaining:
        return

    # Deterministic from the day, so a restart can't reroll for a better
    # one -- and there is no better one, which is the point.
    pick = remaining[abs(hash_day(profile)) % len(remaining)]
    found = scrapbook.find_gift(profile, pick)
    if not found:
        return

    # The escalation (#30) rides along: consecutive days make the gift a
    # little bigger. An absence resets the step silently -- the gift
    # itself never stops arriving, and nothing ever mentions the gap.
    bonus = rituals.gift_bonus(profile)
    if bonus:
        profile["fish"] = profile.get("fish", 0) + bonus
    profiles.save_all(all_profiles)

    lines = ["%s dropped something at your feet." % kitty.name,
             "",
             "It's %s." % found,
             "",
             "Straight into the scrapbook."]
    if bonus:
        lines += ["", "...and %d fish, for keeping it up." % bonus]

    ui.celebrate(stdscr, lines, title="A PRESENT",
                 art=kitty.art("overjoyed"))


def weekend_crate(stdscr, all_profiles, profile):
    """
    A crate on the first weekend login of an ISO week.

    Keyed to the week rather than the day, and to a week *later* than the
    last one collected -- a Pi with a dead RTC boots into the past, and
    merely checking "different week" would let a backwards jump reopen a
    crate already taken, forever.

    Nothing here is missable. A weekend spent away costs nothing; the
    crate is simply there the next one.
    """
    fish = rituals.take_crate(profile)
    if not fish:
        return
    profiles.save_all(all_profiles)
    kitty = cat.Cat.from_profile(profile)
    ui.celebrate(
        stdscr,
        ["Something got dragged in from outside.",
         "",
         "%d fish in it." % fish,
         "",
         "There'll be another one next weekend."],
        title="WEEKEND DELIVERY",
        art=kitty.art("pounce") if kitty else None,
    )


def hash_day(profile):
    """A stable per-day number, so the day's gift can't be rerolled."""
    import zlib
    stamp = "%s:%s" % (profile.get("name", ""), date.today().isoformat())
    return zlib.crc32(stamp.encode("utf-8"))


def growth_ceremony(stdscr, all_profiles, profile):
    """
    The cat growing up: sleeps, stretches, and comes back bigger.

    Fires at most once per stage. The stage itself is already recorded by
    the time we get here, so quitting halfway through costs nothing -- the
    'seen' marker is only written at the end, which means an interrupted
    ceremony plays again next time instead of being silently spent.

    Framed as time-plus-care throughout: nothing here mentions speed,
    accuracy, or scores. It's "look what you've grown", not a payout.
    """
    stage = cat.growth_unseen(profile)
    if stage is None:
        return
    kitty = cat.Cat.from_profile(profile)
    if kitty is None:
        return

    word = cat.GROWTH_WORDS[cat.GROWTH_STAGES[stage]]
    h, w = stdscr.getmaxyx()
    top = max(2, h // 2 - 6)

    fx.clear()
    stdscr.nodelay(True)
    try:
        # Asleep, then a stretch, then the reveal -- three beats so the
        # change reads as something that happened rather than a redraw.
        for pose, beats, note in (("sleep", 22, "%s is fast asleep..." % kitty.name),
                                  ("groom", 16, "...and has a big stretch..."),
                                  ("overjoyed", 26, "look how you've grown!")):
            if pose == "overjoyed":
                fx.spawn("burst", top + 2, w // 2, n=24)
            for _ in range(beats):
                stdscr.erase()
                center(stdscr, top - 1, note, cp(C_WARN, True))
                art_x = max(0, (w - kitty.width(pose)) // 2)
                kitty.draw(stdscr, top + 1, art_x, pose)
                fx.tick(fx.FRAME)
                fx.draw(stdscr)
                stdscr.refresh()
                if engine.is_quit(stdscr.getch()):
                    return          # 'seen' unwritten: it'll come back
                curses.napms(45)
    finally:
        stdscr.nodelay(False)
        fx.clear()

    ui.message(
        stdscr,
        ["%s is a %s now." % (kitty.name, word),
         "",
         "That took %d days of showing up" % profile.get("days_played", 0),
         "and %d letters learned." % len(adaptive.alphabet(profile)),
         "",
         "Nothing was rushed. It just happened."],
        title="LOOK WHO GREW",
        art=kitty.art("overjoyed"),
    )
    cat.mark_growth_seen(profile, stage)
    profiles.save_all(all_profiles)


def choose_cat_screen(stdscr, all_profiles, profile):
    """
    Pick which cat you're looking after.

    A shelved cat is in stasis: locked exactly as you left it. It doesn't
    get hungry, doesn't drift toward wary, doesn't age. Switching back
    finds it precisely as it was, however long it's been -- so choosing
    one is never abandoning the other, and there is nothing to feel bad
    about either way.
    """
    while True:
        book = stasis.shelf(profile)
        if not book:
            return
        live = cat.Cat.from_profile(profile)
        options = []
        if live:
            options.append("* %-14s (with you now)" % live.name)
        for data in book:
            kit = cat.Cat(data["seed"], data.get("name"),
                          data.get("growth", 0), parent=data.get("parent"))
            options.append("  %-14s (curled up, safe)" % kit.name)
        options.append("Done".center(30))

        choice = ui.menu(
            stdscr,
            "W H O   T O D A Y ?",
            options,
            subtitle="whoever waits, waits exactly as they are",
            art=live.art("sit") if live else None,
        )
        first = 1 if live else 0
        if choice == -1 or choice >= len(options) - 1:
            return
        if live and choice == 0:
            continue
        index = choice - first
        woken = stasis.switch_to(profile, index)
        if woken:
            profiles.save_all(all_profiles)
            kit = cat.Cat.from_profile(profile)
            ui.message(
                stdscr,
                ["%s uncurls and stretches." % kit.name,
                 "",
                 "Exactly as you left them.",
                 "",
                 "Nothing changed while they were waiting."],
                title="THERE YOU ARE",
                art=kit.art("overjoyed"),
            )


def graduation_ceremony(stdscr, all_profiles, profile):
    """
    The win condition: every letter mastered AND 40+ wpm sustained.

    An egg arrives, and the kid hatches a kitten the way they hatched
    their first -- deliberately the same ceremony, because it rhymes.

    The cat they already have does not go anywhere. It is shelved into
    stasis, not replaced, not retired, not traded. A kid who has spent a
    year with an animal that has their name on it is not being asked to
    give it up for a newer one.
    """
    if not graduation.check(profile):
        return
    grown = cat.Cat.from_profile(profile)
    if grown is None:
        return

    median = graduation.recent_wpm(profile)
    ui.message(
        stdscr,
        ["Every letter on the keyboard. All twenty-six.",
         "",
         "And %.0f words a minute, again and again --" % (median or 0.0),
         "not once, but every time you sit down.",
         "",
         "%s has something for you." % grown.name],
        title="YOU CAN TYPE",
        art=grown.art("overjoyed"),
    )

    # Same hatch the game opened with. It is theirs to name, and their
    # first cat is standing right there while it happens.
    data = hatch_ceremony(stdscr, profile, parent=grown.seed,
                          keep_existing=True)
    graduation.mark_graduated(profile)
    profiles.save_all(all_profiles)

    kit = cat.Cat.from_profile(profile)
    ui.message(
        stdscr,
        ["%s and %s." % (grown.name, kit.name),
         "",
         "Whoever you aren't looking after waits exactly",
         "as they are -- nothing changes while they're curled up.",
         "",
         "Switch whenever you like."],
        title="LOOK WHAT YOU CAN TEACH",
        art=kit.art("sit"),
    )


def secret_ceremony(stdscr, all_profiles, profile):
    """
    The one thing the game never tells you about in advance.

    Every letter unlocked and every letter mastered, and the cat comes
    back wearing stars. Nothing hints at it beforehand -- no progress bar,
    no "keep going and something happens", nothing in the shop. It's meant
    to travel between siblings by word of mouth, and it can't do that if
    the game spoils it.

    It stays lateral: a surprise for finishing the journey, not a tier
    above anybody else's cat.
    """
    if not cat.secret_unseen(profile):
        return
    kitty = cat.Cat.from_profile(profile)
    if kitty is None:
        return

    h, w = stdscr.getmaxyx()
    top = max(2, h // 2 - 6)
    fx.clear()
    stdscr.nodelay(True)
    try:
        for beat in range(46):
            if beat in (0, 14, 28):
                fx.spawn("confetti", top + 2, w // 2, n=14)
            stdscr.erase()
            center(stdscr, top - 1, "something is different...",
                   cp(C_WARN, True))
            art_x = max(0, (w - kitty.width("overjoyed")) // 2)
            kitty.draw(stdscr, top + 1, art_x, "overjoyed")
            fx.tick(fx.FRAME)
            fx.draw(stdscr)
            stdscr.refresh()
            if engine.is_quit(stdscr.getch()):
                return          # unwritten: it comes back next time
            curses.napms(45)
    finally:
        stdscr.nodelay(False)
        fx.clear()

    ui.message(
        stdscr,
        ["%s is covered in stars." % kitty.name,
         "",
         "You learned every letter on the keyboard,",
         "and then you got good at all of them.",
         "",
         "Nobody was told this would happen."],
        title="OH!",
        art=kitty.art("overjoyed"),
    )
    cat.mark_secret_seen(profile)
    profiles.save_all(all_profiles)


def check_growth(stdscr, all_profiles, profile):
    """Advance the cat if earned, then pay out any ceremony still owed."""
    if cat.advance_growth(profile) is not None:
        profiles.save_all(all_profiles)
    growth_ceremony(stdscr, all_profiles, profile)
    secret_ceremony(stdscr, all_profiles, profile)


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
        # Fish come from volume typed, never from hitting a score. Showing
        # up on a bad day has to pay the same as a good one.
        profile["fish"] = profile.get("fish", 0) + summary.get("words", 0)
    fresh = badges.check_new(profile)
    profiles.save_all(all_profiles)
    announce_letters(stdscr, profile, progress["unlocked"])
    celebrate_tricks(stdscr, profile, progress["green"])
    if summary:
        announce_catches(stdscr, profile, summary.get("species") or [])
    if fresh:
        celebrate_badges(stdscr, fresh)
    celebrate_milestones(stdscr, profile, milestones.check_new(profile))
    # Last, so a stage-up lands after the letter that earned it, and
    # graduation after the mastery that earned that.
    check_growth(stdscr, all_profiles, profile)
    graduation_ceremony(stdscr, all_profiles, profile)
    profiles.save_all(all_profiles)


POSE_TICKS = 36        # ~4s at the menu's 110ms idle tick
BUBBLE_MAX = 14        # keeps the bubble clear of the centred menu labels
SLEEP_AFTER_ROUNDS = 2  # free-play rounds before the cat curls up (a cue, not a wall)


def _sentence(items):
    """'food, playtime and a clean litter box'"""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def _wrap(text, width=38):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return lines


def care_callout(stdscr, profile):
    """
    The cat as quest-giver: on arrival it says what it would like today.
    It asks; it never guilts, and nothing bad happens if the kid ignores
    it and goes to Stats instead.
    """
    kitty = cat.Cat.from_profile(profile)
    if not kitty:
        return
    left = cat.tasks_left_today(profile)
    if cat.wary_active(profile):
        lines = _wrap("%s has been on its own a while. Go gently." % kitty.name)
        pose = "wary"
    elif left:
        lines = _wrap("%s would like %s." % (
            kitty.name, _sentence([cat.CARE_NEEDS[t] for t in left])))
        pose = cat.mood_pose(cat.mood(profile))
    else:
        lines = ["%s has everything it needs." % kitty.name, "Go and play!"]
        pose = "overjoyed"

    # A reason to look in the shop, phrased as news rather than as a
    # deadline: the stock rotates, but nothing in it ever expires.
    feature = shop.featured_today(profile)
    if feature is not None:
        lines += [""] + _wrap("The shop has a %s today!" % feature["name"].lower())

    stdscr.erase()
    h, w = stdscr.getmaxyx()
    top = max(1, h // 2 - 6)
    art_w = kitty.width(pose)
    cat_x = max(0, (w - art_w) // 2)
    bubble_w = max(len(l) for l in lines) + 4
    tail_x = 3
    ui.speech_bubble(stdscr, top, max(0, min(w - bubble_w,
                                             cat_x + art_w // 2 - tail_x)),
                     lines, cp(C_ACCENT, True), tail_x=tail_x)
    kitty.draw(stdscr, top + len(lines) + 2, cat_x, pose)
    center(stdscr, min(h - 2, top + len(lines) + 9), "press any key", cp(C_PENDING))
    stdscr.refresh()
    stdscr.getch()


def menu_cat_painter(profile, day):
    """
    The cat living in the corner of the menu. Returns a `draw_extra` for
    ui.menu, or None for a profile with no cat -- in which case the menu
    is exactly the menu it always was.

    `day` is the mutable per-login state main_menu keeps, so the cat can
    settle down after a couple of free-play rounds.
    """
    c = cat.Cat.from_profile(profile)
    if c is None:
        return None
    state = {"pose": "sit", "line": "Hi, %s!" % profile["name"], "ticks": 0}

    def paint(win, idx=0):
        h, w = win.getmaxyx()
        state["ticks"] += 1
        if state["ticks"] % POSE_TICKS == 0:
            state["pose"] = c.next_idle()
            state["line"] = c.says(state["pose"])

        # Two stopping cues, both warm and neither a wall. A cat that's
        # been alone a while is asleep and missing you; a cat that's been
        # played with is asleep because it's had a lovely day.
        if cat.wary_active(profile):
            state["pose"], state["line"] = "wary", "..."
        elif day.get("free_play", 0) >= SLEEP_AFTER_ROUNDS:
            state["pose"], state["line"] = "sleep", "*dreaming*"
        elif cat.mood(profile) == "missing":
            state["pose"], state["line"] = "sleep", "*curled up*"

        pose = state["pose"]
        art_w, art_h = c.width(pose), c.height(pose)
        x = max(0, w - art_w - 4)
        y = max(0, h - art_h - 1)

        # The bubble sits three rows up, beside the short menu labels
        # rather than the long ones, and is capped so a long name can't
        # push it left into them.
        c.draw(win, y, x, pose)

        # A seasonal touch beside the cat, and a hat on its hatch
        # anniversary. Purely cosmetic and computed from the date, so a
        # Pi with a wrong clock gets a pumpkin in March -- a funny bug
        # rather than anything stored wrong. Nothing is missable: every
        # season comes back next year.
        mark = None
        if rituals.is_hatch_birthday(profile):
            mark = "_o_"
        else:
            spell = rituals.season()
            if spell:
                mark = spell[2]
        if mark:
            safe_addstr(win, max(0, y - 1), x + max(0, art_w // 2 - 1),
                        mark, cp(C_WARN, True))

        # Everything they've bought, arranged beside them: the visible
        # record of months of care, which is the whole point of decor.
        dx = x - 2
        for item in reversed(shop.owned_decor(profile)[-2:]):
            art = item["art"]
            dx -= max(len(row) for row in art) + 1
            for i, row in enumerate(art):
                # One row above the cat's feet: the bottom row belongs to
                # ui.menu's footer, and decor must never sit on the text.
                safe_addstr(win, y + art_h - len(art) + i - 1, dx, row,
                            cp(C_PENDING, True))

        # A looked-after cat purrs. Wisps only, and only when everything
        # is full -- it's a reward for care, not ambient decoration.
        if cat.mood(profile) == "thriving" and state["ticks"] % 8 == 0:
            fx.spawn("purr", y - 1, x + art_w // 2)
        fx.tick(0.11)   # the menu's idle tick
        fx.draw(win)

        # The bubble goes on last so wisps drift behind the words rather
        # than through them.
        line = state["line"][:BUBBLE_MAX]
        bubble_w = len(line) + 4
        ui.speech_bubble(win, max(0, y - 3), max(0, w - bubble_w - 2), [line],
                         cp(C_ACCENT), tail_x=max(1, bubble_w - 5))

    return paint


def _shop_painter(profile, kitty, items):
    """The cat leaning over the counter with an opinion about everything."""
    def paint(win, idx):
        h, w = win.getmaxyx()
        # Below ui.menu's footer row, so nothing lands on the title.
        info = min(h - 9, 14)
        safe_addstr(win, info, 4, "You have %d fish" % shop.fish(profile),
                    cp(C_WARN, True))

        inv = shop.inventory(profile)
        owned = "%d toys   %d decor   %s litter" % (
            len(inv["toys"]), len(inv["decor"]), inv["litter"])
        safe_addstr(win, info + 1, 4, owned, cp(C_PENDING))

        if not kitty:
            return
        item = items[idx] if idx < len(items) else None
        line = item["says"] if item else "*tail flick*"
        if item and item["id"] == kitty.favourite_treat:
            line = "That's my favourite!"

        pose = "pounce" if item and item["kind"] == shop.KIND_TOY else "sit"
        art_w = kitty.width(pose)
        x = max(0, w - art_w - 4)
        y = max(0, h - kitty.height(pose) - 1)
        bubble = line[:34]
        bw = len(bubble) + 4
        ui.speech_bubble(win, max(0, y - 3), max(0, w - bw - 2), [bubble],
                         cp(C_ACCENT), tail_x=max(1, bw - 5))
        kitty.draw(win, y, x, pose)
    return paint


def use_treat_screen(stdscr, all_profiles, profile):
    """Arm a treat for the next game. The kid chooses when, always."""
    kitty = cat.Cat.from_profile(profile)
    while True:
        treats = sorted(shop.inventory(profile)["treats"].items())
        if not treats:
            return
        labels = []
        for item_id, count in treats:
            item = shop.BY_ID[item_id]
            ready = shop.has_effect(profile, item["effect"])
            labels.append("%-18s x%-2d  %s%s" % (
                item["name"], count, shop.EFFECT_NAMES[item["effect"]],
                "  (already ready)" if ready else ""))
        labels.append("Back")

        armed = shop.armed(profile)
        choice = ui.menu(
            stdscr,
            "TREAT TIME",
            labels,
            subtitle=("ready to use: " + ", ".join(shop.EFFECT_NAMES[e] for e in armed)
                      if armed else "pick one to save for your next game"),
            footer="ENTER to use one   ESC to go back",
        )
        if choice == -1 or choice >= len(treats):
            return

        item = shop.BY_ID[treats[choice][0]]
        effect = shop.activate(profile, item["id"])
        if effect is None:
            ui.message(stdscr,
                       ["You've already got that one ready to go.", "",
                        "Use it first -- no need to spend two."],
                       title="ALREADY SAVED")
            continue
        profiles.save_all(all_profiles)
        name = kitty.name if kitty else "Your cat"
        ui.message(
            stdscr,
            ["%s wolfs down the %s." % (name, item["name"].lower()),
             "",
             "Ready for your next game: %s." % shop.EFFECT_BLURBS[effect]],
            title="SAVED FOR LATER",
            art=kitty.art("overjoyed") if kitty else None,
        )


def scrapbook_screen(stdscr, profile):
    """
    The album. Never gated -- looking at what you've collected costs
    nothing, and on an empty page the silhouettes are the invitation.

    Unfound items are `? ? ?` rather than a count of what's missing or
    any hint of a deadline. "There is more to find" is the whole message;
    a collection screen is exactly where a game would normally start
    manufacturing urgency, and this one doesn't.
    """
    pages = scrapbook.albums(profile)
    if not pages:
        return
    kitty = cat.Cat.from_profile(profile)
    page = 0

    while True:
        title, rows = pages[page]
        found, total = scrapbook.page_progress(rows)

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        center(stdscr, 0, "%s's SCRAPBOOK" % profile["name"], cp(C_TITLE, True))
        safe_addstr(stdscr, 1, 2, "%s  --  %d of %d" % (title, found, total),
                    cp(C_ACCENT, True))
        safe_addstr(stdscr, 1, max(30, w - 26),
                    "page %d of %d" % (page + 1, len(pages)), cp(C_PENDING))

        # Two columns, so 26 fish fit on one page at 80x24. The floor
        # stops above the cat in the corner: the second column shares its
        # columns, so a full page would otherwise draw items through it.
        top = 3
        room = max(4, h - 9)
        col_w = max(18, (w - 8) // 2)
        for i, (label, got, note) in enumerate(rows[:room * 2]):
            row = top + i % room
            x = 4 + (i // room) * col_w
            text = label if got else "? ? ?"
            if got and note:
                text = "%s (%s)" % (label, note)
            safe_addstr(stdscr, row, x, text[:col_w - 2],
                        cp(C_CORRECT, True) if got else cp(C_PENDING))

        if kitty is not None and w > 60:
            kitty.draw(stdscr, h - 6, max(2, w - kitty.width("sit") - 3), "sit")

        center(stdscr, h - 2, "nothing here can ever be lost", cp(C_PENDING))
        center(stdscr, h - 1,
               "left/right to turn the page   -   ESC to close", cp(C_PENDING))
        stdscr.refresh()

        key = stdscr.getch()
        if engine.is_quit(key) or key in (ord("q"), ord("Q")):
            return
        if key in (curses.KEY_RIGHT, ord("l"), ord(" ")):
            page = (page + 1) % len(pages)
        elif key in (curses.KEY_LEFT, ord("h")):
            page = (page - 1) % len(pages)


def announce_catches(stdscr, profile, catches):
    """
    New species, stamped into the album.

    One popup for the batch: a kid typing "quiet" early on can hook four
    at once, and four popups would bury the moment the rare one turned up.
    """
    if not catches:
        return
    rare = [(c, n) for c, n in catches
            if scrapbook.fish_tier(c) in ("rare", "legendary")]
    lines = ["  ".join(n for _, n in catches), ""]
    if rare:
        lines.append("The %s is a rare one!" % rare[0][1])
    else:
        lines.append("Stamped into your scrapbook.")
    ui.celebrate(
        stdscr, lines,
        "NEW FISH" if len(catches) == 1 else "%d NEW FISH" % len(catches),
        art=["", "   > < >   ", ""],
    )


def dress_up_screen(stdscr, all_profiles, profile):
    """
    Swap between accessories already owned, or take everything off.

    Owning several and being stuck in whichever was bought last would
    make the fifth one a downgrade of the fourth, which is exactly the
    tiering this game doesn't do. Taking it off is always on the list --
    a bare cat is a look, not a lack.
    """
    while True:
        inv = shop.inventory(profile)
        owned = [i for i in inv["accessories"] if i in cat.ACCESSORIES]
        if not owned:
            return
        worn = cat.worn_accessory(profile)

        labels = []
        for item_id in owned:
            mark = "*" if item_id == worn else " "
            labels.append("%s %-24s" % (mark, shop.BY_ID[item_id]["name"]))
        labels.append("%s %-24s" % (" " if worn else "*", "Nothing at all"))
        labels.append("Done".center(26))

        kitty = cat.Cat.from_profile(profile)
        choice = ui.menu(
            stdscr,
            "D R E S S   U P",
            labels,
            subtitle="* is what %s has on right now"
                     % (kitty.name if kitty else "your cat"),
            art=kitty.art("overjoyed") if kitty else None,
        )
        if choice == -1 or choice >= len(labels) - 1:
            return
        cat.wear(profile, None if choice == len(owned) else owned[choice])
        profiles.save_all(all_profiles)


def shop_screen(stdscr, all_profiles, profile):
    """
    Browsing is always free and never gated -- window shopping with no
    fish is a perfectly good thing for a kid to do, and being told "come
    back when you've earned it" is the pattern this game doesn't use.
    """
    kitty = cat.Cat.from_profile(profile)
    while True:
        items = shop.shelf(profile)
        labels = []
        for item in items:
            ok, _ = shop.can_buy(profile, item["id"])
            tag = "" if ok else "  (saving up)"
            flag = " *" if shop.is_featured(profile, item["id"]) else "  "
            labels.append("%s%-20s %4d fish%s" % (
                flag, item["name"], item["price"], tag))

        inv = shop.inventory(profile)
        treats = inv["treats"]
        extras = []
        if treats:
            extras.append("Use a treat (%d)" % sum(treats.values()))
        if inv["accessories"]:
            extras.append("Dress up (%d)" % len(inv["accessories"]))
        extras.append("Done")

        # ui.menu centres each label on its own, so a price list with
        # ragged lengths visibly wobbles as you move down it.
        width = max(len(l) for l in labels + extras)
        labels = [l.ljust(width) for l in labels]
        extras = [l.center(width) for l in extras]

        choice = ui.menu(
            stdscr,
            "THE SHOP",
            labels + extras,
            subtitle="* today's pick   --   new things every week, and "
                     "everything comes back",
            footer="ENTER to buy   ESC to go back",
            draw_extra=_shop_painter(profile, kitty, items),
        )
        if choice == -1 or choice >= len(labels) + len(extras) - 1:
            return
        if choice >= len(labels):
            picked = extras[choice - len(labels)].strip()
            if picked.startswith("Dress up"):
                dress_up_screen(stdscr, all_profiles, profile)
            else:
                use_treat_screen(stdscr, all_profiles, profile)
            continue

        item = items[choice]
        ok, reason = shop.can_buy(profile, item["id"])
        if not ok:
            # Never "you can't afford this". Always "here's how close".
            ui.message(
                stdscr,
                [reason, "", "It'll still be here -- nothing in this shop",
                 "ever goes away for good."],
                title="MAYBE NEXT TIME",
                art=kitty.art("sit") if kitty else None,
            )
            continue

        if shop.buy(profile, item["id"]):
            profiles.save_all(all_profiles)
            name = kitty.name if kitty else "Your cat"
            ui.celebrate(
                stdscr,
                ["%s: %s" % (item["name"], item["blurb"]),
                 "",
                 '"%s" -- %s' % (item["says"], name),
                 "",
                 "%d fish left" % shop.fish(profile)],
                title="BOUGHT IT",
                art=kitty.art("overjoyed") if kitty else None,
            )


def run_mode(stdscr, mode, profile):
    try:
        return mode.play(stdscr, profile)
    except curses.error:
        ui.message(stdscr,
                   ["Your terminal is too small for that mode.",
                    "Try making the window bigger (80x24 minimum)."],
                   title="OOPS")
        return None


def arcade_for(profile):
    """
    The modes this kid can actually play right now.

    A mode may define `available(profile)` to hide itself. Alphabet Soup
    uses it while the unlocked alphabet is too small to build a bowl worth
    solving; Whisker Quiz will use it for an empty quiz file. A mode
    without the hook is always available, so nothing else has to change.

    Hiding rather than showing-and-refusing is deliberate: a locked door a
    kid can see is a door they'll rattle, and this game doesn't do that.
    """
    out = []
    for entry in ARCADE:
        check = getattr(entry[0], "available", None)
        if check is None or check(profile):
            out.append(entry)
    return out


def play_slot(stdscr, profile):
    """
    The Play care task. The cat wants to play; which game is entirely the
    kid's call. This is the autonomy slot the research asks for, sitting
    inside the structure rather than fighting it.
    """
    kitty = cat.Cat.from_profile(profile)
    name = kitty.name if kitty else "your cat"
    arcade = arcade_for(profile)
    choice = ui.menu(
        stdscr,
        "P L A Y   T I M E",
        ["%-18s(%s)" % (label, blurb) for _, _, label, blurb in arcade]
        + ["Never mind"],
        subtitle="%s wants to play -- you pick" % name,
    )
    if choice == -1 or choice >= len(arcade):
        return None
    return run_mode(stdscr, arcade[choice][0], profile)


def build_menu(profile, gated):
    """
    The menu as (label, action) pairs, so the care entry can come and go
    without every index below it shifting by hand.

    The gate covers free play only. Stats, Badges, Switch and Quit are
    never locked -- a kid always has a way out of any screen in this game.
    """
    kitty = cat.Cat.from_profile(profile)
    entries = []
    if kitty:
        left = cat.tasks_left_today(profile)
        note = ("all done today!" if not left
                else "%d thing%s to do" % (len(left), "" if len(left) == 1 else "s"))
        entries.append(("%-18s(%s)" % ("Care for " + kitty.name, note), ("care", None)))

    for mod, key, label, blurb in arcade_for(profile):
        note = ("after %s's cared for" % kitty.name) if gated else blurb
        entries.append(("%-18s(%s)" % (label, note), ("mode", (mod, key))))

    # Never gated: browsing costs nothing and looking at things you're
    # saving for is half the fun of saving for them.
    if stasis.shelf(profile):
        entries.append(("Choose a cat", ("choosecat", None)))
    entries.append(("The Shop", ("shop", None)))
    entries.append(("My Scrapbook", ("scrapbook", None)))
    entries.append(("My Badges", ("badges", None)))
    entries.append(("My Stats", ("stats", None)))
    entries.append(("Switch player", ("switch", None)))
    entries.append(("Quit", ("quit", None)))
    return entries


def menu_cat_panel(profile, day):
    """
    The framed cat column for the main menu: the big portrait, an idle
    pose, and whatever they're wearing.

    Returns (width, height, draw) for ui.menu, or None for a profile with
    no cat -- in which case the menu is the plain centred one it always
    was. The portrait set is used here rather than the game sprite: this
    is the screen where the cat IS the screen.
    """
    kitty = cat.Cat.from_profile(profile)
    if kitty is None:
        return None

    poses = [p for p in cat.POSES if p not in ("wary",)]
    width = max(kitty.width(p, big=True) for p in poses)
    height = max(kitty.height(p, big=True) for p in poses)
    state = {"pose": "sit", "ticks": 0}

    def draw(win, top, left):
        state["ticks"] += 1
        if state["ticks"] % POSE_TICKS == 0:
            state["pose"] = kitty.next_idle()
        pose = state["pose"]
        if cat.wary_active(profile):
            pose = "wary"
        elif day.get("free_play", 0) >= SLEEP_AFTER_ROUNDS:
            pose = "sleep"
        elif cat.mood(profile) == "missing":
            pose = "sleep"
        # Centred in its frame, and never taller than the frame allows.
        art_w = kitty.width(pose, big=True)
        kitty.draw(win, top, left + max(0, (width - art_w) // 2), pose,
                   big=True)

    return width, height, draw


def main_menu(stdscr, all_profiles, profile):
    first_today = profiles.touch_day(profile)
    if first_today:
        # Today counts against the cat actually being looked after; a
        # shelved one is frozen and must not age (#33).
        stasis.touch_active_day(profile)
    fresh = badges.check_new(profile)
    profiles.save_all(all_profiles)
    # A new day can be the day the cat grows, and a ceremony interrupted
    # last time is still owed. Both are settled before the menu appears.
    check_growth(stdscr, all_profiles, profile)
    # Retroactive credit lands here for a kid whose history predates the
    # feature -- several at once is the design working, not a bug.
    celebrate_milestones(stdscr, profile, milestones.check_new(profile))
    profiles.save_all(all_profiles)
    show_up_gift(stdscr, all_profiles, profile, first_today)
    weekend_crate(stdscr, all_profiles, profile)

    if first_today and profile["current_streak"] > 1:
        lines = ["Day %d in a row. Keep it going!" % profile["current_streak"]]
        if profiles.streak_was_rescued(profile):
            kitty = cat.Cat.from_profile(profile)
            lines = [
                "The %s litter kept things cosy while you were away," %
                shop.inventory(profile)["litter"],
                "so your %d-day streak is exactly where you left it." %
                profile["current_streak"],
                "",
                "%s is pleased with your planning." %
                (kitty.name if kitty else "Your cat"),
            ]
        ui.message(stdscr, lines,
                   title="WELCOME BACK, %s" % profile["name"].upper())

    # Latched once at login rather than recomputed all session, so doing
    # one task doesn't make the cat flip back and forth.
    if profile.get("cat") and cat.is_wary(profile):
        cat.set_wary(profile, True)
    if fresh:
        celebrate_badges(stdscr, fresh)
    if not profile.get("cat"):
        offer_hatch(stdscr, all_profiles, profile)

    care_callout(stdscr, profile)

    day = {"free_play": 0}
    paint_cat = menu_cat_painter(profile, day)
    panel = menu_cat_panel(profile, day)

    def after_task(task, summary):
        after_session(stdscr, all_profiles, profile, task, summary)

    while True:
        kitty = cat.Cat.from_profile(profile)
        gated = kitty is not None and not cat.care_done_today(profile)
        entries = build_menu(profile, gated)

        lvl = lessons.get_level(profile["rocket_level"])
        sub = "streak %d days  |  %d fish  |  %d badges" % (
            profile["current_streak"], profile.get("fish", 0), len(profile["badges"])
        )
        choice = ui.menu(
            stdscr,
            "%s  --  Level %d: %s" % (profile["name"], profile["rocket_level"], lvl["name"]),
            [label for label, _ in entries],
            subtitle=sub,
            panel=panel,
            panel_title=(cat.Cat.from_profile(profile).name
                         if profile.get("cat") else None),
            draw_extra=paint_cat if panel is None else None,
        )

        action, payload = ("quit", None) if choice == -1 else entries[choice][1]

        if action == "quit":
            return "quit"
        if action == "switch":
            return "switch"
        if action == "shop":
            shop_screen(stdscr, all_profiles, profile)
            continue
        if action == "scrapbook":
            scrapbook_screen(stdscr, profile)
            continue
        if action == "choosecat":
            choose_cat_screen(stdscr, all_profiles, profile)
            continue
        if action == "badges":
            show_badges(stdscr, profile)
            continue
        if action == "stats":
            show_stats(stdscr, profile)
            continue
        if action == "care":
            care.board(stdscr, profile, play_slot, after_task)
            continue

        mode, name = payload
        if gated:
            # Not a scolding and not a dead end: it says what opens it,
            # and the care board is one keypress away.
            ui.message(
                stdscr,
                ["%s would like to be looked after first." % kitty.name,
                 "",
                 "Head to the care board -- it's quick,",
                 "and then everything's open."],
                title="SOON!",
                art=kitty.art(cat.mood_pose(cat.mood(profile))),
            )
            continue

        summary = run_mode(stdscr, mode, profile)
        day["free_play"] += 1
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
