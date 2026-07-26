"""
Pure-ASCII particle effects.

Cogmind's writeups make the case that ASCII particles can carry all of a
game's feedback, and this is the cheap version of that: one small module
any mode can fire into from the draw loop it already has.

Design constraints that shaped the API:

- **Fire and forget.** `spawn` never blocks, never sleeps, never touches
  the clock. Hosts keep their own `napms(33)` loop and just call `tick`
  and `draw` inside it.
- **Additive.** Delete every fx call from a mode and the mode is exactly
  what it was before. Nothing here owns gameplay state.
- **Cheap.** A hard cap on live particles, `__slots__`, and no work at
  all when the field is empty -- this has to run on a Pi.
- **Curses-free until draw time.** Particles carry a colour *pair id*,
  not a resolved attribute, so spawning and ticking work without a
  terminal and can be tested like any other pure code.

Terminal cells are about twice as tall as they are wide, so horizontal
velocities are doubled -- otherwise every burst comes out as a tall thin
smear instead of a circle.
"""

import curses
import random

from core import ui

FRAME = 0.033   # the ~30fps cadence every mode already runs at

MAX_PARTICLES = 120   # Pi CPU budget; spawning past this drops the oldest
ASPECT = 2.0          # cell width:height fudge, so bursts look round


class Particle:
    __slots__ = ("ch", "y", "x", "vy", "vx", "ttl", "pair", "bold", "gravity")

    def __init__(self, ch, y, x, vy, vx, ttl, pair, bold, gravity):
        self.ch = ch
        self.y = y
        self.x = x
        self.vy = vy
        self.vx = vx
        self.ttl = ttl
        self.pair = pair
        self.bold = bold
        self.gravity = gravity


# Each preset is a recipe, not a hard script: counts and speeds are
# ranges so no two bursts look identical.
PRESETS = {
    # a keystroke landing -- tiny, fast, gone before you focus on it
    "spark": {"n": (3, 5), "chars": ".*'`", "speed": (6.0, 14.0),
              "ttl": (0.12, 0.28), "pair": ui.C_WARN, "bold": True,
              "gravity": 0.0, "spread": "all"},
    # something worth celebrating: slower, colourful, falls
    "confetti": {"n": (18, 26), "chars": "*+.ox", "speed": (5.0, 13.0),
                 "ttl": (0.7, 1.5),
                 "pairs": (ui.C_WARN, ui.C_CORRECT, ui.C_ACCENT, ui.C_TITLE),
                 "bold": True, "gravity": 16.0, "spread": "all"},
    # the egg letting go
    "burst": {"n": (16, 22), "chars": "*.,'`", "speed": (9.0, 20.0),
              "ttl": (0.35, 0.85), "pair": ui.C_WARN, "bold": True,
              "gravity": 9.0, "spread": "all"},
    # a fish hitting water
    "splash": {"n": (6, 10), "chars": "~.'", "speed": (5.0, 12.0),
               "ttl": (0.25, 0.6), "pair": ui.C_PENDING, "bold": True,
               "gravity": 20.0, "spread": "up"},
    # a happy cat, drifting upward and fading out
    "purr": {"n": (1, 2), "chars": "~", "speed": (2.0, 4.5),
             "ttl": (0.9, 1.8), "pair": ui.C_ACCENT, "bold": False,
             "gravity": -2.5, "spread": "up"},
    # the wary cat's warning swat
    "bang": {"n": (4, 7), "chars": "!", "speed": (6.0, 14.0),
             "ttl": (0.2, 0.45), "pair": ui.C_WRONG, "bold": True,
             "gravity": 0.0, "spread": "all"},
    # a jump sticking its landing
    "puff": {"n": (4, 7), "chars": ".oO", "speed": (3.0, 8.0),
             "ttl": (0.2, 0.5), "pair": ui.C_PENDING, "bold": False,
             "gravity": -2.0, "spread": "side"},
}


