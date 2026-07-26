"""
WHISKER QUIZ -- the cat asks, the kid types the answer.

Typing of the Dead's boss format: read a question, type the answer. It
combines reading comprehension with typing, and it turns the tutor into a
general study tool -- the questions live in `data/quiz.txt`, which a parent
can replace with this week's spelling words, times tables, or anything
else. Same pattern as `data/passages.txt`.

Kindness rules, all of them load-bearing:

- **No lives.** A wrong answer shows the right one, the cat tilts its head,
  and the question goes back into the deck to come round again. Missing
  something is how you learn it.
- **Matching is forgiving.** Case and surrounding whitespace never matter,
  internal runs of spaces collapse, and a question can list alternates so
  "8" and "eight" both land. Being marked wrong on a technicality is the
  fastest way to lose a seven-year-old.
- **A question only comes back once.** Spaced repetition needs a second
  look, not an interrogation; the second miss moves on.

The mode hides itself when there are no questions, so deleting the file
removes the feature rather than breaking the menu.
"""

import curses
import os
import random

from core import cat, engine, fx, ui
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "quiz.txt",
)

ROUND = 8            # questions per visit
RETRY_LIMIT = 1      # times a missed question comes back
MAX_ANSWER = 24      # input box width

_CACHE = {}


def normalize(text):
    """Case, surrounding space and internal runs of space all forgiven."""
    return " ".join(text.strip().lower().split())


def load(path=None):
    """
    `[(question, [answers...]), ...]`, read once per path and cached.

    Malformed lines are skipped rather than raised on: a parent editing
    this file by hand should get the questions that work, not a crash on
    the menu. A missing file simply yields nothing.
    """
    path = path or DATA
    if path not in _CACHE:
        out = []
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    s = line.strip()
                    if not s or s.startswith("#") or "|" not in s:
                        continue
                    q, _, a = s.partition("|")
                    q = q.strip()
                    answers = [normalize(x) for x in a.split(";") if x.strip()]
                    if not q or not answers:
                        continue
                    out.append((q, answers))
        except OSError:
            out = []
        _CACHE[path] = out
    return _CACHE[path]


def reset_cache():
    """Drop the cache. For tests pointing at a fixture file."""
    _CACHE.clear()


def available(profile=None):
    """No questions, no mode. Cheap: `load` is cached."""
    return bool(load())


def is_correct(given, answers):
    return normalize(given) in answers


def pick_round(questions, rng, n=ROUND):
    pool = list(questions)
    rng.shuffle(pool)
    return pool[:n]


def _wrap(text, width):
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if len(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]


