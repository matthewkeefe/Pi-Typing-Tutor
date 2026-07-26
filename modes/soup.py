"""
ALPHABET SOUP -- the only mode that trains word *construction*.

Letters float in the cat's bowl; make as many words as you can before the
soup cools. Every other mode in the game shows the kid what to type. This
one doesn't: they have to find the words themselves, which is spelling and
vocabulary rather than transcription.

Three things about it are deliberate and easy to break by accident:

1. **Nothing is penalised.** A word that isn't in the list gets a slurp and
   nothing else -- no lost time, no lost score, no lost fish. Guessing is
   how you find words, so guessing has to be free.

2. **Per-key capture is off.** The kid chooses every word here, so they'd
   naturally build from letters they already find easy, and since a new
   letter only unlocks when *all* the current ones are green, that could
   drive unlocks off words that never practised anything hard. Drill data
   comes from modes where the engine picks the word. See issue #25.

3. **The soup cooling is not a fail state.** The round ends and scores
   whatever was found. There is no way to lose here, only to stop.

The mode hides itself until the kid's alphabet is big enough to build a
bowl worth solving -- with the starting six letters there are exactly two
viable bowls in the whole word list.
"""

import curses
import random
import time

from core import adaptive, cat, engine, fx, ui, wordlist
from core.ui import (cp, safe_addstr, center, C_TITLE, C_WARN, C_CORRECT,
                     C_PENDING, C_ACCENT, C_WRONG)

ROUND_SECONDS = 90.0
GATE_LETTERS = 12        # below this the bowl pool is too thin to be a game
MIN_WORD = 3

# Rejections are frequent and completely fine, so they get variety rather
# than one repeated buzzer. None of these tell the kid they were wrong.
SLURPS = [
    "*slurp* -- not one I know!",
    "*sip* -- try another.",
    "The cat blinks. Not in the pot.",
    "*slurp* -- keep going.",
    "Hmm, that one's not in the soup.",
]


def available(profile):
    """
    Hidden until the alphabet can actually fill a bowl.

    Cheap on purpose: this runs every time the menu is drawn, and counting
    genuinely viable bowls takes most of a second on a full alphabet.
    """
    return len(adaptive.alphabet(profile)) >= GATE_LETTERS


def score_for(word):
    """Longer words are worth disproportionately more -- that's the hook."""
    return len(word) * len(word)


# Column within a bowl row where the letters start. The frame is drawn in
# one colour and the letters in another, so they must not overlap.
LETTER_X = 2


def tile_text(tiles):
    return "  ".join(tiles)


def _bowl_rows(tiles):
    """
    The bowl frame, with a blank channel where the letters go.

    The letters are painted separately and brighter, so this deliberately
    leaves their columns empty -- drawing them in both places is how you
    get a doubled-up smear when the frame and the overlay disagree by a
    column. All three rows are the same width so the bowl can't skew.
    """
    width = len(tile_text(tiles)) + 2
    return [
        "." + "-" * width + ".",
        "\\" + " " * width + "/",
        " \\" + "_" * (width - 2) + "/ ",
    ]


def _steam(remaining, total):
    """A gauge, not a countdown clock -- this is a cooling soup, not a bomb."""
    frac = max(0.0, min(1.0, remaining / total))
    width = 12
    filled = int(round(width * frac))
    if frac > 0.6:
        label, attr = "piping hot", C_CORRECT
    elif frac > 0.3:
        label, attr = "still warm", C_WARN
    elif frac > 0.0:
        label, attr = "going cold", C_WRONG
    else:
        label, attr = "cold", C_PENDING
    return "[" + "#" * filled + "." * (width - filled) + "] " + label, attr


