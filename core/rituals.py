"""
Weekly and seasonal rituals -- the texture that gives a year a shape.

Three things live here: a weekend delivery, seasonal decoration, and the
escalation on the daily show-up gift.

THE CLOCK IS NOT TRUSTWORTHY. This runs on a Pi with no network and
possibly no RTC battery. The date can be wrong, can jump backwards on
boot, and can leap forward by years. Every function here is written for
that:

- Seasonal state is a pure function of the date. Nothing is stored, so a
  wrong clock is a cosmetic oddity for a day rather than corrupted save
  data that outlives it.
- The weekend crate is keyed to the ISO week, so a clock jumping around
  inside one week cannot farm it, and a clock jumping *backwards* cannot
  re-award a week already collected.
- Nothing is ever missable. Every season returns next year, the crate
  returns next weekend, and the gift never stops arriving. A limited-time
  offer on a device whose clock might be wrong would be unfair even if
  guard 8 allowed it, which it does not.

The escalation is the one piece with a stored counter, and it only ever
raises the size of a gift, never removes one.
"""

from datetime import date

# --- the weekend crate ----------------------------------------------

CRATE_FISH = 40         # roughly a care day, so it feels like a real find


def is_weekend(today=None):
    return (today or date.today()).weekday() >= 5


def week_key(today=None):
    """
    ISO year+week. Stable across a weekend, and the thing the crate is
    keyed to: a clock wobbling inside one week can't produce a second
    crate, and one jumping backwards can't reopen a collected one.
    """
    iso = (today or date.today()).isocalendar()
    return "%04d-w%02d" % (iso[0], iso[1])


def crate_due(profile, today=None):
    """
    True on the first weekend login of an ISO week.

    Compares *greater than* the last week collected, not merely different.
    A Pi with a dead RTC boots into the past, and "different" would let a
    backwards jump reopen a crate already taken -- collect on Saturday,
    reboot into last month, collect again, forever. The key format sorts
    correctly as a string, so this is just a comparison.
    """
    if not is_weekend(today):
        return False
    seen = (profile or {}).get("crate_week")
    if not seen:
        return True
    return week_key(today) > seen


def take_crate(profile, today=None):
    """
    Claim the weekend crate. Returns the fish, or 0 if it isn't due.

    Marks the week before paying out, so a crash between the two costs
    the crate rather than granting it forever.
    """
    if not crate_due(profile, today):
        return 0
    profile["crate_week"] = week_key(today)
    profile["fish"] = profile.get("fish", 0) + CRATE_FISH
    return CRATE_FISH


# --- seasons ---------------------------------------------------------
#
# Cosmetic only, and derived purely from the date. A wrong clock means a
# pumpkin in March, which is a funny bug rather than a broken save.
#
# (start_month, start_day, end_month, end_day, key, label, art)

SEASONS = [
    (10, 24, 11, 2, "pumpkin", "pumpkin season", "(^)"),
    (12, 10, 1, 6, "winter", "winter", "*^*"),
    (3, 18, 4, 10, "spring", "spring", ",o,"),
    (6, 20, 8, 20, "summer", "high summer", "\\o/"),
]


def _in_window(today, sm, sd, em, ed):
    """Handles windows that wrap the new year."""
    start = (sm, sd)
    end = (em, ed)
    now = (today.month, today.day)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def season(today=None):
    """(key, label, art) for the date, or None most of the year."""
    today = today or date.today()
    for sm, sd, em, ed, key, label, art in SEASONS:
        if _in_window(today, sm, sd, em, ed):
            return key, label, art
    return None


def is_hatch_birthday(profile, today=None):
    """
    The cat's hatch anniversary. Never the kid's -- we don't know that,
    and asking a child their birthday is not something this game does.
    """
    today = today or date.today()
    hatched = ((profile or {}).get("cat") or {}).get("hatched")
    if not hatched:
        return False
    try:
        d = date.fromisoformat(hatched)
    except (TypeError, ValueError):
        return False
    if d >= today:
        return False          # a clock in the past; say nothing
    return (d.month, d.day) == (today.month, today.day)


# --- show-up gift escalation ----------------------------------------
#
# Extends the daily hello from Phase 3 (#9, shipped with the Scrapbook).
# Consecutive days step the gift up a little. An absence resets the step
# WITHOUT COMMENT -- the gift itself never stops arriving, only the
# escalation goes back to the beginning.
#
# That is guard 2 exactly: absence freezes, it never reverses, and it is
# never mentioned. A kid returning after a month gets a day-one gift and
# a warm hello, not a note about where they have been.

STEP_DAYS = [1, 3, 7, 14]     # the streak lengths that step the gift up
STEP_FISH = [0, 5, 10, 20]    # a little extra alongside the gift


def gift_step(profile):
    """
    How far up the escalation this kid is, 0..len(STEP_DAYS)-1.

    Read from the day streak the game already keeps, so there is no
    second counter to drift, and an absence resets it the same way the
    streak resets: quietly.
    """
    streak = int((profile or {}).get("current_streak", 0) or 0)
    step = 0
    for i, need in enumerate(STEP_DAYS):
        if streak >= need:
            step = i
    return step


def gift_bonus(profile):
    """Fish riding along with today's gift. Never negative, never taken."""
    return STEP_FISH[min(gift_step(profile), len(STEP_FISH) - 1)]
