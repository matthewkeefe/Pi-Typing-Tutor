#!/usr/bin/env python3
"""
Render any screen to a real terminal and print what it actually drew.

    python3 tools/screenshot.py --list
    python3 tools/screenshot.py stats
    python3 tools/screenshot.py scrapbook --profile veteran
    python3 tools/screenshot.py --all --out /tmp/shots
    python3 tools/screenshot.py soup --size 20x60

WHY THIS EXISTS

    The test suite draws into a fake window that fails loudly if anything
    lands off-screen. That catches crashes and overflow. It cannot tell
    you the screen is *correct*, and across phases 6-9 every single
    rendering bug got through a green suite and was caught only by
    looking:

      - the Alphabet Soup bowl smeared its last two tiles, because the
        frame and the letter overlay disagreed by one column
      - Mystery Word RENDERED ITS OWN ANSWER during the spelling phase --
        draw_typing_line paints the target, which is right everywhere
        else and defeats the entire mode here
      - hats sat on the cat's nose, inserted below the ears
      - "take the collar off" silently put it back on
      - earned accessories were invisible: in the inventory, absent from
        cat.ACCESSORIES, so they never drew at all
      - the stats screen drew straight through itself, and had been doing
        so since Phase 6 quietly added modes

    Seven bugs, seven green suites. Assertions prove nothing escaped the
    screen; only a person can see that the screen is right. This makes
    looking cheap.

HOW IT WORKS

    curses needs a real terminal, so this forks one with `os.forkpty`.
    The parent must keep draining the master fd or the child blocks the
    moment curses fills the buffer -- that is why it isn't a bare
    `openpty`, and it's the first thing to check if this ever hangs.
"""

import argparse
import fcntl
import os
import struct
import sys
import termios

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_H, DEFAULT_W = 24, 80


# --- profile fixtures ------------------------------------------------
#
# Three kids at three points in the journey. Add more here rather than
# building profiles inside a scene -- most bugs show up at one particular
# stage, and being able to swap the stage is half the value.


def _profile(kind):
    from core import adaptive, cat, contests, scrapbook, shop
    from core import profiles as P

    p = P._blank_profile("Matt")
    p["cat"] = cat.blank_cat_data(4242, "Mittens", "2025-03-14")

    if kind == "new":
        return p

    p["current_streak"], p["longest_streak"] = 5, 9
    p["days_played"], p["total_words"] = 120, 12000
    p["total_seconds"], p["best_wpm"], p["best_accuracy"] = 4200, 28.4, 96.2
    p["cat"]["growth"] = 2
    p["cat"]["days_active"] = 120
    p["fish"] = 900
    p["alphabet"] = adaptive.FREQ_ORDER[:20]
    p["keys"] = {c: {"n": 99, "conf": 0.93, "ms": 310.0}
                 for c in adaptive.FREQ_ORDER[:20]}
    for word in ("eel", "quiet", "trout", "salad", "dozen", "cabin", "jazz"):
        scrapbook.catch_from_word(p, word)
    scrapbook.find_gift(p, "feather")
    shop.buy(p, "yarn_ball")
    shop.buy(p, "red_collar")
    for letter in "enitr":
        cat.learn_trick(p, letter)
    contests.award(p, 0)
    p["history"] = [{"date": "2026-07-0%d" % (i % 9 + 1), "mode": "dash",
                     "wpm": 26.0 + i, "accuracy": 95.0, "words": 40,
                     "seconds": 60} for i in range(8)]
    if kind == "veteran":
        return p

    # A graduate: everything mastered, ten fast sessions, two cats.
    p["alphabet"] = adaptive.FREQ_ORDER
    p["keys"] = {c: {"n": 200, "conf": 0.99, "ms": adaptive.MASTER_MS - 20}
                 for c in adaptive.FREQ_ORDER}
    p["history"] = [{"date": "2026-07-2%d" % (i % 9), "mode": "dash",
                     "wpm": 42.0, "accuracy": 97.0, "words": 45,
                     "seconds": 60} for i in range(10)]
    p["graduated"] = "2026-07-26"
    p["cat"]["growth"] = 3
    from core import stasis
    stasis.add_cat(p, cat.blank_cat_data(77, "Pip", "2026-07-26", parent=4242))
    return p


PROFILES = ("new", "veteran", "graduate")


# --- scenes ----------------------------------------------------------
#
# Each takes (stdscr, profile) and draws one screen. Keep them dumb: the
# point is to see what the real code draws, so call the real function.


def _scene_picker(stdscr, profile):
    """
    The profile picker: block-letter title, framed table of players.

    Built from several profiles rather than the one passed in, because
    the whole point of this screen is the shared-device case -- four
    kids, four cat glyphs, one straight left edge down the names.
    """
    import curses
    import main
    from core import cat, profiles as P
    people = {}
    for i, name in enumerate(("Anne", "Arthur", "Betsey", "Matt")):
        p = P._blank_profile(name)
        p["cat"] = cat.blank_cat_data(1000 + i * 37, "Cat%d" % i, "2026-01-01")
        people[name] = p
    curses.ungetch(27)
    main.pick_profile(stdscr, people)


