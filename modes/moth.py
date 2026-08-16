"""
MOTH CATCH -- endless, score based.

Moths flutter in from the right, each carrying a letter. Type a letter
and the cat bats the nearest matching moth out of the air. Let one slip
past the cat and it's out the window, which costs a life. Three lives,
then it's over. Everything speeds up as your score climbs, so the run
ends when your reaction time runs out rather than at a fixed finish line.

This is the only mode in the game that drills single letters rather than
words -- it's pure reaction on one key at a time, which is what makes it
the right place to spend the adaptive engine's weak-key picks.

Contrast Pantry Defense, which is this same arcade with *words* on the
mice. Both are endless and score-only; the difference is the unit.
"""

import curses
import random
import time

from core import cat, lessons, ui, engine, adaptive, fx, shop
from core.ui import cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT, C_WRONG, C_PENDING, C_ACCENT

# Drawn only for a profile that hasn't hatched a cat yet -- same fallback
# the platformer uses for its jumper.
LEGACY_CAT = [
    "   /\\_/\\    ",
    "  ( o.o )   ",
    "   > ^ <    ",
    "  /     \\   ",
    " (__)_(__)  ",
]
LEGACY_SWAT = [
    "   /\\_/\\    ",
    "  ( -.o )   ",
    "   > ^ <~~o ",
    "  /     \\   ",
    " (__)_(__)  ",
]

FLOOR = "_"

# How far to the right the cat can reach, in columns. Deliberately a
# constant rather than the drawn sprite's width: a kid with a big adult
# cat would otherwise get a wider catching zone than a kid with a kitten,
# and the run speed is tuned against this number.
REACH = 15

# The wings flap between two glyph pairs on this cycle, in seconds.
FLUTTER = 0.18
WINGS = [("}", "{"), (")", "(")]


class Moth:
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


def _next_letter(profile, level):
    """
    Once the kid has fed the adaptive engine, spawns lean on the letters
    they're worst at. Before that (and for saves from before the engine
    existed) it's the old level-based pick.
    """
    if adaptive.has_data(profile):
        return adaptive.weighted_char(profile, random)
    return lessons.random_char(level)


def _draw_cat(stdscr, kitty, swatting, top, left, attr):
    """Paint the cat and return how many rows it took."""
    if kitty is not None:
        pose = "swat" if swatting else "sit"
        kitty.draw(stdscr, top, left, pose)
        return kitty.height(pose)
    art = LEGACY_SWAT if swatting else LEGACY_CAT
    for i, line in enumerate(art):
        safe_addstr(stdscr, top + i, left, line, attr)
    return len(art)


