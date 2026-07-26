# Design & Architecture — The Cat Update

The plan for the next major version: an adaptive drill engine that actually
teaches, and a hatched-from-an-egg cat avatar that makes kids want to come
back to it. This doc records what we're building, why the evidence says to
build it that way, and how it maps onto the existing code.

---

## 1. What the research said

We ran a verified research pass (July 2026) over typing pedagogy, gamification
meta-analyses, and adaptive-tutor design. Findings that survived adversarial
fact-checking, and what each one buys us:

| Finding | Confidence | Design consequence |
|---|---|---|
| Distributed practice beats massed: short daily sessions; retention scales with *number of distinct practice days*, not reps per day (Baddeley & Longman 1978; Walsh et al. 2022) | High (3-0) | The daily-care loop is the core structure. Short sessions, warm stopping cues, streaks promoted from stat to centerpiece. |
| keybr's adaptive model (verified against its source): per-key stats, start with ~6 most frequent letters, unlock one letter when all current ones hit a confidence target, force the weakest letter into every generated word | High (3-0) | Build the same engine in stdlib Python. Replaces static `LEVELS` as the source of drill content. |
| Pronounceable pseudo-words from bigram frequencies train real letter combinations and beat random strings | High (3-0, first-party claim, mechanism code-verified) | Word generator uses an English bigram table, not `random.choice`. |
| Gamification helps learning (g ≈ 0.5–0.8) but barely moves intrinsic motivation for primary-age kids (g = 0.31); the verified gaps are *perceived competence* and *perceived autonomy* | High | Show skill growing (heatmap, tricks, trend lines). Give real choices (name, mode, daily goal). Don't just add more badges. |
| Expected performance-contingent rewards undermine kids' intrinsic motivation more than adults' (d = −0.39); praise alone doesn't reliably help | High (3-0) | Rewards are *informational milestones* ("your J went green"), never payment or punishment. **The cat never suffers, starves, or dies.** |
| Game-first format holds its own against structured curricula for ages 8–11; TypingClub's engagement comes from structure/feedback/rewards, not drill content | High / Medium | Keep the arcade format. Invest in feedback juice, not lesson authoring. |

Competitor-mechanic specifics (Nitro Type economies, ZType waves, etc.) did
NOT survive verification — treat them as inspiration, not evidence.

## 2. Design principles

Everything below follows from the table above. When in doubt, come back here.

1. **The streak is sacred.** Daily return is the most learning-effective thing
   the game can cause. Everything warm in the game points at "come back
   tomorrow"; nothing cold punishes a missed day.
2. **Additive-only progress.** Fish, toys, tricks, growth, badges — earned
   things never decay, expire, or get taken away. Daily care gauges (§3.3)
   drift down by design, but a low gauge reads as "wants attention," never
   as damage: no death, no sickness, no rarity tiers.
3. **Competence must be visible.** The kid should be able to *see* themselves
   getting better without reading numbers: keys turning green, the cat
   learning tricks, the trend line climbing.
4. **Autonomy is a feature.** Name the cat. Pick tonight's mode. Choose which
   toy to buy. Structure is fine — care comes before free play (§5) — but
   inside the structure the kid always holds real choices: task order, the
   play slot, what to spend fish on. Small real choices beat big fake ones.
5. **Short sessions, warm exits.** After the daily loop, the cat yawns and
   curls up. A sleeping cat is a stopping cue, not a locked door.
6. **Shared-device fairness.** Siblings see each other's cats. All trait
   variation is lateral (different, never better). No comparisons the game
   itself ranks.
7. **Terminal-native.** Everything must read at 80×24, in the 8 bright-capable
   colors of the bare Pi console (`TERM=linux`), in pure ASCII, at the ~30fps
   `napms(33)` cadence the modes already use.

## 3. The cat

The cat is three things at once:

- **Avatar** — it represents the kid everywhere: menu, profile picker,
  starring role in the mini-games.
- **Guide** — it does the talking. On startup it greets the kid and calls
  out what it needs today (§3.3); tips, celebrations, and onboarding come
  as cat speech bubbles instead of system messages.
- **Pet** — it needs daily care (§5), and caring for it *is* the practice.

### 3.1 Hatching