def _draw(stdscr, kitty, pose, tiles, typed, found, score, remaining, msg,
          msg_ok):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    center(stdscr, 0, "A L P H A B E T   S O U P", cp(C_TITLE, True))
    safe_addstr(stdscr, 1, 2, "Found %d" % len(found), cp(C_ACCENT, True))
    safe_addstr(stdscr, 1, 14, "Score %d" % score, cp(C_WARN, True))
    gauge, gattr = _steam(remaining, ROUND_SECONDS)
    safe_addstr(stdscr, 1, max(28, w - len(gauge) - 3), gauge, cp(gattr, True))

    rows = _bowl_rows(tiles)
    bowl_w = max(len(r) for r in rows)
    bowl_x = max(2, (w - bowl_w) // 2)
    top = 3

    # Steam wisps while it's still hot, thinning as it cools.
    if remaining > ROUND_SECONDS * 0.3:
        safe_addstr(stdscr, top - 1, bowl_x + bowl_w // 2 - 2, "~  ~  ~",
                    cp(C_PENDING))

    for i, row in enumerate(rows):
        safe_addstr(stdscr, top + i, bowl_x, row, cp(C_ACCENT, True))
    # The letters themselves, bright, in the channel the frame left blank
    safe_addstr(stdscr, top + 1, bowl_x + LETTER_X, tile_text(tiles),
                cp(C_TITLE, True))

    if kitty is not None:
        cx = max(0, bowl_x - kitty.width(pose) - 3)
        kitty.draw(stdscr, top, cx, pose)

    prompt_row = top + 5
    center(stdscr, prompt_row, "Make words from those letters -- ENTER to try one",
           cp(C_PENDING))

    box = "> " + typed
    bx = max(2, (w - 24) // 2)
    safe_addstr(stdscr, prompt_row + 2, bx, box + "_", cp(C_CORRECT, True))

    if msg:
        center(stdscr, prompt_row + 4, msg,
               cp(C_CORRECT if msg_ok else C_WRONG, True))

    # Everything found so far, newest first, wrapped into the space left.
    if found:
        listing = sorted(found, key=lambda x: (-len(x), x))
        line, lines = "", []
        for word in listing:
            piece = word + "  "
            if len(line) + len(piece) > w - 8:
                lines.append(line)
                line = ""
            line += piece
        if line:
            lines.append(line)
        start = prompt_row + 6
        room = max(0, h - 2 - start)
        for i, text in enumerate(lines[:room]):
            center(stdscr, start + i, text.rstrip(), cp(C_CORRECT))

    center(stdscr, h - 1,
           "ESC to stop -- every word you found is yours", cp(C_PENDING))
    fx.tick(fx.FRAME)
    fx.draw(stdscr)
    stdscr.refresh()


def _is_enter(key):
    return key in (10, 13, curses.KEY_ENTER)


def play(stdscr, profile):
    kitty = cat.Cat.from_profile(profile)
    alphabet = adaptive.alphabet(profile)
    rng = random.Random()

    made = wordlist.make_bowl(alphabet, rng)
    if not made:
        ui.message(stdscr,
                   ["The soup pot is empty!",
                    "",
                    "Learn a few more letters and come back."],
                   title="NOT YET")
        return None
    tiles, solvable = made
    solvable = set(solvable)

    sess = engine.Session()
    found = []
    score = 0
    typed = ""
    msg, msg_ok = "", True
    pose = "sit"
    pose_until = 0.0

    curses.curs_set(0)
    stdscr.nodelay(True)
    fx.clear()

    started = time.monotonic()
    running = True

    while running:
        now = time.monotonic()
        remaining = ROUND_SECONDS - (now - started)
        if remaining <= 0:
            remaining = 0.0
            running = False

        if pose_until and now > pose_until:
            pose, pose_until = "sit", 0.0

        _draw(stdscr, kitty, pose, tiles, typed, found, score, remaining,
              msg, msg_ok)

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
            if _is_enter(key):
                word = typed.strip().lower()
                typed = ""
                if not word:
                    continue

                # The clock is already running; what matters at submit time
                # is whether this counted. Characters are accounted here,
                # never per keypress, so accuracy means "how much of what I
                # typed was a real word I could actually build" instead of
                # a free 100% that would set a bogus personal best.
                if word in found:
                    msg, msg_ok = "You already found '%s'!" % word, True
                    continue
                if len(word) < MIN_WORD:
                    msg, msg_ok = "Words need %d letters or more." % MIN_WORD, False
                    for _ in word:
                        sess.keystroke(False)
                    continue
                if word not in solvable:
                    # Either not a word, or not buildable from these tiles.
                    # The kid doesn't need that distinction mid-round.
                    msg = rng.choice(SLURPS)
                    msg_ok = False
                    for _ in word:
                        sess.keystroke(False)
                    pose, pose_until = "wary", now + 0.6
                    continue

                found.append(word)
                gained = score_for(word)
                score += gained
                for _ in word:
                    sess.keystroke(True)
                sess.word_done()
                msg = "'%s' -- %d points!" % (word, gained)
                msg_ok = True
                pose, pose_until = "overjoyed", now + 0.8
                h, w = stdscr.getmaxyx()
                fx.spawn("splash" if len(word) < 5 else "confetti", 5, w // 2)
                continue

            if engine.is_typable(key):
                ch = chr(key)
                if ch.isalpha() and len(typed) < 12:
                    sess.start_if_needed()   # clock runs from the first key
                    typed += ch.lower()

        curses.napms(33)

    sess.finish()
    stdscr.nodelay(False)

    profile["soup_words_found"] = profile.get("soup_words_found", 0) + len(found)
    if score > profile.get("soup_best_score", 0):
        profile["soup_best_score"] = score
    if len(found) > profile.get("soup_most_words", 0):
        profile["soup_most_words"] = len(found)

    name = kitty.name if kitty else "Your cat"
    missed = len(solvable) - len(found)
    if found:
        title = "SOUP'S UP!"
        lines = ["You found %d word%s for %d points."
                 % (len(found), "" if len(found) == 1 else "s", score)]
        if missed > 0:
            lines.append("There were %d more hiding in there." % missed)
    else:
        title = "MAYBE LATER"
        lines = ["No words this time -- that's alright.",
                 "", "%s drank the soup anyway." % name]

    lines += ["", "Best word: %s" % (max(found, key=len) if found else "-")]

    ui.message(stdscr, lines, title=title,
               art=kitty.art("overjoyed" if found else "sit") if kitty else None)
    return sess.summary()