def play(stdscr, profile):
    level = profile.get("tower_level", 1)  # reuse unlocked level as difficulty
    h, w = stdscr.getmaxyx()

    kitty = cat.Cat.from_profile(profile)   # None for a profile with no cat

    lane_top = 4
    lane_rows = max(3, min(7, h - 12))
    cat_top = lane_top + 1
    catch_x = 2 + REACH

    moths = []
    score = 0
    combo = 0
    best_combo = 0
    lives = 3
    swat_until = 0.0
    flash_until = 0.0
    saver_until = 0.0
    sess = engine.Session()
    sess.start_if_needed()

    last_tick = time.monotonic()
    next_spawn = last_tick + 0.6

    curses.curs_set(0)
    stdscr.nodelay(True)
    fx.clear()

    # Treats the kid chose to use before this run. Both are buffers: they
    # forgive or reward, they never type anything for anybody.
    combo_saver = shop.take_effect(profile, shop.EFFECT_COMBO_SAVER)
    bonus_until = 0.0
    if shop.take_effect(profile, shop.EFFECT_BONUS):
        bonus_until = time.monotonic() + shop.BONUS_SECONDS

    running = True
    while running:
        now = time.monotonic()
        dt = now - last_tick
        last_tick = now

        # --- spawn ---
        if now >= next_spawn:
            ch = _next_letter(profile, level)
            row = lane_top + random.randrange(lane_rows)
            moths.append(Moth(ch, w - 2, row))
            next_spawn = now + _spawn_gap(score)

        # --- move ---
        speed = _speed_for(score)
        for m in moths:
            m.x -= speed * dt

        # --- moths that got past the cat ---
        survivors = []
        for m in moths:
            if m.x <= catch_x:
                lives -= 1
                combo = 0
                flash_until = now + 0.25
                if lives <= 0:
                    running = False
            else:
                survivors.append(m)
        moths = survivors

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
            # bat the closest matching moth
            match = None
            for m in moths:
                if m.ch == typed_ch and (match is None or m.x < match.x):
                    match = m
            if match is not None:
                moths.remove(match)
                sess.keystroke(True, ch=match.ch)
                sess.word_done()
                combo += 1
                best_combo = max(best_combo, combo)
                gained = 1 + combo // 10
                if now < bonus_until:
                    gained *= shop.BONUS_MULTIPLIER
                score += gained
                swat_until = now + 0.12
                fx.spawn("spark", match.row, int(match.x))
                if combo and combo % 10 == 0:
                    fx.spawn("confetti", match.row, int(match.x), n=10)
            else:
                # Nothing on screen matched. The letter they *should* have
                # hit is the one closest to the cat, so the miss counts
                # against that key -- there's no other expected char here.
                missed = min(moths, key=lambda m: m.x, default=None)
                sess.keystroke(False, ch=missed.ch if missed else None)
                if combo and combo_saver:
                    combo_saver = False   # the catnip cookie, spent
                    saver_until = now + 1.2
                else:
                    combo = 0
                flash_until = now + 0.15

        # --- draw ---
        stdscr.erase()
        center(stdscr, 0, "M O T H   C A T C H", cp(C_TITLE, True))
        safe_addstr(stdscr, 1, 2, "Score %-6d" % score, cp(C_WARN, True))
        safe_addstr(stdscr, 1, 18, "Combo x%-4d" % combo, cp(C_ACCENT, True))
        safe_addstr(stdscr, 1, 32, "Lives " + "<3 " * max(0, lives), cp(C_WRONG, True))
        safe_addstr(stdscr, 1, max(48, w - 22), "Acc %5.1f%%" % sess.accuracy, cp(C_PENDING))
        if now < bonus_until:
            center(stdscr, 2, "BONUS ROUND -- double score for %.0fs"
                   % (bonus_until - now), cp(C_WARN, True))
        elif now < saver_until:
            center(stdscr, 2, "combo saved!", cp(C_ACCENT, True))

        cat_attr = cp(C_WRONG, True) if now < flash_until else cp(C_CORRECT, True)
        cat_rows = _draw_cat(stdscr, kitty, now < swat_until, cat_top, 2, cat_attr)

        left, right = WINGS[int(now / FLUTTER) % len(WINGS)]
        for m in moths:
            x = int(m.x)
            danger = x < catch_x + 12
            attr = cp(C_WRONG, True) if danger else cp(C_WARN, True)
            if x >= 1:
                safe_addstr(stdscr, m.row, x - 1, left, cp(C_PENDING))
            safe_addstr(stdscr, m.row, x, m.ch.upper(), attr)
            safe_addstr(stdscr, m.row, x + 1, right, cp(C_PENDING))

        floor_row = cat_top + cat_rows
        safe_addstr(stdscr, floor_row, 0, FLOOR * max(0, w - 1), cp(C_PENDING))
        center(stdscr, h - 1, "type the letters before the moths slip past   -   ESC to quit",
               cp(C_PENDING))
        fx.tick(dt)
        fx.draw(stdscr)   # after the scene, so sparks land on top of it
        stdscr.refresh()

        curses.napms(33)  # ~30fps -- smooth enough, and easy on the Pi

    stdscr.nodelay(False)
    sess.finish()

    if score > profile.get("moth_high_score", 0):
        profile["moth_high_score"] = score
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
            "High score: %d" % profile["moth_high_score"],
        ],
        title=headline,
        art=kitty.art("swat") if kitty is not None else LEGACY_SWAT,
    )

    return sess.summary()