Profile creation becomes the hatch:

1. Kid enters their name (existing `ask_text` flow).
2. A wobbling ASCII egg appears. A short home-row drill starts — each correct
   keystroke cracks the shell a little more (`( )` → `(  )` with fissure chars
   accumulating). Wrong keys don't hurt the egg; it just wobbles.
3. Final keystroke: the egg bursts (particle burst, see §7) and the cat is
   revealed with its randomized look.
4. Kid names the cat — free text, their choice, never randomized.

The whole ceremony is 3–5 seconds of animation plus one short drill:
satisfying for the kid hatching, short enough that siblings waiting their
turn don't riot. First typing act = the game's thesis: typing makes things
happen.

### 3.2 Genetics

One integer seed, stored in the profile, derives everything through
`random.Random(seed)` — save data stays tiny and the cat is reconstructable
forever.

Trait axes (all lateral, all equal-value):

| Gene | Values |
|---|---|
| Fur pattern | solid, tabby (`=`/`~` striping), patches (`%`), tuxedo, socks |
| Color pair | curated combos from the 8-color space (white/yellow, cyan/blue, magenta/white, …). Must render on `TERM=linux`; richer terminals just make it prettier. |
| Eyes | `o o`, `O o` (odd-eyed), `- -` (sleepy), `^ ^` |
| Build | loaf, lanky, round; ear and tail variants |
| Personality | weights idle behavior: **lazy** (naps, stretches), **chaotic** (knocks an ASCII cup off a shelf), **hunter** (stalks the menu cursor), **cuddly** (sits close, purrs) |

**Slow-reveal genes:** cats hatch as kittens with partial trait expression.
Full markings and adult build express as adaptive-engine milestones are hit
(§4), giving the randomization a second act months later. Growth is framed
as time-plus-care, shown as "look what she's becoming" — informational,
never a performance payout.

### 3.3 Care gauges — wants, not wounds

Five gauges track today's care, visible on the status screen as bracket
bars and on the menu as small icons next to the cat:

```
 Food   [######----]     Water  [########--]
 Play   [####------]     Pets   [##########]
 Clean  [######----]
```

Each gauge fills when its care task is done (§5.1) and drifts down over
roughly a day. The critical rule: **the floor of every gauge is "wants,"
never "harmed."** An empty Food gauge means the cat sits by its bowl
looking hopeful; an empty Clean gauge means it pointedly ignores the litter
box. The cat's overall pose/mood is driven by the gauges, ranging from
*thriving* (all high) down to *sleepy and missing you* (long absence) —
that's the bottom. Come back after a week away and it's overjoyed, not dead.

Low gauges never debuff gameplay, subtract progress, or shame the kid.
On an offline Pi there is no way to warn a kid the cat needs them, so the
design never turns absence into damage. Gauges are *information the cat
acts out*, and the startup callout (§5) turns them into today's to-do list.

### 3.4 Tricks — skill made visible

When a letter reaches mastery in the adaptive engine ("goes green"), the cat
learns a trick — a short idle animation added permanently to its repertoire
(jump, spin, high-five, backflip, box-sit…). The trick popup names the
letter: `Mochi learned POUNCE! (your R key went green)`. This is the
research's "perceived competence" lever wearing a cat suit.

## 4. Adaptive drill engine

A stdlib port of keybr's verified mechanism.

### 4.1 Per-key statistics

Every drill keystroke records `(expected_char, correct, latency_ms)`.
Per key we keep an exponential moving average (recent-weighted, O(1) space):

```json
"keys": {
  "e": {"n": 512, "err": 0.04, "ms": 285, "conf": 0.82}
}
```

`conf` blends normalized speed and accuracy into 0..1. A key is **green**
(mastered) at `conf >= 0.8` (tunable).

### 4.2 Letter progression

- Start set: `e n i t r l` (English frequency order, per keybr).
- Unlock exactly one new letter when **all** unlocked letters are green.
  Unlock order continues down the frequency list: `s a u o d y c h g m p b
  k v w f z x q j`.
- The existing 7 `LEVELS` stay as the *content* backdrop for sentences and
  the Memorize mode; the adaptive alphabet becomes the source of drill and
  arcade content. `rocket_level` maps onto alphabet milestones so the
  rocket's 7 parts still pace the journey.

