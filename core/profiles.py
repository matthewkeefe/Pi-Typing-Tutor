"""
Per-kid save data. Stored as one JSON file so it's trivially
backup-able off the Pi and human-readable if you ever need to
hand-fix something.
"""

import json
import os
import tempfile
from datetime import date, timedelta

from core import adaptive, shop

DATA_DIR = os.environ.get(
    "TYPING_TUTOR_DATA",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
SAVE_PATH = os.path.join(DATA_DIR, "profiles.json")


def _blank_profile(name):
    return {
        "name": name,
        "created": date.today().isoformat(),
        "last_played": None,
        "current_streak": 0,
        "longest_streak": 0,
        "days_played": 0,
        "total_words": 0,
        "total_chars": 0,
        "total_seconds": 0,
        "best_wpm": 0.0,
        "best_accuracy": 0.0,
        "rocket_level": 1,
        "rocket_parts": 0,
        "dino_high_score": 0,
        "platformer_best_streak": 0,
        "platformer_perfect_runs": 0,
        "yarn_best_streak": 0,
        "yarn_perfect_rounds": 0,
        "pantry_high_score": 0,
        "mystery_opened": 0,
        "quiz_right": 0,
        "soup_words_found": 0,
        "soup_best_score": 0,
        "soup_most_words": 0,
        "memorize_completions": 0,
        "badges": [],
        "history": [],  # [{date, mode, wpm, accuracy, words, seconds}]
        # Adaptive engine. Both are top-level so get_or_create's setdefault
        # pass migrates saves written before it existed.
        "keys": {},  # {ch: {"n", "err", "ms", "conf"}}
        "alphabet": adaptive.START_ALPHABET,
        # Empty until the kid hatches one; saves from before the cat
        # existed get offered the hatch on their next login.
        "cat": {},
        # Earned by volume typed, never by hitting a score. Spendable in
        # the shop; additive-only, never taken away.
        "fish": 0,
        "inventory": {"toys": [], "treats": {}, "litter": "basic", "decor": []},
        # Treat effects armed but not yet used. Survives a restart, so
        # quitting never wastes one.
        "active_effects": {},
    }


def _atomic_write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_all():
    if not os.path.exists(SAVE_PATH):
        return {}
    try:
        with open(SAVE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupt save (yanked SD card mid-write) -- keep a copy, start fresh
        try:
            os.replace(SAVE_PATH, SAVE_PATH + ".corrupt")
        except OSError:
            pass
        return {}


def save_all(profiles):
    _atomic_write(SAVE_PATH, profiles)


def get_or_create(profiles, name):
    if name not in profiles:
        profiles[name] = _blank_profile(name)
    else:
        # Forward-compat: fill in any keys added by a later version
        for k, v in _blank_profile(name).items():
            profiles[name].setdefault(k, v)
    return profiles[name]


def streak_was_rescued(profile, today=None):
    """True if the litter tier covered a missed day at today's login."""
    return profile.get("streak_rescued") == (today or date.today()).isoformat()


def touch_day(profile):
    """
    Call once per session start. Updates daily streak.
    Returns True if this is the first play of a new day.
    """
    today = date.today()
    last = profile.get("last_played")
    if last == today.isoformat():
        return False

    if last:
        try:
            last_d = date.fromisoformat(last)
        except ValueError:
            last_d = None
        gap = (today - last_d).days if last_d else None
        # Streak insurance: the litter tier was bought ahead of time, so a
        # covered gap keeps the streak. Protection, not pardon -- and it
        # only ever preserves, it can never subtract.
        covered = gap is not None and 2 <= gap <= 1 + shop.litter_coverage(profile)
        if gap == 1 or covered:
            profile["current_streak"] += 1
            if covered:
                profile["streak_rescued"] = today.isoformat()
        else:
            profile["current_streak"] = 1
    else:
        profile["current_streak"] = 1

    profile["last_played"] = today.isoformat()
    profile["days_played"] += 1
    profile["longest_streak"] = max(
        profile["longest_streak"], profile["current_streak"]
    )
    return True


def record_session(profile, mode, wpm, accuracy, words, chars, seconds):
    profile["total_words"] += words
    profile["total_chars"] += chars
    profile["total_seconds"] += int(seconds)
    if wpm > profile["best_wpm"]:
        profile["best_wpm"] = round(wpm, 1)
    if accuracy > profile["best_accuracy"]:
        profile["best_accuracy"] = round(accuracy, 1)

    profile["history"].append(
        {
            "date": date.today().isoformat(),
            "mode": mode,
            "wpm": round(wpm, 1),
            "accuracy": round(accuracy, 1),
            "words": words,
            "seconds": int(seconds),
        }
    )
    # Keep the file from growing forever on a small SD card
    if len(profile["history"]) > 500:
        profile["history"] = profile["history"][-500:]
