"""
MYSTERY WORD -- word production, disguised as a covered dish.

The cat paws at something under a lid. Guess letters to reveal what's
written on it; once enough is showing, spell the whole thing out and the
dish opens. Hangman's mechanic, with everything that punishes taken out.

Why it exists: every other mode in the game is transcription. The target
is on screen and the kid copies it. Here the word is *hidden*, so they
have to produce it from partial information -- spelling from deduction
rather than from sight, which is a different skill and the one no other
mode touches.

What it deliberately doesn't do:

- **Nothing is lost.** Six wrong guesses ends the round with the dish
  still covered and a "maybe tomorrow"; no fish, no streak, no progress.
  There is no gallows and nothing gets drawn on it.
- **Guesses aren't drill data.** Letter guessing is deduction, not typing,
  so `keystroke` is only called during the final spelling -- the one part
  where the kid is actually producing a known word. Same reasoning as
  Alphabet Soup (#25), and the same reason accuracy is accounted at
  submit time rather than per keypress.
- **Words are always solvable.** They're drawn from the kid's unlocked
  alphabet, so no round can hinge on a letter they've never met.
"""

import curses
import random
import time

from core import adaptive, cat, engine, fx, ui, wordlist
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

DISHES = 3               # covered dishes per visit
MAX_WRONG = 6            # whisker droops before the round ends softly
REVEAL_SHARE = 0.5       # distinct letters showing before spelling opens

LID = [
    "   .-------.   ",
    "  /         \\  ",
    " '-----------' ",
]
LID_OPEN = [
    "      ___      ",
    "  .-'     '-.  ",
    " '-----------' ",
]