### 4.3 Word generation

Pronounceable pseudo-words plus real words:

- A compact English bigram frequency table (embedded dict, ~26×26 counts)
  drives a Markov-style generator constrained to the unlocked alphabet.
- The current **focus letter** (lowest `conf`) is forced into every word.
- Real words from `LEVELS` that fit the unlocked alphabet get mixed in so
  drills don't feel alien.

### 4.4 Where it shows up

- **The daily feed drill** (§5) is pure adaptive content.
- **Dino Chomp** spawns letters weighted toward weak keys instead of uniform
  `random_char`.
- **Platform Jumper** can draw platform words from the generator.
- **Stats** gains a keyboard heatmap: the QWERTY layout drawn in color —
  green mastered, yellow learning, blue locked. This is the single highest
  value competence display and it's ~40 lines of curses.

## 5. The daily loop

On startup the cat is the quest-giver: it greets the kid by name and calls
out, in a speech bubble, whatever its gauges say it needs today —
`"Mochi needs: food, play, and a clean litter box!"` Care comes first;
the arcade modes unlock for the day once the cat is looked after.

```
open game → cat greets you, calls out today's needs (from gauges, §3.3)
  └─ CARE BOARD — the kid picks the ORDER (autonomy inside structure);
      each task is a 1-3 minute typing activity; all of them together
      stay under ~10 minutes:
        Food, Water, Pets, Play, Clean — see mapping below
      done → gauges full, streak ticks, fish earned, cat delighted,
      trick popup if a key went green
  └─ FREE PLAY — all modes open, kid's pure choice. No further gates.
  └─ After a session or two, the cat yawns and curls up = stopping cue.
      Free play never locks; the sleepy cat is a signal, not a wall.
```

The care board is the pedagogical payload wearing a chore chart costume:
it guarantees the daily distributed-practice dose and lets each task train
a different micro-skill. Free play is dessert, and dessert is never locked
once care is done.

### 5.1 Care tasks → typing skills

Each care verb maps to a distinct exercise, so "chores" are secretly a
balanced curriculum:

| Task | Activity | Skill it trains |
|---|---|---|
| **Food** | The fishing drill (`modes/feed.py`): adaptive weak-key words, each word = a fish in the bowl | Weak-key targeting — the core payload |
| **Water** | Fill the bowl without spilling: a short passage typed slowly and *perfectly*; errors slosh, calm accuracy fills | Accuracy-first habit |
| **Pets** | Purr rhythm: type a soothing phrase with *even* keystroke timing; steady cadence = louder ASCII purring | Typing rhythm/evenness |
| **Play** | Kid's choice of any mini-game, short round | Autonomy slot + whatever they pick |
| **Clean** | Litter scoop: numbers/symbols drill (the unglamorous keys for the unglamorous job) | The keys nobody practices |

### 5.2 The wary cat — consequences without punishment

If the cat has been uncared-for for several days, it starts **wary**: it
sits farther away, ears half-back, and today's Pets/Play tasks begin with a
short *win-it-back* beat. Rushing or sloppy typing makes the cat swat —
a `!` particle and it steps back a pace, adding a few more keystrokes to
the exercise. Typing slow and steady draws it closer until it purrs, and
the normal task proceeds.

Hard limits that keep this on the right side of the research:

- The swat is **feedback, not failure**: it costs seconds, never lives,
  score, fish, streaks, or progress. There is nothing to lose, only a
  slightly longer warm-up.
- Winning the cat back is **guaranteed and quick** — 30–60 seconds worst
  case. A comeback day must end *warmer* than a normal day, because the
  comeback moment is exactly where a returning kid is most likely to quit
  for good.
- The cat is wary, never hostile: "not yet, slow down," not rejection.
- Nice side effect: it's honest pet education — real cats are exactly like
  this — and the win-it-back exercise is literally the rhythm/evenness
  drill in costume.

### 5.3 The shop — weekly upgrades

Every week (real-time, e.g. Mondays) the shop rotates in a couple of new
items. Fish are the currency, and fish are earned by *words typed* —
volume, not performance thresholds — so buying power comes from showing up,
and the shop never becomes a skill leaderboard in disguise.

