"""
Stasis -- what happens to a cat you aren't currently looking after.

A shelved cat is **locked**. Its status is saved exactly as it was and
nothing changes: it does not get hungry, does not drift toward wary, does
not age, and does not judge anybody for being away. Time does not touch
it. In the game this is simply a magic; in here it is a timestamp shift.

This is what makes more than one cat possible without the daily loop
doubling. Only the active cat is live, so there is exactly one care board
however many cats a kid owns.

It also lands on three guards rather than straining them:

- **The cat never suffers** (guard 1). A cat in stasis cannot starve or
  be neglected. The obvious failure mode of a second pet is unreachable.
- **Earned progress never decays** (guard 2). "Saved and not changed" is
  guard 2 restated as a mechanic.
- **Reunion, never reprimand.** Switching back finds the cat exactly as
  you left it. There is nothing to come home to but the cat you had.

HOW IT WORKS
    Care gauges are derived from timestamps rather than stored, so
    freezing is: remember when the cat was shelved; on waking, shift
    every stored moment forward by however long it was away. The gauge
    code needs no changes at all -- it keeps deriving from timestamps
    that now say what they always meant.

    `hatched` is deliberately NOT shifted. That is the cat's birthday, a
    fact about history rather than a status, and the hatch anniversary
    (#30) reads it.
"""

from datetime import datetime, timedelta

# Cat fields holding a moment that stasis has to carry forward. `hatched`
# is absent on purpose -- see the note above.
FROZEN_STAMPS = ("wary_cleared", "woke")


def shelf(profile):
    """Cats currently in stasis. The live one is `profile['cat']`."""
    return (profile if profile is not None else {}).setdefault("shelf", [])


def all_cats(profile):
    """[(index, data, is_active), ...] -- active first, then the shelf."""
    out = []
    live = (profile or {}).get("cat") or {}
    if live.get("seed") is not None:
        out.append((-1, live, True))
    for i, data in enumerate(shelf(profile)):
        out.append((i, data, False))
    return out


def count(profile):
    return len(all_cats(profile))


def _parse(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def freeze(data, now=None):
    """Mark a cat as entering stasis. Idempotent."""
    if not data or data.get("stasis_at"):
        return data
    data["stasis_at"] = (now or datetime.now()).isoformat(timespec="seconds")
    return data


def thaw(data, now=None):
    """
    Bring a cat out of stasis, carrying every stored moment forward by
    exactly the time it was away.

    A cat shelved with a half-full food gauge wakes with a half-full food
    gauge, whether that was an hour ago or a year. Nothing decayed while
    it was gone, because from the cat's point of view no time passed.
    """
    if not data:
        return data
    since = _parse(data.pop("stasis_at", None))
    now = now or datetime.now()
    if since is None:
        # Never shelved, or an unreadable stamp. Waking is still safe:
        # give it a `woke` moment so a cat with no care history doesn't
        # read as abandoned. Same reasoning as the Phase 3 fix -- an
        # absence of timestamps is not evidence of neglect.
        data["woke"] = now.isoformat(timespec="seconds")
        return data

    gap = now - since
    if gap < timedelta(0):
        # A clock that went backwards. Shifting by a negative gap would
        # age the cat instead of freezing it, so do nothing but mark it
        # awake -- erring toward the cat having just been seen.
        gap = timedelta(0)

    care = data.get("care") or {}
    for task, stamp in list(care.items()):
        when = _parse(stamp)
        if when is not None:
            care[task] = (when + gap).isoformat(timespec="seconds")

    for field in FROZEN_STAMPS:
        when = _parse(data.get(field))
        if when is not None:
            data[field] = (when + gap).isoformat(timespec="seconds")

    data["woke"] = now.isoformat(timespec="seconds")
    return data


def in_stasis(data):
    return bool((data or {}).get("stasis_at"))


def switch_to(profile, index, now=None):
    """
    Make the shelved cat at `index` the live one.

    A straight swap: the current cat is frozen and takes the shelf slot,
    the chosen one thaws and becomes `profile['cat']`. There is only ever
    one copy of any cat, so nothing can drift out of step with itself.

    Returns the newly active cat's data, or None if the index is bad.
    """
    book = shelf(profile)
    if not (0 <= index < len(book)):
        return None
    now = now or datetime.now()

    live = profile.get("cat") or {}
    incoming = book[index]

    if live.get("seed") is not None:
        book[index] = freeze(live, now)
    else:
        book.pop(index)

    profile["cat"] = thaw(incoming, now)
    return profile["cat"]


def add_cat(profile, data, now=None):
    """
    Add a newly hatched cat and make it the live one.

    The cat that was live goes to the shelf rather than anywhere else --
    it is never replaced, never retired, never discarded. That is the one
    non-negotiable of the whole second-cat design.
    """
    now = now or datetime.now()
    live = profile.get("cat") or {}
    if live.get("seed") is not None:
        shelf(profile).append(freeze(live, now))
    profile["cat"] = data
    return data


def days_active(profile):
    """
    Days the LIVE cat has been the one being looked after.

    Growth has to read this rather than the profile's `days_played`, or a
    shelved cat would keep growing up while frozen. On a one-cat profile
    the two are identical, so nothing that already exists changes.
    """
    data = (profile or {}).get("cat") or {}
    if "days_active" in data:
        return int(data.get("days_active", 0) or 0)
    # Old save, or a cat from before this existed: it has been the only
    # cat all along, so every day the kid played was a day with it.
    return int((profile or {}).get("days_played", 0) or 0)


def touch_active_day(profile):
    """Count today against the live cat. Called once per new day."""
    data = (profile or {}).get("cat") or {}
    if data.get("seed") is None:
        return
    if "days_active" not in data:
        data["days_active"] = int((profile or {}).get("days_played", 0) or 0)
    data["days_active"] = int(data["days_active"]) + 1