def _scene_menu_cat(stdscr, profile):
    """The real main menu: framed cat portrait left, options right."""
    import curses
    import main
    from core import cat, ui
    panel = main.menu_cat_panel(profile, {"free_play": 0})
    entries = main.build_menu(profile, False)
    kitty = cat.Cat.from_profile(profile)
    curses.ungetch(27)
    ui.menu(stdscr, "%s  --  Level 1" % profile["name"],
            [label for label, _ in entries],
            subtitle="streak %d days  |  %d fish"
                     % (profile["current_streak"], profile.get("fish", 0)),
            panel=panel, panel_title=kitty.name if kitty else None)


def _scene_care(stdscr, profile):
    """The care board: framed cat + gauges left, task list right."""
    import curses
    from modes import care
    curses.ungetch(27)
    care.board(stdscr, profile, lambda *_a: None, lambda *_a: None)


def _scene_shop(stdscr, profile):
    import curses
    import main
    curses.ungetch(27)
    main.shop_screen(stdscr, {"Matt": profile}, profile)


def _scene_playslot(stdscr, profile):
    import curses
    import main
    curses.ungetch(27)
    main.play_slot(stdscr, profile)


def _scene_stats(stdscr, profile):
    import curses
    import main
    curses.ungetch(27)
    main.show_stats(stdscr, profile)


def _scene_scrapbook(stdscr, profile):
    import curses
    import main
    curses.ungetch(27)
    main.scrapbook_screen(stdscr, profile)


def _scene_soup(stdscr, profile):
    import random
    from core import adaptive, cat, wordlist
    from modes import soup
    tiles, sols = wordlist.make_bowl(adaptive.alphabet(profile), random.Random(4))
    soup._draw(stdscr, cat.Cat.from_profile(profile), "overjoyed", tiles,
               "stu", sols[:4], 52, 45.0, "'%s' -- nice!" % sols[0], True)


def _scene_mystery(stdscr, profile):
    from core import cat
    from modes import mystery
    mystery._draw(stdscr, cat.Cat.from_profile(profile), "swat", "letter",
                  {"e", "t"}, 2, 2, 3, True, "lett",
                  "Enough showing -- spell it out!", True, False)


def _scene_pantry(stdscr, profile):
    from core import cat
    from modes import pantry
    kitty = cat.Cat.from_profile(profile)
    guard = 2 + pantry.BOWL_W + 1 + (kitty.width("sit") if kitty else 3)
    mice = [pantry.Mouse("stub", 30, 4), pantry.Mouse("studio", 52, 6),
            pantry.Mouse("tin", 68, 8), pantry.Mouse("net", guard + 4, 10)]
    pantry._draw(stdscr, kitty, "swat", mice, "stu", 42, 3, 3, 94.2,
                 guard, 2, 4, False, None)


def _scene_quiz(stdscr, profile):
    from core import cat
    from modes import quiz
    quiz._draw(stdscr, cat.Cat.from_profile(profile), "wary",
               "What do you call an animal that eats only plants?", "plant",
               2, 8, 1, "Not quite -- it's 'herbivore'. We'll come back to it.",
               False)


def _scene_race(stdscr, profile):
    from core import cat, ghosts
    from modes import race
    words = list(ghosts.PASSAGES[0][1])
    race._draw(stdscr, words, 3, "fa", cat.Cat.from_profile(profile),
               cat.Cat(77, "Pip"), "Pip", 2, 4.2, "", None)


def _scene_contest(stdscr, profile):
    from core import cat, contests
    from modes import contest
    contest._draw(stdscr, cat.Cat.from_profile(profile), "pounce", "planet",
                  "pla", 14, 37.5, contests.CUPS[1], "", False)


