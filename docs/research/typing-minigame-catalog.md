# Typing Mini-Game Mechanics Catalog

*Research pass 2 (July 2026), agent 3 of 4 (Claude Opus 4.8, web research; single-pass,
not adversarially verified). Feeds DESIGN.md. Mechanics are described by
input/challenge/feedback structure, stripped of theme. Feasibility tags assume Python
curses, ASCII-only, 80x24, ~30fps, kids 8+.*

## Survey highlights

**Tux Typing** (open source, [github.com/tux4kids/tuxtype](https://github.com/tux4kids/tuxtype)):
Fish Cascade (falling letters/words, type before landing — fits-as-is, same family as
our letter-shooter); Comet Zap (comets target 8 cities; triage multiple simultaneous
approaching targets — fits-as-is); XML lesson drills with finger guidance; phrase mode.

**Typing Land** ([Microsoft Store](https://apps.microsoft.com/detail/9n6xlptqqp26)):
the "~40 mini-games" are mostly **theme reskins of a few cores** — balloon-pop
single-target reaction, conveyor-belt throughput pacing, looming-threat defense, plus
a 150-badge meta. Validates a mode-framework-with-variants architecture.

**ZType** ([ztype.com](https://ztype.com/)): wave-based word shooter; multi-target
switching; boss waves = long sentences while distractors spawn. Fits-as-is.

**Typer Shark Deluxe**: approach-defense plus layered structure — **timed shipwreck
bonus round** (type as many flashed words as possible), bosses needing multiple words
back-to-back, **nonsense/scrambled words that remove the word-recognition crutch**, an
earned screen-clear resource. Fits/adaptable.

**Epistory/Nanotale**: word-labeled enemies, multi-word kills, longer words on tougher
enemies, movement-by-typing. Adaptable to ASCII.

**The Textorcist**: **dual-task** — arrows dodge bullet-hell while letters type the
attack word. Typing under divided attention. Adaptable to ASCII.

**Typing of the Dead**: famous for **drill variety on one core** — words → phrases →
paragraphs with punctuation; **trivia Q&A bosses (type the correct answer)**;
fill-in-the-blank; drill/boss-rush practice mode; 2-player co-op. Fits-as-is.

**TypeRacer/Nitro Type**: copy-typing race vs live opponents/ghosts, car advances with
progress; Nitro adds a **spendable burst meter** and a cosmetics economy. Fits-as-is
(ghost/AI opponents avoid networking).

**MonkeyType/keybr/TypingClub**: configurable timed tests with live graphs;
adaptive pseudo-words with weak-key weighting (≈ our planned engine); guided
curriculum with on-screen keyboard.

**Novel mechanics:** rhythm typing (hit keys in a beat window, combo on cadence —
[Typing Tempo](https://store.steampowered.com/app/2332930/Typing_Tempo/)); typing
roguelike/deckbuilder (run-based perk drafts — TypInc, Wordlike); **anagram/word-builder**
(TextTwist/Bookworm — word *production* from a letter bag, needs a word-list validator);
**word-guessing/letter-reveal** (Cryptmaster — hangman-adjacent deduction typing);
head-to-head sabotage vs AI (Typefighters).

## The gaps — mechanics NOT covered by existing + planned modes

Existing (letter-shooter, no-backspace platformer, accuracy-gated drills, occlusion
memory) + planned (adaptive fishing, yarn-chase, pantry-defense) already cover:
single-letter reaction, approach-word defense, perfect-word gating, accuracy gates,
memorization, adaptive weak-key drilling.

**Ranked genuine gaps (kid-appeal × feasibility):**

1. **Copy-typing race vs ghost/AI** (TypeRacer/Nitro) — sustained transcription speed
   with visible opponent pacing + real punctuation; nitro burst meter. fits-as-is.
   *(Already planned as ghost racing — add the burst meter + AI pacer option.)*
2. **Word-guessing / hangman-with-reveal** (Cryptmaster) — kid *produces* a guess;
   correct letters reveal; spelling-from-deduction. fits-as-is. Very high kid appeal.
3. **Anagram / word-builder from a letter bag** (TextTwist) — the only mechanic that
   trains spelling/word *production* rather than copying. fits-as-is (bundle a word list).
4. **Rhythm typing** — even cadence/timing, a skill no current mode touches directly
   (our Pets purr drill is the seed of this). adaptable.
5. **Dual-task type-while-dodging** (Textorcist) — typing under divided attention;
   advanced/optional for older kids. adaptable.
6. **Trivia / type-the-answer** (Typing of the Dead bosses) — reading comprehension +
   typing; trivially educational (spelling lists, math facts). fits-as-is.
7. **Timed burst round** (Typer Shark shipwreck / MonkeyType) — most words in N
   seconds; clean benchmark + daily-challenge material. fits-as-is.
8. **Roguelike perk-draft wrapper** — replay/motivation structure over any drill.
   adaptable; heavier build.
9. **Head-to-head vs AI with sabotage** — composure under competition, hotseat/AI.
   adaptable; more effort.
10. **Nonsense/scrambled strings** — removes word-recognition crutch; a difficulty
    modifier, not a mode. fits-as-is, cheap.

**Redundant with what we have:** Comet-Zap triage, ZType switching (pantry-defense
family variations); balloon-pop (letter-shooter); guided-keyboard tutorials.

**Untapped skill territories:** word production (guessing, anagrams), rhythm/timing,
racing a visible opponent, dual-task, trivia-answer typing.
