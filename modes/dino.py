"""
DINO CHOMP -- endless, score based.

Letters drift in from the right. Type a letter and the dino chomps
the closest matching one. Let a letter reach the dino's mouth and you
lose a life. Three lives, then it's over. Everything speeds up as your
score climbs, so the run ends when your reaction time runs out rather
than at a fixed finish line.
"""

import curses
import random
import time

from core import lessons, ui, engine
from core.ui import cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT, C_WRONG, C_PENDING, C_ACCENT

DINO_IDLE = [
    "         _____ ",
    "        / o   \\",
    "       /      |",
    "  ____/    ___|",
    " /         |   ",
    "/  ________|   ",
    "\\_/  ||  ||    ",
]

DINO_CHOMP = [
    "         _____ ",
    "        / o   \\",
    "       /   \\  |",
    "  ____/    /__|",
    " /         |   ",
    "/  ________|   ",
    "\\_/  ||  ||    ",
]

GROUND = "^"
DINO_W = 15
MOUTH_ROW_OFFSET = 3


class Letter:
    __slots__ = ("ch", "x", "row")

    def __init__(self, ch, x, row):
        self.ch = ch
        self.x = float(x)
        self.row = row


def _speed_for(score):
    """Columns per second. Ramps up but flattens so it stays playable."""
    return 6.0 + min(14.0, score * 0.06)


def _spawn_gap(score):
    """Seconds between spawns."""
    return max(0.35, 1.1 - score * 0.004)


def play(stdscr, profile):
    level = profile.get("rocket_level", 1)  # reuse unlocked level as difficulty
    h, w = stdscr.getmaxyx()

    lane_top = 4
    lane_rows = max(3, min(7, h - 12))
    dino_top = lane_top + 1
    mouth_x = 2 + DINO_W
    mouth_row = dino_top + MOUTH_ROW_OFFSET

    letters = []
    score = 0
    combo = 0
    best_combo = 0
    lives = 3
    chomp_until = 0.0
    flash_until = 0.0
    sess = engine.Session()
    sess.start_if_needed()

    last_tick = time.monotonic()
    next_spawn = last_tick + 0.6

    curses.curs_set(0)
    stdscr.nodelay(True)

    running = True
    while running:
        now = time.monotonic()
        dt = now - last_tick
        last_tick = now

        # --- spawn ---
        if now >= next_spawn:
            ch = lessons.random_char(level)
            row = lane_top + random.randrange(lane_rows)
            letters.append(Letter(ch, w - 2, row))
            next_spawn = now + _spawn_gap(score)

        # --- move ---
        speed = _speed_for(score)
        for L in letters:
            L.x -= speed * dt

        # --- collisions with the dino ---
        survivors = []
        for L in letters:
            if L.x <= mouth_x:
                lives -= 1
                combo = 0
                flash_until = now + 0.25
                if lives <= 0:
                    running = False
            else:
                survivors.append(L)
        letters = survivors

        # --- input ---
        while True:
            key = stdscr.getch()
            if key == -1:
                break
            if engine.is_quit(key):
                running = False
                break
            if not engine.is_typable(key):
                continue

            typed_ch = chr(key)
            # chomp the closest matching letter
            match = None
            for L in letters:
                if L.ch == typed_ch and (match is None or L.x < match.x):
                    match = L
            if match is not None:
                letters.remove(match)
                sess.keystroke(True)
                sess.word_done()
                combo += 1
                best_combo = max(best_combo, combo)
                score += 1 + combo // 10
                chomp_until = now + 0.12
            else:
                sess.keystroke(False)
                combo = 0
                flash_until = now + 0.15

        # --- draw ---
        stdscr.erase()
        center(stdscr, 0, "D I N O   C H O M P", cp(C_TITLE, True))
        safe_addstr(stdscr, 1, 2, "Score %-6d" % score, cp(C_WARN, True))
        safe_addstr(stdscr, 1, 18, "Combo x%-4d" % combo, cp(C_ACCENT, True))
        safe_addstr(stdscr, 1, 32, "Lives " + "<3 " * max(0, lives), cp(C_WRONG, True))
        safe_addstr(stdscr, 1, max(48, w - 22), "Acc %5.1f%%" % sess.accuracy, cp(C_PENDING))

        art = DINO_CHOMP if now < chomp_until else DINO_IDLE
        dino_attr = cp(C_WRONG, True) if now < flash_until else cp(C_CORRECT, True)
        for i, line in enumerate(art):
            safe_addstr(stdscr, dino_top + i, 2, line, dino_attr)

        for L in letters:
            x = int(L.x)
            danger = x < mouth_x + 12
            attr = cp(C_WRONG, True) if danger else cp(C_WARN, True)
            safe_addstr(stdscr, L.row, x, L.ch.upper(), attr)

        ground_row = dino_top + len(art)
        safe_addstr(stdscr, ground_row, 0, GROUND * max(0, w - 1), cp(C_PENDING))
        center(stdscr, h - 1, "type the letters before they reach the dino   -   ESC to quit",
               cp(C_PENDING))
        stdscr.refresh()

        curses.napms(33)  # ~30fps -- smooth enough, and easy on the Pi

    stdscr.nodelay(False)
    sess.finish()

    if score > profile.get("dino_high_score", 0):
        profile["dino_high_score"] = score
        headline = "NEW HIGH SCORE!"
    else:
        headline = "GAME OVER"

    ui.message(
        stdscr,
        [
            "Score: %d" % score,
            "Best combo: x%d" % best_combo,
            "Accuracy: %.1f%%" % sess.accuracy,
            "",
            "High score: %d" % profile["dino_high_score"],
        ],
        title=headline,
        art=DINO_CHOMP,
    )

    return sess.summary()