| Item class | Examples | Effect |
|---|---|---|
| **Toys** | yarn ball, feather wand, cardboard box | Unlock mini-game variants and new idle animations; permanent |
| **Treats** | salmon bite, catnip cookie | Consumable power-ups the kid chooses to activate: a mistake shield in the no-backspace platformer, a combo saver in Dino Chomp, a score bonus round |
| **Litter tiers** | basic → clumping → self-raking deluxe | Streak insurance: covers 1–2 missed care days (Duolingo streak-freeze pattern). Bought *ahead of time* — protection, not pardon |
| **Decor** | rug, window perch, plant to knock over | Pure cosmetics for the cat's corner of the menu; the visible record of months of care |

Design guards: treats are *buffers and bonuses only* — no item ever makes
the typing itself easier or auto-completes practice. Prices stay small
(days, not weeks, of fish). New-item announcements come from the cat
("The shop has a feather wand this week!"), which doubles as a weekly
return hook that is additive, not FOMO — items rotate back in later, so
missing a week costs nothing permanently.

## 6. Modes

Existing modes keep working untouched (the cat is additive):

| Mode | Cat integration (cheap) | Later |
|---|---|---|
| Rocket Builder | Cat in a helmet rides the finished rocket | Cat plants a flag per level |
| Dino Chomp | Weak-key-weighted spawns (§4.4) | — |
| Platform Jumper | The jumper *is* the kid's cat (render from genes) | — |
| Memorize | unchanged | Cat "listens" while you recite |

New cat-native modes, in priority order:

1. **Feed** (`modes/feed.py`) — the daily adaptive drill, skinned as fishing:
   type a word, a fish arcs across the screen into the bowl. This is backlog
   item #1's user-facing form.