class Field:
    """A bag of live particles. One per mode, or use the module default."""

    def __init__(self, cap=MAX_PARTICLES, rng=None):
        self.cap = cap
        self.rng = rng or random
        self.particles = []

    def __len__(self):
        return len(self.particles)

    def clear(self):
        self.particles = []

    def spawn(self, kind, y, x, n=None, pair=None, chars=None, scale=1.0):
        """
        Throw a handful of particles from (y, x).

        Unknown kinds are ignored rather than raising: a typo in a mode's
        draw loop should cost a missing sparkle, not the kid's session.
        """
        preset = PRESETS.get(kind)
        if preset is None:
            return

        rng = self.rng
        count = n if n is not None else rng.randint(*preset["n"])
        glyphs = chars or preset["chars"]
        lo, hi = preset["speed"]
        tlo, thi = preset["ttl"]
        spread = preset["spread"]
        pairs = preset.get("pairs")

        for _ in range(count):
            if spread == "up":
                angle = rng.uniform(3.4, 6.0)          # upward fan
            elif spread == "side":
                angle = rng.choice((0.0, 3.14159)) + rng.uniform(-0.5, 0.5)
            else:
                angle = rng.uniform(0.0, 6.28318)
            speed = rng.uniform(lo, hi) * scale
            # sin/cos without importing math: close enough for confetti,
            # and this module is meant to be the cheap one.
            vy = speed * _sin(angle)
            vx = speed * _cos(angle) * ASPECT
            self.particles.append(Particle(
                ch=rng.choice(glyphs),
                y=float(y), x=float(x),
                vy=vy, vx=vx,
                ttl=rng.uniform(tlo, thi),
                pair=pair if pair is not None else (
                    rng.choice(pairs) if pairs else preset["pair"]),
                bold=preset["bold"],
                gravity=preset["gravity"] * scale,
            ))

        # Past the cap the oldest go first -- the newest effect is the one
        # the kid is actually looking at.
        if len(self.particles) > self.cap:
            del self.particles[:len(self.particles) - self.cap]

    def tick(self, dt):
        if not self.particles:
            return
        alive = []
        for p in self.particles:
            p.ttl -= dt
            if p.ttl <= 0.0:
                continue
            p.vy += p.gravity * dt
            p.y += p.vy * dt
            p.x += p.vx * dt
            alive.append(p)
        self.particles = alive

    def draw(self, win):
        """
        Paint the field. Call this AFTER the scene so particles overlay
        it, and before `refresh`.
        """
        if not self.particles:
            return
        # Resolve each colour once per frame, not once per particle, and
        # fall back to plain text if the terminal has no colour at all --
        # a missing palette should cost the colour, not the effect.
        attrs = {}
        for p in self.particles:
            key = (p.pair, p.bold)
            attr = attrs.get(key)
            if attr is None:
                attr = attrs[key] = _attr(*key)
            ui.safe_addstr(win, int(p.y), int(p.x), p.ch, attr)


def _attr(pair, bold):
    try:
        return ui.cp(pair, bold)
    except curses.error:
        return 0


def _sin(a):
    """Bhaskara-style sine approximation -- no math import, plenty accurate."""
    a = a % 6.283185307
    if a > 3.141592653:
        return -_sin(a - 3.141592653)
    return 16.0 * a * (3.141592653 - a) / (49.348022 - 4.0 * a * (3.141592653 - a))


def _cos(a):
    return _sin(a + 1.570796327)


def sparkle_over(win, kind, paint, seconds=1.2, spawn_seconds=0.6,
                 origin=None, field=None, n=3):
    """
    Run a short particle flourish on top of a static screen.

    `paint(win)` redraws the underlying scene each frame -- pass
    `ui.message(..., wait=False)` in a lambda and the celebration draws
    itself. Any keypress skips straight to the end, because a kid who has
    seen the confetti twice should never have to sit through it again.
    """
    field = field or _default
    field.clear()
    win.nodelay(True)
    elapsed = 0.0
    try:
        while elapsed < seconds:
            if elapsed < spawn_seconds:
                # A few per frame from a fresh spot, rather than a wall of
                # them at once -- it should read as confetti falling, not
                # as a burst that buries the message underneath.
                h, w = win.getmaxyx()
                y, x = origin or (1, random.randint(4, max(5, w - 5)))
                field.spawn(kind, y, x, n=n)
            paint(win)
            field.tick(FRAME)
            field.draw(win)
            win.refresh()
            if win.getch() != -1:
                break
            curses.napms(int(FRAME * 1000))
            elapsed += FRAME
    finally:
        win.nodelay(False)
        field.clear()


# --- module-level default field --------------------------------------
#
# Modes never run at the same time, so one shared field keeps the call
# sites down to `fx.spawn(...)`. Call `fx.clear()` when a mode starts so
# nothing drifts in from the last one.

_default = Field()


def spawn(kind, y, x, **kw):
    _default.spawn(kind, y, x, **kw)


def tick(dt):
    _default.tick(dt)


def draw(win):
    _default.draw(win)


def clear():
    _default.clear()


def count():
    return len(_default)
