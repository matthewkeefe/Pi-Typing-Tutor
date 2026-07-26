"""
Progressive typing lesson content, roughly modeled on typing.com's
letter-introduction order: home row first, then reaches up/down,
then full words, then sentences.

Each LEVEL is used by every game mode as a source of "what to type."
Game modes pick words/phrases appropriate to their format from here.
"""

import random

LEVELS = [
    {
        "id": 1,
        "name": "Home Row",
        "chars": "asdfjkl;",
        "words": ["ask", "dad", "fall", "jazz", "lads", "flask", "salad", "ads", "jak", "flag"],
    },
    {
        "id": 2,
        "name": "Home Row +E/I",
        "chars": "asdfjkl;ei",
        "words": ["idea", "safe", "field", "leads", "seal", "life", "aisle", "deal", "fake", "lied"],
    },
    {
        "id": 3,
        "name": "Top Row",
        "chars": "qwertyuiop",
        "words": ["type", "quote", "power", "quiet", "write", "quiet", "you", "top", "wire", "root"],
    },
    {
        "id": 4,
        "name": "Bottom Row",
        "chars": "zxcvbnm",
        "words": ["zebra", "mix", "vain", "cabin", "brave", "camo", "van", "bomb", "cave", "next"],
    },
    {
        "id": 5,
        "name": "Numbers",
        "chars": "1234567890",
        "words": ["100", "247", "911", "2024", "1999", "42", "007", "365", "88", "12345"],
    },
    {
        "id": 6,
        "name": "Full Words",
        "chars": None,
        "words": [
            "happy", "planet", "rocket", "monster", "castle", "forest", "dragon", "wizard",
            "puzzle", "garden", "silver", "bright", "winter", "summer", "island", "jungle",
            "shadow", "wonder", "sunset", "mighty",
        ],
    },
    {
        "id": 7,
        "name": "Sentences",
        "chars": None,
        "words": [
            "the quick fox runs fast",
            "she sells sea shells",
            "we can build a rocket",
            "the dragon flew away",
            "practice makes perfect",
            "keep your eyes on the screen",
            "type with all ten fingers",
            "the dino loves to chomp letters",
        ],
    },
]


def get_level(level_id):
    for lvl in LEVELS:
        if lvl["id"] == level_id:
            return lvl
    return LEVELS[-1]


def max_level():
    return len(LEVELS)


def random_word(level_id):
    lvl = get_level(level_id)
    return random.choice(lvl["words"])


def random_char(level_id):
    """Single-character target, used by the Dino mode. Falls back to
    a random letter from a random word if the level has no raw chars
    (e.g. full-word / sentence levels)."""
    lvl = get_level(level_id)
    if lvl["chars"]:
        return random.choice(lvl["chars"])
    word = random.choice(lvl["words"])
    return random.choice([c for c in word if c != " "])


def words_for_level(level_id, count=8):
    lvl = get_level(level_id)
    pool = lvl["words"][:]
    random.shuffle(pool)
    while len(pool) < count:
        pool.append(random.choice(lvl["words"]))
    return pool[:count]
