"""
Shared typing measurement. Every mode funnels keystrokes through a
Session so WPM/accuracy are computed the same way everywhere.

WPM uses the standard "5 characters = 1 word" convention, counted on
correct characters only, and the clock starts on the first keystroke
(not when the screen appears) so a kid staring at the screen doesn't
tank their score.

A mode that tells us which character it was expecting also gets per-key
statistics for free -- that's what feeds the adaptive engine. Modes that
don't pass `ch` behave exactly as they always have.
"""

import time

# A gap longer than this isn't typing speed, it's the kid looking away,
# picking a mode, or waiting for the next letter to drift on screen.
MAX_LATENCY_MS = 2000.0


class Session:
    def __init__(self):
        self.started = None
        self.ended = None
        self.correct_chars = 0
        self.wrong_chars = 0
        self.words_done = 0
        self.keys = {}          # {ch: {"n", "err", "ms_sum", "ms_n"}}
        self._last_key_at = None

    def start_if_needed(self):
        if self.started is None:
            self.started = time.monotonic()

    def keystroke(self, correct, ch=None):
        """
        Record one keystroke. `ch` is the character the kid was *supposed*
        to type, not what they hit -- errors belong to the target key.
        """
        self.start_if_needed()
        if correct:
            self.correct_chars += 1
        else:
            self.wrong_chars += 1

        now = time.monotonic()
        if ch is not None and ch != " ":
            entry = self.keys.get(ch)
            if entry is None:
                entry = {"n": 0, "err": 0, "ms_sum": 0.0, "ms_n": 0}
                self.keys[ch] = entry
            entry["n"] += 1
            if not correct:
                entry["err"] += 1
            elif self._last_key_at is not None:
                # Time only clean hits: a fast wrong mash shouldn't make a
                # key look easy. Accuracy is already tracked separately.
                gap = (now - self._last_key_at) * 1000.0
                if gap <= MAX_LATENCY_MS:
                    entry["ms_sum"] += gap
                    entry["ms_n"] += 1
        self._last_key_at = now

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
        out = {
            "wpm": self.wpm,
            "accuracy": self.accuracy,
            "words": self.words_done,
            "chars": self.correct_chars,
            "seconds": self.elapsed,
        }
        if self.keys:
            out["keys"] = self.keys
        return out


def is_typable(key):
    """True for printable ASCII the kid actually meant to type."""
    return 32 <= key < 127


def is_backspace(key):
    import curses
    return key in (curses.KEY_BACKSPACE, 127, 8)


def is_quit(key):
    return key == 27  # ESC
