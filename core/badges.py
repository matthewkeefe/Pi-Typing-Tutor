"""
Badges. Each badge is a dict with an id, display name, icon, blurb,
and a `check(profile)` predicate. Checked after every session; newly
earned ones get shown to the kid immediately.
"""

BADGES = [
    # --- Daily habit ---
    {"id": "first_day", "icon": "[*]", "name": "First Flight",
     "desc": "Played for the first time",
     "check": lambda p: p["days_played"] >= 1},
    {"id": "streak_3", "icon": "[3]", "name": "Three in a Row",
     "desc": "Practiced 3 days in a row",
     "check": lambda p: p["current_streak"] >= 3},
    {"id": "streak_7", "icon": "[7]", "name": "Week Warrior",
     "desc": "Practiced 7 days in a row",
     "check": lambda p: p["current_streak"] >= 7},
    {"id": "streak_30", "icon": "[30]", "name": "Unstoppable",
     "desc": "Practiced 30 days in a row",
     "check": lambda p: p["current_streak"] >= 30},
    {"id": "days_50", "icon": "[50]", "name": "Half Century",
     "desc": "Played on 50 different days",
     "check": lambda p: p["days_played"] >= 50},

    # --- Speed ---
    {"id": "wpm_15", "icon": "(>)", "name": "Getting Going",
     "desc": "Hit 15 WPM",
     "check": lambda p: p["best_wpm"] >= 15},
    {"id": "wpm_25", "icon": "(>>)", "name": "Quick Fingers",
     "desc": "Hit 25 WPM",
     "check": lambda p: p["best_wpm"] >= 25},
    {"id": "wpm_40", "icon": "(>>>)", "name": "Speed Demon",
     "desc": "Hit 40 WPM",
     "check": lambda p: p["best_wpm"] >= 40},
    {"id": "wpm_60", "icon": "(!!!)", "name": "Lightning Hands",
     "desc": "Hit 60 WPM",
     "check": lambda p: p["best_wpm"] >= 60},

    # --- Accuracy ---
    {"id": "acc_90", "icon": "(o)", "name": "Sharp Shooter",
     "desc": "Finished a run at 90% accuracy",
     "check": lambda p: p["best_accuracy"] >= 90},
    {"id": "acc_100", "icon": "(*)", "name": "Flawless",
     "desc": "Finished a run at 100% accuracy",
     "check": lambda p: p["best_accuracy"] >= 100},

    # --- Rocket mode ---
    {"id": "rocket_3", "icon": "/^\\", "name": "Ship Builder",
     "desc": "Built 3 rocket parts",
     "check": lambda p: p["rocket_parts"] >= 3},
    {"id": "rocket_full", "icon": "/^^\\", "name": "To The Stars",
     "desc": "Completed the whole rocket",
     "check": lambda p: p["rocket_parts"] >= 7},

    # --- Dino mode ---
    {"id": "dino_50", "icon": "<C~", "name": "Snack Time",
     "desc": "Scored 50 in Dino Chomp",
     "check": lambda p: p["dino_high_score"] >= 50},
    {"id": "dino_150", "icon": "<CC~", "name": "Big Appetite",
     "desc": "Scored 150 in Dino Chomp",
     "check": lambda p: p["dino_high_score"] >= 150},
    {"id": "dino_300", "icon": "<CCC~", "name": "Apex Predator",
     "desc": "Scored 300 in Dino Chomp",
     "check": lambda p: p["dino_high_score"] >= 300},

    # --- Platformer mode ---
    {"id": "plat_10", "icon": "_o_", "name": "Sure Footed",
     "desc": "Cleared 10 platforms in a row",
     "check": lambda p: p["platformer_best_streak"] >= 10},
    {"id": "plat_perfect", "icon": "_O_", "name": "No Slip Ups",
     "desc": "Finished a platformer run with no falls",
     "check": lambda p: p["platformer_perfect_runs"] >= 1},

    # --- Memorize mode ---
    {"id": "mem_1", "icon": "{i}", "name": "Memory Spark",
     "desc": "Memorized your first phrase",
     "check": lambda p: p["memorize_completions"] >= 1},
    {"id": "mem_10", "icon": "{I}", "name": "Steel Trap",
     "desc": "Memorized 10 phrases",
     "check": lambda p: p["memorize_completions"] >= 10},

    # --- Volume ---
    {"id": "words_500", "icon": "500", "name": "Wordsmith",
     "desc": "Typed 500 words total",
     "check": lambda p: p["total_words"] >= 500},
    {"id": "words_5000", "icon": "5K", "name": "Novelist",
     "desc": "Typed 5,000 words total",
     "check": lambda p: p["total_words"] >= 5000},
]


def _graduated(profile):
    from core import graduation
    return graduation.graduated(profile)


BADGES.append({
    "id": "graduate",
    "name": "Touch typist",
    "desc": "every letter mastered, and 40 wpm every time you sit down",
    "icon": "[*]",
    "check": _graduated,
})


def check_new(profile):
    """Award any newly-earned badges. Returns the list of new ones."""
    earned = set(profile.get("badges", []))
    fresh = []
    for b in BADGES:
        if b["id"] in earned:
            continue
        try:
            if b["check"](profile):
                profile.setdefault("badges", []).append(b["id"])
                fresh.append(b)
        except KeyError:
            continue
    return fresh


def by_id(badge_id):
    for b in BADGES:
        if b["id"] == badge_id:
            return b
    return None
