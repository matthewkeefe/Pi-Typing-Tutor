"""
PANTRY DEFENSE -- word arcade.

Dino Chomp's engine with words instead of single letters. Mice sneak in
from the right, each carrying a word; type a mouse's word and the cat
swats it away. Let one reach the food bowl and it costs a life. Three
lives, then the score screen.

The stakes are score-only, on purpose. A mouse that gets through takes a
life and nothing else -- it never eats fish, never touches the streak,
never undoes a day's care. Losing a run here should feel like losing a
game, not like losing progress.

Words come from `adaptive.generate_lesson`, so this drills the letters the
kid is worst at, and per-key capture is on: the engine chose these words,
which is exactly the case where the keystrokes are worth learning from.
(Contrast Alphabet Soup and Mystery Word, where the kid picks the word and
capture stays off.)
"""

import curses
import random
import time

from core import adaptive, cat, engine, fx, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_WRONG, C_PENDING, C_ACCENT)

LIVES = 3
MOUSE = "o~"            # nose leads: these are moving left
GAP = 1                 # spaces between the mouse and its word

BOWL = [
    " \\_____/ ",
    "  \\___/  ",
]
BOWL_W = 9


class Mouse:
    __slots__ = ("word", "x", "row")

    def __init__(self, word, x, row):
        self.word = word
        self.x = float(x)
        self.row = row

    @property
    def word_x(self):
        return int(self.x) + len(MOUSE) + GAP

    @property
    def width(self):
        return len(MOUSE) + GAP + len(self.word)


def speed_for(score):
    """Columns per second. Ramps, then flattens so it stays playable."""
    return 3.0 + min(7.0, score * 0.02)


def spawn_gap(score):
    """Seconds between mice. Never below a beat you can read a word in."""
    return max(1.1, 2.6 - score * 0.01)