def _scene_yarn(stdscr, profile):
    from core import cat
    from modes import yarn
    art, name = yarn.toy_for(profile)
    kitty = cat.Cat.from_profile(profile)
    floor = stdscr.getmaxyx()[0] - 5
    yarn._draw_scene(stdscr, kitty, "pounce", art, name, "tinter", "tin",
                     3, 2, (stdscr.getmaxyx()[1] // 2, floor - 4),
                     stdscr.getmaxyx()[1] - 22)


def _scene_platformer(stdscr, profile):
    from core import cat
    from modes import platformer
    words = ["cat", "jump", "fish", "leap", "star", "moon"] * 3
    pos = platformer._hero_anchor(2, 2, 7, stdscr)
    platformer._draw_world(stdscr, words, 2, 7, pos, "stand",
                           cat.Cat.from_profile(profile), 3, 4, "fi", None)


def _scene_cats(stdscr, profile):
    """Every growth stage and accessory at once -- the gallery."""
    from core import cat, ui
    ui.center(stdscr, 0, "growth 0-3, then every accessory", 0)
    for i, g in enumerate((0, 1, 2, 3)):
        cat.Cat(4242, "M", growth=g).draw(stdscr, 2, 2 + i * 13, "sit")
        ui.safe_addstr(stdscr, 8, 2 + i * 13, cat.GROWTH_STAGES[g], 0)
    for i, aid in enumerate(sorted(cat.ACCESSORIES)[:5]):
        cat.Cat(4242, "M", growth=2, accessory=aid).draw(stdscr, 10,
                                                         2 + i * 15, "sit")
        ui.safe_addstr(stdscr, 17, 2 + i * 15, aid[:13], 0)
    cat.Cat(4242, "M", growth=3, secret=True).draw(stdscr, 19, 2, "sit")
    ui.safe_addstr(stdscr, 19, 16, "<- the secret", 0)


SCENES = {
    "picker": ("the profile picker: title, framed player table",
               _scene_picker),
    "menu-cat": ("the framed main menu: cat left, options right",
                 _scene_menu_cat),
    "care": ("the care board, framed", _scene_care),
    "shop": ("the shop, framed", _scene_shop),
    "playslot": ("the Play task picker, framed", _scene_playslot),
    "stats": ("stats screen, paginated, heatmap pinned", _scene_stats),
    "scrapbook": ("collection albums", _scene_scrapbook),
    "cats": ("every growth stage, accessory and the secret", _scene_cats),
    "soup": ("Alphabet Soup bowl", _scene_soup),
    "mystery": ("Mystery Word, spelling phase", _scene_mystery),
    "pantry": ("Pantry Defense lanes", _scene_pantry),
    "quiz": ("Whisker Quiz, wrong answer", _scene_quiz),
    "race": ("Ghost Race, two lanes", _scene_race),
    "contest": ("a contest cup mid-run", _scene_contest),
    "yarn": ("Yarn Chase mid-pounce", _scene_yarn),
    "platformer": ("Platform Jumper, cat as the jumper", _scene_platformer),
}


# --- the pty -----------------------------------------------------------


def render(scene, profile_kind="veteran", h=DEFAULT_H, w=DEFAULT_W):
    """Draw `scene` on a real terminal and return the rows it produced."""
    read_fd, write_fd = os.pipe()
    os.environ.update(TERM="xterm-256color", LINES=str(h), COLUMNS=str(w))
    pid, master = os.forkpty()

    if pid == 0:
        os.close(read_fd)
        try:
            import curses
            from core import fx, ui
            stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(True)
            try:
                ui.init_colors()
                fx.clear()
                profile = _profile(profile_kind)
                SCENES[scene][1](stdscr, profile)
                stdscr.refresh()
                # Read by BYTES, not cells. `instr` hands back the
                # multibyte encoding of the row, so a row of braille is
                # up to 3 bytes per column -- asking for `w` bytes
                # returned a third of the line and made a correct screen
                # look shredded.
                rows = [stdscr.instr(y, 0, w * 4).decode("utf-8", "replace")
                        .rstrip() for y in range(h)]
            finally:
                curses.endwin()
            payload = "\n".join(rows)
        except BaseException as exc:          # noqa: BLE001 -- never hang
            payload = "SCENE FAILED: %r" % (exc,)
        with os.fdopen(write_fd, "w", encoding="utf-8") as out:
            out.write(payload)
        os._exit(0)

    os.close(write_fd)
    # Size the terminal, then drain the master or the child blocks as soon
    # as curses fills the buffer. This is the bit that makes it work.
    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", h, w, 0, 0))
    try:
        while True:
            try:
                if not os.read(master, 65536):
                    break
            except OSError:
                break
    finally:
        os.close(master)
    with os.fdopen(read_fd, encoding="utf-8") as fh:
        payload = fh.read()
    os.waitpid(pid, 0)
    return payload.split("\n")


def show(scene, kind, h, w, border=True):
    rows = render(scene, kind, h, w)
    print("=== %s  (%s profile, %dx%d) -- %s"
          % (scene, kind, w, h, SCENES[scene][0]))
    if border:
        print("+" + "-" * w + "+")
        for row in rows:
            print("|" + row.ljust(w)[:w] + "|")
        print("+" + "-" * w + "+")
    else:
        print("\n".join(rows))
    print()
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene", nargs="?", help="scene name; see --list")
    ap.add_argument("--list", action="store_true", help="list scenes")
    ap.add_argument("--all", action="store_true", help="render every scene")
    ap.add_argument("--profile", default="veteran", choices=PROFILES)
    ap.add_argument("--size", default="%dx%d" % (DEFAULT_H, DEFAULT_W),
                    help="HxW, default 24x80 (the supported minimum)")
    ap.add_argument("--out", help="write each scene to a file in this dir")
    args = ap.parse_args(argv)

    if args.list or not (args.scene or args.all):
        print("scenes:")
        for name, (desc, _fn) in sorted(SCENES.items()):
            print("  %-12s %s" % (name, desc))
        print("\nprofiles: %s" % ", ".join(PROFILES))
        return 0

    try:
        h, w = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        ap.error("--size wants HxW, e.g. 24x80")

    names = sorted(SCENES) if args.all else [args.scene]
    for name in names:
        if name not in SCENES:
            ap.error("unknown scene %r; --list to see them" % name)
        rows = show(name, args.profile, h, w)
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            path = os.path.join(args.out, "%s.txt" % name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(rows) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