def _draw(stdscr, kitty, pose, question, typed, index, total, right,
          msg, msg_ok):
    h, w = stdscr.getmaxyx()
    stdscr.erase()

    center(stdscr, 0, "W H I S K E R   Q U I Z", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Question %d of %d" % (index, total),
                cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 26, "Right %d" % right, cp(C_CORRECT, True))

    bubble_w = min(52, max(20, w - 24))
    lines = _wrap(question, bubble_w)
    bubble_x = max(2, (w - bubble_w) // 2 - 4)
    top = 3
    ui.speech_bubble(stdscr, top, bubble_x, lines, cp(C_WARN, True), tail_x=4)

    cat_y = top + len(lines) + 3
    if kitty is not None:
        kitty.draw(stdscr, cat_y, bubble_x + 1, pose)
        below = cat_y + kitty.height(pose)
    else:
        safe_addstr(stdscr, cat_y, bubble_x + 1, "(_)", cp(C_WARN, True))
        below = cat_y + 1

    prompt_row = min(h - 6, below + 2)
    center(stdscr, prompt_row, "Type your answer and press ENTER",
           cp(C_PENDING))

    box_w = MAX_ANSWER + 2
    bx = max(2, (w - box_w) // 2)
    safe_addstr(stdscr, prompt_row + 2, bx, "[" + " " * box_w + "]",
                cp(C_PENDING))
    safe_addstr(stdscr, prompt_row + 2, bx + 1, (typed + "_")[:box_w],
                cp(C_CORRECT, True))

    if msg:
        for i, line in enumerate(_wrap(msg, w - 8)[:2]):
            center(stdscr, prompt_row + 4 + i, line,
                   cp(C_CORRECT if msg_ok else C_WRONG, True))

    center(stdscr, h - 1, "ESC to stop -- nothing here is ever lost",
           cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def _is_enter(key):
    return key in (10, 13, curses.KEY_ENTER)


def play(stdscr, profile):
    questions = load()
    if not questions:
        ui.message(stdscr,
                   ["There are no questions yet!",
                    "",
                    "Put some in data/quiz.txt and the cat will ask them."],
                   title="NOTHING TO ASK")
        return None

    kitty = cat.Cat.from_profile(profile)
    rng = random.Random()
    deck = [[q, a, 0] for q, a in pick_round(questions, rng)]
    total = len(deck)

    sess = engine.Session()
    right = 0
    results = []          # (question, got_it)
    typed = ""
    pose = "sit"
    msg, msg_ok = "", True
    asked = 0

    curses.curs_set(0)
    stdscr.nodelay(False)
    fx.clear()

    while deck:
        question, answers, tries = deck.pop(0)
        asked += 1
        typed = ""
        pose = "sit"

        answered = False
        while not answered:
            _draw(stdscr, kitty, pose, question, typed,
                  min(asked, total), total, right, msg, msg_ok)
            key = stdscr.getch()

            if engine.is_quit(key):
                deck = []
                break
            if engine.is_backspace(key):
                typed = typed[:-1]
                continue
            if _is_enter(key):
                if not typed.strip():
                    continue
                answered = True
                continue
            if engine.is_typable(key) and len(typed) < MAX_ANSWER:
                sess.start_if_needed()
                typed += chr(key)

        if not answered:
            break

        if is_correct(typed, answers):
            # Capture on: we now know exactly which characters the kid
            # meant, so every one can be attributed to its key. Done at
            # submit rather than per keypress because until ENTER there
            # is no expected character to compare against -- the kid is
            # producing an answer, not copying a target.
            for ch in normalize(typed):
                sess.keystroke(True, ch=ch if ch != " " else None)
            sess.word_done()
            right += 1
            results.append((question, True))
            pose = "overjoyed"
            msg, msg_ok = "Yes! That's right.", True
            h, w = stdscr.getmaxyx()
            fx.spawn("spark", 4, w // 2)
        else:
            # A miss can't be attributed to any key -- we don't know what
            # they were reaching for -- so the characters count against
            # accuracy without touching per-key statistics.
            for _ in typed:
                sess.keystroke(False)
            pose = "wary"
            msg = "Not quite -- it's '%s'." % answers[0]
            msg_ok = False
            if tries < RETRY_LIMIT:
                # Spaced-repetition-lite: back into the deck, a few
                # questions later, so it comes round again once.
                where = min(len(deck), 2)
                deck.insert(where, [question, answers, tries + 1])
                msg += " We'll come back to it."
            else:
                results.append((question, False))

        _draw(stdscr, kitty, pose, question, typed,
              min(asked, total), total, right, msg, msg_ok)
        curses.napms(1100)
        msg, msg_ok = "", True

    sess.finish()
    stdscr.nodelay(False)

    profile["quiz_right"] = profile.get("quiz_right", 0) + right

    name = kitty.name if kitty else "Your cat"
    lines = []
    for question, got in results[:8]:
        mark = "+" if got else "-"
        lines.append("%s %s" % (mark, question[:56]))
    if not lines:
        lines = ["No questions answered this time."]

    if right == total and total:
        title = "EVERY ONE!"
        head = "%s is very impressed." % name
    elif right:
        title = "GOOD THINKING"
        head = "%d right out of %d." % (right, total)
    else:
        title = "MAYBE LATER"
        head = "%s liked the company anyway." % name

    ui.message(stdscr, [head, ""] + lines, title=title,
               art=kitty.art("overjoyed" if right else "sit") if kitty else None)
    return sess.summary()
