"""
Shared typing measurement. Every mode funnels keystrokes through a
Session so WPM/accuracy are computed the same way everywhere.

WPM uses the standard "5 characters = 1 word" convention, counted on
correct characters only, and the clock starts on the first keystroke
(not when the screen appears) so a kid staring at the screen doesn't
tank their score.
"""

import time


class Session:
    def __init__(self):
        self.started = None
        self.ended = None
        self.correct_chars = 0
        self.wrong_chars = 0
        self.words_done = 0

    def start_if_needed(self):
        if self.started is None:
            self.started = time.monotonic()

    def keystroke(self, correct):
        self.start_if_needed()
        if correct:
            self.correct_chars += 1
        else:
            self.wrong_chars += 1

    def word_done(self):
        self.words_done += 1

    def finish(self):
        if self.ended is None:
            self.ended = time.monotonic()

    @property
    def elapsed(self):
        if self.started is None:
            return 0.0
        end = self.ended if self.ended is not None else time.monotonic()
        return max(0.0, end - self.started)

    @property
    def total_keystrokes(self):
        return self.correct_chars + self.wrong_chars

    @property
    def wpm(self):
        # The clock starts on the first keystroke, so for the first
        # instant elapsed is ~0 and the raw formula explodes into the
        # tens of thousands. Don't report anything until there's a
        # real sample behind it.
        if self.elapsed < 1.0 or self.correct_chars < 5:
            return 0.0
        mins = self.elapsed / 60.0
        return min(300.0, (self.correct_chars / 5.0) / mins)

    @property
    def accuracy(self):
        if self.total_keystrokes == 0:
            return 100.0
        return 100.0 * self.correct_chars / self.total_keystrokes

    def summary(self):
        return {
            "wpm": self.wpm,
            "accuracy": self.accuracy,
            "words": self.words_done,
            "chars": self.correct_chars,
            "seconds": self.elapsed,
        }


def is_typable(key):
    """True for printable ASCII the kid actually meant to type."""
    return 32 <= key < 127


def is_backspace(key):
    import curses
    return key in (curses.KEY_BACKSPACE, 127, 8)


def is_quit(key):
    return key == 27  # ESC
