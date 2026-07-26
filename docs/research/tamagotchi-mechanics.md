# Tamagotchi Mechanics Research

*Research pass 2 (July 2026), agent 1 of 4 (Claude Opus 4.8, web research; single-pass,
not adversarially verified). Feeds DESIGN.md. See also: tamagotchi-psychology.md,
typing-minigame-catalog.md, pet-game-care-loops.md.*

Sourcing note: the Tamagotchi Fandom wiki blocked automated fetching, so figures come
primarily from Thaao's care guides, TamaVault, the archived 1996 P1 manual, and
cross-referenced search snippets.

## 1. The original 1996–97 Tamagotchi: the care loop

Three buttons — A (select), B (confirm), C (cancel) — and a row of icon menus.
([Thaao P1](https://thaao.net/tama/p1/), [archived 1996 manual](https://archive.org/stream/bandai-tamagotchi-p1-1996/bandai-tamagotchi-p1-1996_djvu.txt))

**Meters** (status screen shows age, weight, discipline, hunger, happiness):
- **Hunger:** 0–4 hearts. At 0, if left, leads to a care mistake and eventually death.
- **Happiness:** 0–4 hearts.
- **Discipline:** 0–100% in 25% steps — a *training* stat, the key lever for evolution.

**Care verbs:**
- **Feed → Meal:** +1 hunger heart, +1 weight. Refused when full.
- **Feed → Snack:** +1 happiness heart, +2 weight. *Never refused* — endless overfeeding
  possible (the 2018 rerelease added a lifespan penalty for it).
- **Play (mini-game):** win = +1 happiness heart and −1 weight — the weight-neutral way
  to raise happiness vs. snacks.
- **Clean:** poop drops with **no beep** — you must notice it. Up to ~4 piles; left too
  long causes sickness.
- **Discipline (scold):** used only during a "misbehavior" call (beeping despite full
  meters). +25% per correct scold. Scolding at the wrong time is a mistake.
- **Medicine:** skull icon when sick; often needs repeated doses.
- **Light:** lights out at bedtime is a required daily action.

**Timing / attention demands:**
- Attention calls stay lit **15 minutes**; unresolved past that = a **care mistake**.
- Heart decay (old adult): ~1 hunger heart per ~6 min, 1 happy heart per ~7 min —
  faster when young. Implies a check-in every ~15–60 minutes while awake.
- Sleep ~8–10 PM to 9–11 AM depending on form; waking advances age by 1 year
  (1 real day = 1 year).

**Death triggers:** cumulative neglect (ignored calls, hunger at 0, untreated
poop-sickness) and old age. Critically, **sickness does not beep** on the original —
a pet can die while the player is unaware. Past age 10 it sickens spontaneously at 12,
then every 3 days. ([Fandom Death/Sickness via search](https://tamagotchi.fandom.com/wiki/Death),
[TamaVault Gen1](https://tamavault.com/devices/original-gen1/))

## 2. Lifecycle / evolution and the care-mistakes system

| Stage | Duration |
|---|---|
| Egg | ~5 minutes |
| Baby | ~1 hour |
| Child | ages 1–3 (~3 days) |
| Teen | ages 3–6 (~3 days) |
| Adult | age 6+ |
| Secret adult | ~age 10–12, special conditions |

- A **care mistake** = a heart at 0 not refilled within 15 minutes. Mistakes accumulate
  across child+teen stages and are tallied at adult evolution.
- The teen branch gates the adult pool: the good-care teen can reach all six adults,
  the bad-care teen only three.
- **Thresholds:** 0–2 care mistakes = good-tier adults; **3+ = bad tier**; discipline
  mistakes pick the exact character within tier. Perfect care + full discipline →
  Mametchi (the iconic "best" pet); worst care → Tarakotchi.
- **Secret character as a care-style reward:** Oyajitchi requires *never pressing
  Discipline once* plus near-perfect care of a specific adult — the canonical "hidden
  reward for a specific play style." ([TamaVault Gen1](https://tamavault.com/devices/original-gen1/))

## 3. Evolution across generations

**Connection/Plus (2004+):** Gotchi Points money (~100/game win, cap 99,999), shops
(150+ items: meals, snacks, accessories, costumes, furniture), **marriage &
generations** (Matchmaker at 10:30 AM / 3 PM / 7 PM; babies inherit traits/money; a
Generations counter turns one life into a dynasty), and **care-mistake forgiveness**
(winning mini-games can reverse mistakes; several models reverse one mistake on a
near-death rescue).

**Color/later models:** **Daycare/babysitter replaces pausing** (originals had no
pause — walking away = neglect); the Pix sends a sitter to the pet's house.
Personality mechanics, likes/dislikes, NPC marriage, toilet training.

**Tamagotchi Uni (2023):** personality-driven likes/dislikes; **softened death** —
age counter stops at 99 and a well-cared adult lives indefinitely; death is a
consequence of neglect, not an inevitability. The 15-minute rule persists but the
loop is far more forgiving. ([Tama-Palace](https://tamapalace.tumblr.com/post/728009800827518976/tamagotchi-uni-version-126-adds-arrows-to-death))

**Net trajectory:** early Tamagotchi = punishing, permanent death, no pause,
invisible sickness. Modern = forgiving, buffered against real life, enriched with
economy and social/generational progression. Bandai systematically retreated from
every harsh mechanic over 25 years.

## 4. The built-in mini-games

- **Original "Left or Right":** pure 50/50 guessing, 5 rounds, win ≥3 → +1 happiness,
  −1 weight. No skill — just engagement.
- **Connection onward** added skill games (3+ per device, ~100 GP per win):
  Flag (reaction/fake-outs), Jump/Heading (timing), **Dance/Memory (Simon-style
  sequence repeat)**, Shape, Bump, etc. Some models tier rewards (strong win +10
  happiness, loss still +5).
- Games are the canonical weight-free happiness source and, from Connection on, the
  primary income source. Kids realistically play a game or two per pickup, several
  short sessions a day.

## 5. Consolidated numbers

- Meters: hunger/happiness 0–4 hearts; discipline 0–100% in 25% steps.
- Meal +1 hunger/+1 weight; snack +1 happy/+2 weight (never refused); game win
  +1 happy/−1 weight.
- Attention window 15 min → care mistake. 0–2 mistakes = good adult tier, 3+ = bad.
- Heart decay ~6–7 min/heart (old adult), faster young.
- Stages: egg 5 min → baby 1 hr → child 3 days → teen 3 days → adult; secret ~10–12.
- Lifespan: original averages ~12 days (~7 worst to ~25 best care); modern models
  effectively unlimited with care.
- Money: ~100 GP/game win; cap 99,999; 150+ shop items.

## Mechanics most transferable to a daily-care typing game (agent's ranking)

1. Decaying care meters refilled by *doing an action* — the exercise IS the care verb.
2. Meal vs. snack duality (nutritious-but-limited vs. easy-but-costly).
3. Care-mistakes → evolution branching (long-arc motivation) — **needs adaptation to
   lateral-only variety per DESIGN.md principles; no bad-tier shaming.**
4. Attention windows, but borrowing the modern forgiveness model, not the original's.
5. Daycare/babysitter as the pause-substitute for real-life absences.
6. Mini-game → happiness → points loop (Left-or-Right/Flag/Memory map to typing games).
7. Points economy + shop (food, accessories, decorations).
8. Sleep schedule / daily rhythm as the return-tomorrow habit.
9. Discipline reframed as *training/corrections* raising a stat.
10. Generations/marriage as endless late-game progression.

**Design caution:** the original's permanent death, invisible sickness, and no-pause
design were the most-complained-about elements and were softened in every later
generation — lean entirely on the modern, forgiving end of the lineage.
