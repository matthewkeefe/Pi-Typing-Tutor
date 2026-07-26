"""
DAILY DASH -- sixty seconds, no bars, nothing riding on it.

The same burst round the contest cups are judged on (#28), with the
judging taken off. It exists because that round turned out to be the most
replayable thing in the game and it would be a waste to lock it behind an
entry throttle -- and because a kid who wants to practise for a cup
should be able to, without spending one of their three goes.

Unlocked once the first cup has been won, so it arrives as something the
ladder gave you rather than as one more thing on the menu on day one.
"""

from core import contests
from modes.contest import daily_dash


def available(profile=None):
    """
    Hidden until a cup has been won.

    A kid who has never entered a contest has no idea what a "dash" is,
    and the menu is already long. After the Beginner Cup it means
    something: it's that round again, whenever you like.
    """
    return contests.rank(profile or {}) >= 1


def play(stdscr, profile):
    return daily_dash(stdscr, profile)
