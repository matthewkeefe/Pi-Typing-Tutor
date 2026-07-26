"""
MEMORIZE -- repetition with progressive occlusion.

Straight repetition gets you copying, not remembering. So this mode
hides more of the text on every successful pass:

    reps 1-2   full text shown
    rep 3      25% of words blanked
    rep 4      50% blanked
    rep 5      75% blanked
    rep 6      fully blanked -- pure recall

Finish the blind pass and it counts as memorized. There's a peek key
(TAB) that reveals the text for a moment; peeking doesn't fail you,
it just gets logged so you can see how much scaffolding you needed.

Passages come from data/passages.txt if it exists (one per line,
blank-line separated for multi-line entries), otherwise the built-ins
below are used.
"""

import curses
import os
import random
import time

from core import ui, engine, profiles
from core.ui import cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT, C_WRONG, C_PENDING, C_ACCENT

BUILTIN = [
    "the quick brown fox jumps over the lazy dog",
    "practice does not make perfect practice makes permanent",
    "a journey of a thousand miles begins with a single step",
    "i think therefore i am",
    "the only way out is through",
    "every letter has a home key and every finger has a job",
    "curiosity is the engine of achievement",
    "we are made of star stuff",
]

REVEAL_SCHEDULE = [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]
PEEK_SECONDS = 1.5


def load_passages():
    path = os.path.join(profiles.DATA_DIR, "passages.txt")
    if not os.path.exists(path):
        return BUILTIN[:]
    try:
        with open(path) as f:
            raw = [ln.strip() for ln in f]
        found = [ln for ln in raw if ln and not ln.startswith("#")]
        return found or BUILTIN[:]
    except OSError:
        return BUILTIN[:]


def _occlude(text, fraction, seed):
    """
    Blank out `fraction` of the words, deterministically per rep so the
    same blanks stay blank for the whole attempt.
    """
    words = text.split(" ")
    if fraction <= 0:
        return " ".join(words)
    rng = random.Random(seed)
    n = int(round(len(words) * fraction))
    hide = set(rng.sample(range(len(words)), min(n, len(words))))
    return " ".join("_" * len(w) if i in hide else w for i, w in enumerate(words))


def _wrap(text, width):
    lines, cur = [], ""
    for word in text.split(" "):
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw(stdscr, text, shown, typed, rep, total_reps, peeking, peeks, sess):
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    width = min(64, w - 8)

    center(stdscr, 0, "M E M O R I Z E", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Pass %d of %d" % (rep + 1, total_reps), cp(C_WARN, True))
    hidden_pct = int(REVEAL_SCHEDULE[min(rep, len(REVEAL_SCHEDULE) - 1)] * 100)
    safe_addstr(stdscr, 1, 20, "Hidden %d%%" % hidden_pct, cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 36, "Peeks %d" % peeks, cp(C_PENDING))

    prompt = text if peeking else shown
    center(stdscr, 3, "-- prompt --" + ("  (peeking)" if peeking else ""),
           cp(C_WARN if peeking else C_PENDING))
    x0 = max(0, (w - width) // 2)
    for i, line in enumerate(_wrap(prompt, width)):
        attr = cp(C_WARN) if peeking else cp(C_PENDING, True)
        safe_addstr(stdscr, 4 + i, x0, line, attr)

    top = 4 + len(_wrap(prompt, width)) + 2
    center(stdscr, top, "-- your typing --", cp(C_PENDING))

    # Render what they've typed against the real text, wrapped
    real_lines = _wrap(text, width)
    consumed = 0
    for i, line in enumerate(real_lines):
        seg_typed = typed[consumed:consumed + len(line)]
        ui.draw_typing_line(stdscr, top + 1 + i, x0, line, seg_typed)
        consumed += len(line) + 1  # +1 for the space we wrapped on

    foot = top + 1 + len(real_lines) + 2
    safe_addstr(stdscr, foot, x0, "WPM %.1f    Accuracy %.1f%%" % (sess.wpm, sess.accuracy),
                cp(C_WARN))
    center(stdscr, h - 1, "TAB to peek   BACKSPACE to fix   ESC to quit", cp(C_PENDING))
    stdscr.refresh()


def play(stdscr, profile):
    passages = load_passages()

    choice = ui.menu(
        stdscr,
        "Pick something to memorize",
        [p[:52] + ("..." if len(p) > 52 else "") for p in passages] + ["(type my own)"],
        subtitle="you'll type it until you can do it with no prompt",
    )
    if choice == -1:
        return None

    if choice == len(passages):
        custom = ui.ask_text(stdscr, "Type the text to memorize", maxlen=120)
        if not custom:
            return None
        text = custom.strip()
    else:
        text = passages[choice]

    total_reps = len(REVEAL_SCHEDULE)
    sess = engine.Session()
    peeks = 0
    seed = random.randrange(10000)

    curses.curs_set(0)

    for rep in range(total_reps):
        fraction = REVEAL_SCHEDULE[rep]
        shown = _occlude(text, fraction, seed + rep)
        typed = ""
        peek_until = 0.0

        while typed != text:
            now = time.monotonic()
            peeking = now < peek_until
            _draw(stdscr, text, shown, typed, rep, total_reps, peeking, peeks, sess)

            stdscr.nodelay(peeking)
            key = stdscr.getch()
            stdscr.nodelay(False)

            if key == -1:
                curses.napms(40)
                continue
            if engine.is_quit(key):
                sess.finish()
                return sess.summary() if sess.total_keystrokes else None
            if key == 9:  # TAB
                peeks += 1
                peek_until = time.monotonic() + PEEK_SECONDS
                continue
            if engine.is_backspace(key):
                typed = typed[:-1]
                continue
            if not engine.is_typable(key):
                continue

            ch = chr(key)
            correct = len(typed) < len(text) and ch == text[len(typed)]
            sess.keystroke(correct)
            if len(typed) < len(text):
                typed += ch if correct else ch

            # If they went wrong, make them fix it before continuing
            if not correct:
                while typed and typed != text[:len(typed)]:
                    _draw(stdscr, text, shown, typed, rep, total_reps, False, peeks, sess)
                    k2 = stdscr.getch()
                    if engine.is_backspace(k2):
                        typed = typed[:-1]
                    elif engine.is_quit(k2):
                        sess.finish()
                        return sess.summary()

        sess.word_done()

        if rep < total_reps - 1:
            nxt = int(REVEAL_SCHEDULE[rep + 1] * 100)
            if nxt >= 100:
                blurb = "Next pass: nothing on screen. All you."
            else:
                blurb = "Next pass hides %d%% of the words." % nxt
            ui.message(
                stdscr,
                ["Pass %d done." % (rep + 1),
                 "",
                 blurb,
                 "",
                 "Say it in your head before you type it."],
                title="NICE",
            )

    sess.finish()
    profile["memorize_completions"] = profile.get("memorize_completions", 0) + 1

    ui.message(
        stdscr,
        ["You typed it with nothing on screen to copy from.",
         "",
         "\"%s\"" % (text[:60] + ("..." if len(text) > 60 else "")),
         "",
         "Peeks used: %d    Accuracy: %.1f%%" % (peeks, sess.accuracy),
         "Total memorized: %d" % profile["memorize_completions"]],
        title="MEMORIZED!",
    )

    return sess.summary()