def max_on_screen(score):
    """Simultaneous mice, so the ramp is pressure as well as pace."""
    return min(5, 2 + score // 60)


def max_word_len(alphabet):
    """
    Word length scales with the alphabet (#19).

    A kid six letters in is reading four-letter words under time pressure;
    by the full alphabet they're on seven. Longer than that stops being a
    typing test and starts being a reading test.
    """
    return max(3, min(7, 3 + len(alphabet) // 5))


def _refill(profile, limit, rng):
    """A fresh pool of words no longer than `limit`."""
    words = adaptive.generate_lesson(profile, 24, rng)
    short = [w for w in words if len(w) <= limit]
    if not short:
        # Every generated word was too long: truncate rather than block.
        short = [w[:limit] for w in words if len(w) >= 3]
    return short or ["cat"]


def pick_word(pool, live_words):
    """
    A word that doesn't collide with anything already on screen.

    If "cat" is live and "cats" spawns, typing c-a-t shoos the first and
    the second can never be completed. Refusing prefix pairs is cheaper
    than teaching the input loop to disambiguate them.
    """
    for word in pool:
        if any(w.startswith(word) or word.startswith(w) for w in live_words):
            continue
        return word
    return None


def matches(mice, typed):
    """Every mouse whose word starts with what's been typed so far."""
    if not typed:
        return []
    return [m for m in mice if m.word.startswith(typed)]


def nearest(candidates):
    """Closest to the bowl wins ties -- the same rule Dino Chomp uses."""
    return min(candidates, key=lambda m: m.x, default=None)


def _draw(stdscr, kitty, pose, mice, typed, score, combo, lives, accuracy,
          guard_x, bowl_x, lane_top, flash, msg=None):
    h, w = stdscr.getmaxyx()
    stdscr.erase()

    center(stdscr, 0, "P A N T R Y   D E F E N S E", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Score %-6d" % score, cp(C_WARN, True))
    safe_addstr(stdscr, 1, 18, "Combo x%-4d" % combo, cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 32, "Lives " + "<3 " * max(0, lives),
                cp(C_WRONG, True))
    safe_addstr(stdscr, 1, max(48, w - 22), "Acc %5.1f%%" % accuracy,
                cp(C_PENDING))
    if msg:
        center(stdscr, 2, msg, cp(C_WRONG, True))

    # The bowl being defended, and the cat standing over it.
    bowl_attr = cp(C_WRONG, True) if flash else cp(C_ACCENT, True)
    for i, row in enumerate(BOWL):
        safe_addstr(stdscr, lane_top + 3 + i, bowl_x, row, bowl_attr)
    if kitty is not None:
        kitty.draw(stdscr, lane_top + 1, bowl_x + BOWL_W + 1, pose)
    else:
        safe_addstr(stdscr, lane_top + 3, bowl_x + BOWL_W + 2, "(_)",
                    cp(C_WARN, True))

    for m in mice:
        x = int(m.x)
        danger = x < guard_x + 14
        safe_addstr(stdscr, m.row, x, MOUSE,
                    cp(C_WRONG, True) if danger else cp(C_PENDING, True))
        if typed and m.word.startswith(typed):
            # Same per-character renderer the drills use, so a partially
            # typed word looks identical wherever a kid meets one.
            ui.draw_typing_line(stdscr, m.row, m.word_x, m.word, typed)
        else:
            safe_addstr(stdscr, m.row, m.word_x, m.word,
                        cp(C_WRONG, True) if danger else cp(C_WARN, True))

    safe_addstr(stdscr, h - 3, 0, "=" * max(0, w - 1), cp(C_PENDING))
    if typed:
        safe_addstr(stdscr, h - 2, 2, "typing: " + typed, cp(C_CORRECT, True))

    center(stdscr, h - 1,
           "type a mouse's word to shoo it   -   ESC to quit", cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def play(stdscr, profile):
    kitty = cat.Cat.from_profile(profile)
    alphabet = adaptive.alphabet(profile)
    limit = max_word_len(alphabet)
    rng = random

    h, w = stdscr.getmaxyx()
    lane_top = 4
    # Lanes run from just under the header down to the counter line at
    # h-3. Capped so a handful of mice don't rattle around in a tall
    # terminal, floored so it still works at the 80x24 minimum.
    lane_rows = max(3, min(8, h - 3 - lane_top - 1))
    bowl_x = 2
    cat_w = kitty.width("sit") if kitty else 3
    guard_x = bowl_x + BOWL_W + 1 + cat_w

    mice = []
    pool = _refill(profile, limit, rng)
    score = 0
    combo = 0
    best_combo = 0
    lives = LIVES
    shooed = 0
    typed = ""
    pose = "sit"
    pose_until = 0.0
    flash_until = 0.0
    msg = None
    msg_until = 0.0

    sess = engine.Session()
    sess.start_if_needed()

    curses.curs_set(0)
    stdscr.nodelay(True)
    fx.clear()

    last_tick = time.monotonic()
    next_spawn = last_tick + 0.8
    running = True

    while running:
        now = time.monotonic()
        dt = now - last_tick
        last_tick = now

        if pose_until and now > pose_until:
            pose, pose_until = "sit", 0.0
        if msg_until and now > msg_until:
            msg, msg_until = None, 0.0

        # --- spawn ---
        if now >= next_spawn and len(mice) < max_on_screen(score):
            if not pool:
                pool = _refill(profile, limit, rng)
            live = [m.word for m in mice]
            word = pick_word(pool, live)
            if word is not None:
                pool.remove(word)
                row = lane_top + rng.randrange(lane_rows)
                mice.append(Mouse(word, w - 3, row))
            next_spawn = now + spawn_gap(score)

        # --- move ---
        speed = speed_for(score)
        for m in mice:
            m.x -= speed * dt

        # --- anything reaching the bowl ---
        survivors = []
        for m in mice:
            if m.x <= guard_x:
                lives -= 1
                combo = 0
                typed = ""
                flash_until = now + 0.3
                pose, pose_until = "wary", now + 0.5
                msg = "a mouse got to the bowl!"
                msg_until = now + 1.2
                if lives <= 0:
                    running = False
            else:
                survivors.append(m)
        mice = survivors

        # --- input ---
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

            ch = chr(key).lower()
            if not ch.isalpha():
                continue

            attempt = typed + ch
            hits = matches(mice, attempt)

            if hits:
                # The character was right for at least one mouse on screen.
                expected = ch
                sess.keystroke(True, ch=expected)
                typed = attempt

                done = [m for m in hits if m.word == typed]
                if done:
                    target = nearest(done)
                    mice.remove(target)
                    sess.word_done()
                    shooed += 1
                    combo += 1
                    best_combo = max(best_combo, combo)
                    score += len(target.word) + combo // 5
                    pose, pose_until = "swat", now + 0.35
                    fx.spawn("spark", target.row, int(target.x))
                    if combo and combo % 10 == 0:
                        fx.spawn("confetti", target.row, int(target.x), n=10)
                    typed = ""
            else:
                # Nothing on screen continues this prefix. The letter they
                # should have hit belongs to the nearest mouse still
                # matching what they'd typed before -- same reasoning as
                # Dino Chomp's nearest-match attribution.
                still = nearest(matches(mice, typed)) if typed else nearest(mice)
                expected = None
                if still is not None and len(typed) < len(still.word):
                    expected = still.word[len(typed)]
                sess.keystroke(False, ch=expected)
                combo = 0
                typed = ""
                flash_until = now + 0.15

        _draw(stdscr, kitty, pose, mice, typed, score, combo, lives,
              sess.accuracy, guard_x, bowl_x, lane_top,
              now < flash_until, msg)
        curses.napms(33)

    stdscr.nodelay(False)
    sess.finish()

    if score > profile.get("pantry_high_score", 0):
        profile["pantry_high_score"] = score
        headline = "NEW HIGH SCORE!"
    else:
        headline = "THE PANTRY IS RAIDED"

    name = kitty.name if kitty else "Your cat"
    ui.message(
        stdscr,
        [
            "%s shooed %d mouse%s away." % (name, shooed,
                                            "" if shooed == 1 else "s"),
            "",
            "Score: %d" % score,
            "Best combo: x%d" % best_combo,
            "Accuracy: %.1f%%" % sess.accuracy,
            "",
            "High score: %d" % profile.get("pantry_high_score", 0),
        ],
        title=headline,
        art=kitty.portrait_art("swat") if kitty else None,
    )

    return sess.summary()