2. **Yarn Chase** — accuracy mode: type words perfectly to dangle and flick a
   yarn ball; the cat pounces on success. (Platformer's engine, reskinned.)
3. **Pantry Defense** — Typer Shark's approach-tension: ASCII mice sneak
   toward the food bowl, each labeled with a word; type it to shoo them.
   (Dino Chomp's engine with words instead of letters.)

## 7. Juice

The Cogmind writeups confirm pure-ASCII particle effects can carry all
gameplay feedback. One small module, used everywhere:

- `fx.spawn(kind, y, x)` + `fx.tick(dt)` + `fx.draw(win)` — fire-and-forget
  particles inside any mode's existing draw loop.
- Kinds: keystroke spark, combo shimmer, egg-crack burst, confetti (level
  clear / badge), fish splash, purr wisps (`~` drifting off a happy cat).
- Budget: pure state-update + `safe_addstr`, no timing changes — modes keep
  their `napms(33)` loop.

## 8. Multi-kid / shared device

- Each profile has its own cat; the profile picker shows a tiny cat glyph
  next to each name (cats become the de-facto profile icons).
- **Ghost racing** (later phase): store per-word cumulative timestamps for a
  completed passage (`"ghosts": {"<passage-key>": [1.2, 2.9, 4.1, …]}`).
  A sibling races the recorded ghost — their cat vs. your cat on parallel
  tracks. Asynchronous, so it works on one keyboard. Racing is opt-in and
  ghosts are chosen by the kid (fairness: you pick who to race).

## 9. Architecture

### 9.1 Module map

```
main.py               menu flow: gains cat-on-menu, hatch on profile create
core/
  engine.py           Session: gains optional per-key capture (expected char + latency)
  profiles.py         schema additions below; existing setdefault migration covers them
  lessons.py          unchanged; becomes content backdrop (real words, sentences)
  badges.py           unchanged mechanics; copy audit per §2 (informational framing)
  ui.py               unchanged
  adaptive.py         NEW — per-key stats, confidence, letter unlocks, word generator
  cat.py              NEW — genes from seed, ASCII rendering, gauges/moods, idles,
                      tricks, wary-state logic, speech bubbles
  shop.py             NEW — item catalog, weekly rotation, fish economy, inventory
  fx.py               NEW — ASCII particle system
modes/
  rocket|dino|platformer|memorize.py   touched only for §6 integrations
  care.py             NEW — care board + the Water/Pets/Clean micro-activities
  feed.py             NEW — Food task: daily adaptive drill (fishing skin)
  yarn.py, pantry.py  NEW — later phases
```

The mode contract is untouched: `play(stdscr, profile) -> summary dict`.
New modes plug into `main_menu()`'s existing list exactly like the README
describes.

### 9.2 Engine changes

`Session.keystroke(correct)` grows optional arguments:

```python
sess.keystroke(correct, ch=expected_char, latency=ms_since_prev)
```

Modes that don't pass them behave exactly as today. `summary()` gains a
`"keys"` entry when data exists; `after_session()` in `main.py` folds it
into the profile via `adaptive.merge_keys(profile, summary)`. One capture
point, every mode feeds the engine for free once it opts in.

### 9.3 Profile schema additions

All top-level keys, so `get_or_create()`'s `setdefault` forward-compat
migrates old saves automatically:

```json
{
  "cat": {
    "seed": 483921,
    "name": "Mochi",
    "hatched": "2026-07-26",
    "tricks": ["jump", "pounce"],
    "growth": 2,
    "care": {"food": "2026-07-27", "water": "2026-07-27", "pets": "2026-07-27",
             "play": "2026-07-26", "clean": "2026-07-26"},
    "wary": false
  },
  "fish": 42,
  "inventory": {"toys": ["yarn_ball"], "treats": {"salmon_bite": 2},
                "litter": "clumping", "decor": ["window_perch"]},
  "keys": {"e": {"n": 512, "err": 0.04, "ms": 285, "conf": 0.82}},
  "alphabet": "enitrl",
  "ghosts": {}
}
```

Size check: `keys` is ≤30 entries of 4 numbers; `ghosts` capped like
`history` (keep last N). The 500-entry history cap pattern already in
`record_session()` is the template.

### 9.4 Rendering constraints (restated for implementers)

- 80×24 minimum; use `safe_addstr` for every write (never raw `addstr`).
- 8 colors + bold only. The existing `C_*` pairs stay; `cat.py` gets its own
  pair slots (10+) initialized in `init_colors()`.
- ASCII only — the bare-console font on the Buildroot path can't be trusted
  beyond 7-bit.
- Kid-proof input: ESC always exits cleanly to the menu (`is_quit`), any
  garbage key is ignored, terminal resize never crashes (`require_size`
  pattern).

## 10. Roadmap

Each phase is independently shippable; kids playtest after every one.

1. **Adaptive engine** — `core/adaptive.py`, Session per-key capture, the
   stats-screen keyboard heatmap. No visible cat yet, but Dino spawns get
   weak-key weighting. *Proves the data pipeline.*
2. **The cat exists** — `core/cat.py`, hatch ceremony on profile creation,
   cat + mood on the main menu, cat glyphs in the profile picker.
   *Kids meet their cats; their reaction steers everything after.*
3. **The daily loop** — care gauges, the startup callout, the care board
   (`modes/care.py` + `modes/feed.py`) wired to streak + fish + trick
   popups; care-before-free-play gate; sleep cue after sessions. Ship with
   Food/Play first, add Water/Pets/Clean as their micro-games land.
4. **Juice pass** — `core/fx.py`; egg burst, keystroke sparks, confetti,
   purr wisps threaded through existing modes.
5. **Shop & wary state** — `core/shop.py` weekly rotation, treats/toys/
   litter/decor, fish economy; wary-cat win-it-back beat (needs the rhythm
   drill from the care board, hence after phase 3).
6. **Cat mini-games** — Yarn Chase, Pantry Defense; platformer renders the
   kid's cat as its jumper.
7. **Ghosts & growth** — ghost racing, slow-reveal genes, growth stages.

## 11. Open questions (future research candidates)

- Optimal drill length for 8–11-year-olds (adult evidence says ~1h/day is
  ceiling; kids' is likely much shorter — tune `feed.py` empirically).
- Do virtual unlockables behave like tangible rewards (undermining) or
  informational feedback for kids? We designed conservatively; watch for
  kids grinding *for fish* instead of playing.
- Verified competitor mechanics never materialized — a future deep-research
  pass on developer postmortems (Tux Typing source, Typer Shark design
  retrospectives) could still pay off.