def word_lengths(alphabet):
    """
    Word length grows with the alphabet (#24).

    Three letters is the floor everywhere; the ceiling opens up as the kid
    meets more of the alphabet, which is also when longer words start
    existing in their pool at all.
    """
    return 3, max(4, min(8, 3 + len(alphabet) // 5))


def candidates(alphabet, path=None):
    """Every real word this kid could possibly solve."""
    lo, hi = word_lengths(alphabet)
    return wordlist.for_alphabet(alphabet, path=path, min_len=lo, max_len=hi)


def pick_words(alphabet, rng, n=DISHES, path=None):
    """`n` distinct words, or as many as the pool can offer."""
    pool = candidates(alphabet, path=path)
    if not pool:
        return []
    rng.shuffle(pool)
    return pool[:n]


def reveal_target(word):
    """How many distinct letters must show before spelling unlocks."""
    distinct = len(set(word))
    return max(1, int(round(distinct * REVEAL_SHARE)))


def masked(word, found):
    """The word as blanks, with guessed letters filled in."""
    return " ".join(ch if ch in found else "_" for ch in word)


def is_solved(word, found):
    return all(ch in found for ch in word)


def _whiskers(wrong):
    """
    The droop meter. Whiskers sag as guesses miss -- it's a mood, not a
    health bar, and nothing is ever drawn being harmed.
    """
    left = MAX_WRONG - wrong
    return "/" * left + "." * wrong


def _draw(stdscr, kitty, pose, word, found, wrong, dish, total, spelling,
          typed, msg, msg_ok, opened):
    h, w = stdscr.getmaxyx()
    stdscr.erase()

    center(stdscr, 0, "M Y S T E R Y   W O R D", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Dish %d of %d" % (dish, total), cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 22, "whiskers %s" % _whiskers(wrong),
                cp(C_WRONG if wrong >= MAX_WRONG - 1 else C_WARN, True))

    art = LID_OPEN if opened else LID
    lid_x = max(2, w // 2 - len(art[0]) // 2)
    top = 3
    for i, row in enumerate(art):
        safe_addstr(stdscr, top + i, lid_x, row, cp(C_ACCENT, True))

    if kitty is not None:
        kitty.draw(stdscr, top, max(0, lid_x - kitty.width(pose) - 3), pose)

    shown = masked(word, found)
    center(stdscr, top + 5, shown, cp(C_TITLE, True))

    if found:
        guessed = " ".join(sorted(found))
        center(stdscr, top + 7, "tried: " + guessed, cp(C_PENDING))

    if spelling:
        center(stdscr, top + 9, "Spell it out to open the dish!",
               cp(C_CORRECT, True))
        # Only ever render what the kid has typed. `draw_typing_line`
        # paints the *target*, which everywhere else is the point and here
        # would hand them the answer -- this is the one mode where the
        # word must stay hidden until they produce it. Spacing matches the
        # mask above so the two line up as the same puzzle.
        span = len(word) * 2 - 1
        tx = max(0, (w - span) // 2)
        for i in range(len(word)):
            if i < len(typed):
                glyph, attr = typed[i], cp(C_CORRECT, True)
            else:
                glyph, attr = "_", cp(C_PENDING)
            safe_addstr(stdscr, top + 10, tx + i * 2, glyph, attr)
    else:
        center(stdscr, top + 9, "Type a letter to guess", cp(C_PENDING))

    if msg:
        center(stdscr, top + 12, msg, cp(C_CORRECT if msg_ok else C_WRONG, True))

    center(stdscr, h - 1, "ESC to stop -- nothing here is ever lost",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def play(stdscr, profile):
    kitty = cat.Cat.from_profile(profile)
    alphabet = adaptive.alphabet(profile)
    rng = random.Random()

    words = pick_words(alphabet, rng)
    if not words:
        ui.message(stdscr,
                   ["There's nothing under the lid yet!",
                    "",
                    "Learn a few more letters and come back."],
                   title="NOT YET")
        return None

    sess = engine.Session()
    opened_count = 0
    name = kitty.name if kitty else "Your cat"

    curses.curs_set(0)
    stdscr.nodelay(False)
    fx.clear()

    for index, word in enumerate(words, start=1):
        found = set()
        wrong = 0
        spelling = False
        typed = ""
        msg, msg_ok = "", True
        pose = "swat"
        opened = False
        quit_now = False

        while True:
            _draw(stdscr, kitty, pose, word, found, wrong, index, len(words),
                  spelling, typed, msg, msg_ok, opened)

            if opened:
                curses.napms(900)
                break

            key = stdscr.getch()
            if engine.is_quit(key):
                quit_now = True
                break

            if spelling:
                if engine.is_backspace(key):
                    typed = typed[:-1]
                    continue
                if not engine.is_typable(key):
                    continue
                ch = chr(key).lower()
                if not ch.isalpha():
                    continue

                expected = word[len(typed)] if len(typed) < len(word) else None
                if expected is not None and ch == expected:
                    # The only keystrokes worth learning from: the kid is
                    # producing a word they now know, one letter at a time.
                    typed += ch
                    sess.keystroke(True, ch=expected)
                    if typed == word:
                        sess.word_done()
                        opened = True
                        opened_count += 1
                        pose = "overjoyed"
                        msg, msg_ok = "It's %s! The dish opens." % word, True
                        h, w = stdscr.getmaxyx()
                        fx.spawn("confetti", 4, w // 2)
                else:
                    sess.keystroke(False, ch=expected)
                    msg, msg_ok = "not quite -- backspace and try again", False
                continue

            # --- guessing phase ---
            if not engine.is_typable(key):
                continue
            ch = chr(key).lower()
            if not ch.isalpha():
                continue
            if ch in found:
                msg, msg_ok = "You already tried '%s'." % ch, True
                continue

            found.add(ch)
            if ch in word:
                pose = "overjoyed"
                msg, msg_ok = "Yes! There's a '%s'." % ch, True
                fx.spawn("spark", 8, stdscr.getmaxyx()[1] // 2)
            else:
                wrong += 1
                pose = "wary"
                msg = "No '%s' in there." % ch
                msg_ok = False

            revealed = len({c for c in word if c in found})
            if is_solved(word, found):
                # They guessed every letter -- the dish is already readable,
                # so spelling it is a formality, not a second puzzle.
                spelling = True
                msg, msg_ok = "You've got it all -- now spell it!", True
            elif revealed >= reveal_target(word):
                spelling = True
                msg, msg_ok = "Enough showing -- spell it out!", True
            elif wrong >= MAX_WRONG:
                pose = "loaf"
                _draw(stdscr, kitty, pose, word, found, wrong, index,
                      len(words), False, "", "", True, False)
                ui.message(
                    stdscr,
                    ["The dish stays covered this time.",
                     "",
                     "It was '%s'." % word,
                     "",
                     "Maybe tomorrow! Nothing was lost."],
                    title="MAYBE TOMORROW",
                    art=kitty.art("loaf") if kitty else None,
                )
                break

        if quit_now:
            break

    sess.finish()

    profile["mystery_opened"] = profile.get("mystery_opened", 0) + opened_count

    if opened_count:
        title = "WHAT A NOSE"
        lines = ["%s opened %d dish%s." % (name, opened_count,
                                           "" if opened_count == 1 else "es")]
    else:
        title = "MAYBE LATER"
        lines = ["No dishes this time -- that's alright.",
                 "", "%s will bring them back." % name]

    lines += ["", "Dishes opened, all time: %d" % profile["mystery_opened"]]

    ui.message(stdscr, lines, title=title,
               art=kitty.art("overjoyed" if opened_count else "sit")
               if kitty else None)
    return sess.summary()
