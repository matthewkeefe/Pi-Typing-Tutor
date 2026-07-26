# How Pet Games Glue Mini-Games to the Care Loop

*Research pass 2 (July 2026), agent 4 of 4 (Claude Opus 4.8, web research; single-pass,
not adversarially verified). Feeds DESIGN.md — the structural layer above the daily loop.*

## Per-game structural findings

**Tamagotchi ecosystem (Connection → Uni)** ([Gotchi Points](https://tamagotchi.fandom.com/wiki/Gotchi_Points)):
mini-games are the income engine (~100 GP/win, no daily cap — a weakness later games
fix); date-based passive rewards (GP dig on the 5th monthly); **recurring shop
discounts on fixed dates** rewarding deferred spending. **Meal/snack split with
quality tiers** (cheap meal +1 hunger, premium +2 and happy hearts; snack tiers
+1/+3/+4/+5) and **per-character favorite foods** (bonus reaction) / disliked foods.
Overfeeding punishments (cavity, forced "fat" evolution) — the punishment half we skip.
Cosmetic depth grew every generation: Uni has **4 accessory slots**, placeable
furniture, a 5-group daily-rotating shop, regional exclusives. Mini-game wins can
**reverse care mistakes** — play redeems care.

**Nintendogs** — the defining pattern: **care and skill-building are the same act**
(walking = care + item discovery + points; training = bonding + contest prep).
**Dual currency:** spendable cash + non-spendable Trainer Points that unlock breeds/
items/themes at thresholds — every session advances two bars. **Contest ladder**
(Obedience/Disc/Agility, Beginner → Championship, prize money by tier, **2–3 entries
per day throttle**). No death; neglect = dirty/disobedient, recoverable. Real-time
cooldowns space engagement across days.

**Neopets** — care is deliberately vestigial (pets can't die; feeding is a
once-every-few-days click) and engagement moved to: **capped daily earning** (3 scored
plays/game/day → bounded checklist), **dailies** (Trudy's Surprise: guaranteed prize
**escalating with consecutive logins**), and **long-horizon collections** (avatars,
permanent stamp albums, trophies) supplying month/year-scale goals a solved care loop
can't. ([Jellyneo dailies](https://www.jellyneo.net/?go=dailies))

**Animal Crossing** — the daily-visit masterclass: fixed 5 AM reset; **bounded
regeneration** (4 fossils, 1 money rock, 5 rotating Nook Miles+ tasks) makes a 15–30
minute visit feel *complete*; login streak escalates to 300 Miles at 7 days;
**daily-rotating shop stock + Sunday turnip ritual + weekly visitor rotation +
real-calendar seasonal events**; **gentle reversible absence** (weeds, cockroaches,
bedhead — all cosmetic/self-correcting; villagers *cannot leave without permission*,
a deliberate softening). Devs actively nudge toward one visit/day, not bingeing.

**My Talking Tom / Pou** — the standard four-stat care-verb → room/activity mapping
(hunger/energy/hygiene/fun) with direct manipulation; energy as pacing gate; a clean
coins → cosmetics → level-up spine. **The AVOID evidence:** a peer-reviewed study of
20 children's apps found **100% contained deceptive patterns** (~6 each), 90% ads,
72.8% non-skippable ([arXiv:2512.17819](https://arxiv.org/abs/2512.17819)); it singles
out pet games using **"sad pet animations to emotionally pressure users to return"**
(Bubbu) — the exact anti-pattern our gauges-floor rule exists to prevent. No ads, no
timers-that-sell-skips, no currency doublers, no loot boxes, no fake urgency, no IAP.

**Finch** — the closest analog to typing-feeds-cat: the bird grows **only** from the
user's real effort; earned growth is **permanent**; **absence freezes progress, never
reverses it**; streaks can be **paused, not broken**; returns are greeted with
affection — reunion, not reprimand. Counter-examples: Forest (tree dies — loss-
aversion by design) and Habitica (missed dailies damage your avatar) — the wrong
tradeoff for kids.

## Cross-cutting structural patterns

1. Daily reset at a fixed rollover time.
2. First-visit-of-day / login-streak bonus (rewards showing up, not performance).
3. Bounded daily earning caps → a finishable checklist, sessions feel complete.
4. Visible complete-the-day checklist with a completion payoff.
5. **Dual currency: spendable cash + non-spendable progression points.**
6. Rotating shop stock on daily/weekly cycles.
7. Weekly ritual anchors + seasonal events + collection albums (week/month/year goals).
8. Gentle, reversible, never-punishing absence — reunion framing.
9. Care collapsed into skill/effort — the "same act" (Nintendogs, Finch — our premise).

## What a five-task daily-care typing game likely needs but may be missing (ranked)

1. **Non-punishing absence as an explicit rule** — freeze, never reverse; reunion framing.
2. **A long-horizon collection album** — a solved daily loop flatlines without
   month/year-scale accumulation goals; the shop is a spend sink, not a completion ladder.
3. **First-task-of-day / streak bonus rewarding showing up** — critical for a
   struggling typist on a bad day.
4. **Dual currency** — fish to spend + non-spendable mastery milestones gating unlocks.
5. **Rotating shop stock** — a static weekly list is browsed once and ignored.
6. **Cosmetic depth as the primary sink** — accessories worn on the cat + decoratable
   room; a lasting visible record of effort (consumables aren't).
7. **Visible checklist + all-five-done completion bonus.**
8. **Meal/treat quality tiers + favorites** — makes shopping a decision.
9. **Contest ladder** (Beginner → Championship, throttled entries) — aspirational
   track above daily care.
10. **Weekly rituals + seasonal events** keyed off the Pi's clock.
11. **A big-ticket aspirational sink** — one expensive dream item anchors saving.
12. **An explicit, positive "done for today" state** — the healthy session boundary.

**One-line synthesis:** the typing=care premise is structurally sound (it mirrors the
best of Nintendogs and Finch); the gaps are almost entirely in the *layers above the
daily loop* — the same scaffolding AC, Neopets, and Tamagotchi use to keep a solved
care loop engaging for months.
