"""
Graduation -- the win condition (#31).

Stated plainly, this is what the whole game is for: a kid arrives hunting
and pecking at about 5 wpm and leaves typing 40+ wpm on the full
keyboard. Everything else is in service of getting them there.

Two conditions, both required:

1. **Every letter mastered.** All 26 unlocked and green, which already
   drives the star-shimmer reveal from #22.
2. **40+ wpm sustained.** Not `best_wpm` -- a peak is one lucky short run
   and is trivially gamed. The median of recent real sessions, so one bad
   afternoon cannot un-graduate a kid and one brilliant run cannot carry
   them.

The two are deliberately separate beats. Stars say "you have mastered
every key"; graduation says "...and you can do it at speed, every time".
The star-covered cat is then the one who gets a kitten, which is a better
story than collapsing both into one event -- and it means sustained speed
is doing real gating work rather than being decoration.

This is the one intentional exception to guard 4 (rewards are
informational, not performance payments). A typing tutor should arguably
have exactly one, and it is framed as a graduation rather than a prize:
the kitten is a lateral second cat, and nothing about earning it makes
the first cat lesser.
"""

from core import adaptive, cat

GRADUATE_WPM = 40.0        # the goal, stated once
GRADUATE_SESSIONS = 10     # how many recent sessions are looked at
GRADUATE_MIN_WORDS = 15    # anything shorter isn't evidence of anything


def qualifying_runs(profile):
    """Recent sessions long enough to mean something, newest last."""
    history = (profile or {}).get("history") or []
    runs = [h for h in history
            if int(h.get("words", 0) or 0) >= GRADUATE_MIN_WORDS]
    return runs[-GRADUATE_SESSIONS:]


def recent_wpm(profile):
    """
    Median wpm across those runs, or None if there aren't enough yet.

    Median rather than mean: one disastrous session shouldn't erase a
    month of consistency, and one outstanding one shouldn't stand in for
    it either.
    """
    runs = qualifying_runs(profile)
    if len(runs) < GRADUATE_SESSIONS:
        return None
    speeds = sorted(float(h.get("wpm", 0.0) or 0.0) for h in runs)
    mid = len(speeds) // 2
    if len(speeds) % 2:
        return speeds[mid]
    return (speeds[mid - 1] + speeds[mid]) / 2.0


def fast_enough(profile):
    median = recent_wpm(profile)
    return median is not None and median >= GRADUATE_WPM


def mastered_everything(profile):
    """All 26 unlocked and green -- the same test the secret uses."""
    return cat.secret_expressed(profile)


def qualifies(profile):
    """Both conditions, right now."""
    return mastered_everything(profile) and fast_enough(profile)


def graduated(profile):
    """
    Has this kid graduated, ever.

    Latched rather than recomputed, because it must never regress: a kid
    who graduates and then has a slow month is still a graduate. Guard 2
    applies to the biggest thing in the game as much as to a feather.
    """
    return bool((profile or {}).get("graduated"))


def mark_graduated(profile, today=None):
    """Latch it. Returns True the first time only."""
    if graduated(profile):
        return False
    from datetime import date
    profile["graduated"] = (today or date.today()).isoformat()
    return True


def check(profile):
    """True when a kid has just qualified and hasn't been recognised yet."""
    return qualifies(profile) and not graduated(profile)


def progress(profile):
    """
    (letters_green, 26, median_wpm_or_None, 40.0) for the stats screen.

    Only worth showing when it's plausibly close -- see #34. Before then
    it is noise, and worse, it turns the whole game into a progress bar
    pointed at one number.
    """
    keys = (profile or {}).get("keys") or {}
    green = sum(1 for ch in adaptive.alphabet(profile or {})
                if adaptive.is_green(keys.get(ch) or {}))
    return green, 26, recent_wpm(profile), GRADUATE_WPM


def worth_showing(profile):
    green, total, _median, _goal = progress(profile)
    return green >= 20 or graduated(profile)
