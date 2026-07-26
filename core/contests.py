"""
The contest ladder -- the aspirational track above daily care.

Five cups, each a triple: a speed sprint, an accuracy trial, and an
endurance passage. Clear all three and the cup is yours, along with a
ribbon for the Scrapbook.

THE FAIRNESS RULE, which is the whole reason this is designed the way it
is: **ranks measure a kid against the game's bars, never against a
sibling.** Nothing here knows another profile exists. There is no
leaderboard, no comparison, no "faster than", and the ladder is the same
for everyone -- which means a rank is a statement about you and the game,
and can't become a statement about you and your sister. The same
invariant governs ghost racing (#21).

Bars are generous at the bottom on purpose. The Beginner cup should be
winnable by a kid who has just started, because a ladder whose first rung
is out of reach is not a ladder.

Entries are throttled to a few a day (the Nintendogs pacing the research
points at). The throttle exists so the ladder stays a highlight rather
than something to grind, and the cat asks them to rest rather than the
game refusing them.
"""

from datetime import date

MAX_ENTRIES_PER_DAY = 3

# (key, name, wpm bar, accuracy bar, endurance words)
#
# The wpm bars sit under the corresponding stage of the 5->40 journey the
# engine is tuned for: a kid should reach a cup a little before they'd
# call themselves that fast, not after.
CUPS = [
    ("beginner", "Beginner Cup", 8.0, 80.0, 10),
    ("junior", "Junior Cup", 15.0, 88.0, 15),
    ("expert", "Expert Cup", 24.0, 92.0, 20),
    ("master", "Master Cup", 32.0, 95.0, 25),
    ("champion", "Champion Cup", 40.0, 97.0, 30),
]

TRIALS = ("sprint", "accuracy", "endurance")


def cup(index):
    if 0 <= index < len(CUPS):
        return CUPS[index]
    return None


def cup_by_key(key):
    for i, row in enumerate(CUPS):
        if row[0] == key:
            return i, row
    return None, None


def state(profile):
    """The stored contest state, filled in for saves that predate it."""
    st = (profile if profile is not None else {}).setdefault("contests", {})
    st.setdefault("rank", 0)          # cups won
    st.setdefault("day", "")
    st.setdefault("entries", 0)
    return st


def rank(profile):
    return int(state(profile).get("rank", 0) or 0)


def next_cup(profile):
    """The cup this kid is working on, or None once the ladder is done."""
    return cup(rank(profile))


def won_cups(profile):
    return [CUPS[i] for i in range(min(rank(profile), len(CUPS)))]


def entries_left(profile, today=None):
    """
    How many goes are left today.

    A date that isn't today's resets the counter, which also means a
    clock jumping backwards hands back entries rather than locking a kid
    out. Generous in the direction of the kid, deliberately: the throttle
    exists to keep this a highlight, not to police anybody.
    """
    st = state(profile)
    stamp = (today or date.today()).isoformat()
    if st.get("day") != stamp:
        return MAX_ENTRIES_PER_DAY
    return max(0, MAX_ENTRIES_PER_DAY - int(st.get("entries", 0) or 0))


def take_entry(profile, today=None):
    """Consume one go. Returns False when they're out for the day."""
    st = state(profile)
    stamp = (today or date.today()).isoformat()
    if st.get("day") != stamp:
        st["day"] = stamp
        st["entries"] = 0
    if int(st.get("entries", 0) or 0) >= MAX_ENTRIES_PER_DAY:
        return False
    st["entries"] = int(st.get("entries", 0) or 0) + 1
    return True


def judge(cup_row, wpm, accuracy, words_done):
    """
    Which trials were cleared. Returns {trial: bool}.

    Deliberately separate from the UI so the bars can be argued about,
    tuned and tested without a terminal anywhere near them.
    """
    _key, _name, wpm_bar, acc_bar, endurance = cup_row
    return {
        "sprint": wpm >= wpm_bar,
        "accuracy": accuracy >= acc_bar,
        "endurance": words_done >= endurance,
    }


def passed(results):
    return all(results.get(t) for t in TRIALS)


def award(profile, cup_index):
    """
    Record a cup win. Returns the ribbon id, or None if it wasn't new.

    Ranks only ever rise: winning a cup you already hold changes nothing,
    and there is no path that lowers a rank. A kid who wins the Junior
    Cup and then has a bad month is still a Junior.
    """
    if not (0 <= cup_index < len(CUPS)):
        return None
    st = state(profile)
    if cup_index < rank(profile):
        return None
    if cup_index > rank(profile):
        return None                    # cups are climbed in order
    st["rank"] = cup_index + 1
    return "%s ribbon" % CUPS[cup_index][1]


def prize_fish(cup_index):
    """Scaled by cup. Additive, and never taken back on a loss."""
    return 25 + 25 * max(0, cup_index)


def tip_for(cup_row, results):
    """
    What to say after a near miss. Names the trial, never the kid.

    Always forward-looking: the entry is spent either way and there is
    nothing else to lose, so the only useful thing to say is what to aim
    at next time.
    """
    _key, _name, wpm_bar, acc_bar, endurance = cup_row
    if not results.get("accuracy"):
        return "Slow down a little -- %.0f%% accuracy is the bar." % acc_bar
    if not results.get("sprint"):
        return "Nearly. %.0f words a minute is the bar." % wpm_bar
    if not results.get("endurance"):
        return "Keep going a bit longer -- %d words does it." % endurance
    return "That was a good run."
