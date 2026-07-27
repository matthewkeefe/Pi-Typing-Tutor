# The playtest backlog

Every phase shipped with questions that only children can answer. They
accumulated across nine phases in scattered issue comments; this is all of
them in one place, so a session with the kids can actually work through
them.

**These are the questions the simulation cannot touch.** `tools/simulate.py`
answers pacing and reachability — does a kid at this ability ever unlock a
seventh letter, how many months to a grown-up cat, can they afford the shop.
It says nothing about how any of it *feels*, and feel is what every question
below is about.

## How to run one

Watch, don't ask. A seven-year-old will tell you they liked something
because you are standing there. What they do with their hands is the data:
where they hesitate, what they skip, what they show their sister, what makes
them stop.

Two kids on one device is the real test condition for anything marked
**siblings** — most of the fairness design only fails when there are two of
them in the room.

Note the date and the kid's rough typing speed alongside any answer. Half
these questions have a different answer at 10 wpm than at 30.

---

## 1. Does progress read as steady, or as stuck?

**Phase 1.** Unlock pacing was tuned against a simulation, and the
simulation is a guess about children.

Watch for: a kid who stops noticing new letters arriving, or one who gets a
burst of three and looks overwhelmed rather than pleased.

If it's wrong: `READY_SAMPLES` and `READY_ACC` in `core/adaptive.py` set how
much practice earns a letter; `BURST_ACC` and `BURST_MAX` set how many
arrive at once.

## 2. Do they find the heatmap?

**Phase 1.** It is the competence lever — the cheapest, loudest "look how
much better you are" the game has. It lives on the stats screen, which a kid
has to choose to open.

Watch for: whether they ever open Stats unprompted, and whether they say
anything about the colours when they do.

If it's wrong: it needs to be somewhere they can't miss, which probably
means the main menu.

## 3. Do siblings read cat traits as better or worse? **siblings**

**Phase 2.** Every trait is lateral by construction — no rarity, no tiers,
nothing ranked. That guarantee lives or dies on how kids actually talk about
it.

Watch for: "yours is better", trading, or one kid wanting to re-roll.

If it's wrong: the problem is presentation, not genetics. Look at what the
picker and the hatch reveal emphasise.

## 4. Does Water's word-restart read as punishing?

**Phase 3.** A mistake restarts the word. Words are capped at seven letters
because a restarting nine-letter word is a wall for exactly the kid who
needs accuracy practice most.

Watch for: visible frustration, or avoiding the Water task.

If it's wrong: switch it to backspace-to-fix like Feed. One-line change.

## 5. Is the first wary encounter "cats being cats", or rejection?

**Phase 5.** The most delicate moment in the game. The design sits between
Finch's zero-consequence model and Nintendogs' visible-but-reversible one.

Watch for: distress, guilt, or a kid who stops coming back. Any of those and
it has failed.

If it's wrong: drop to the Finch end — a warmer reunion, no win-back beat at
all.

## 6. Is the mistake shield clever, or cheating?

**Phase 5.** A treat can forgive a slip in Platform Jumper, and that slip
can still earn a perfect-run badge. It's the one place an item touches an
achievement.

Watch for: whether a kid uses it deliberately for the badge, and whether a
sibling objects.

## 7. Does Yarn Chase land for the kid it was built for?

**Phase 6.** It exists for the child who freezes under Platform Jumper's
pressure — same lesson, no stakes. Whether that child exists is a playtest
question, not a design one.

Watch for: whether an anxious kid chooses it over Platform Jumper, and
whether a confident kid finds it boring. Both are useful answers.

## 8. Is a whole-alphabet bowl exciting or overwhelming to a beginner?

**Phase 6, revised.** The bowl used to be built from the letters a kid had
unlocked, which forced a twelve-letter gate — the starting six yield exactly
two viable bowls in the entire word list. It now draws on all twenty-six, so
the mode is open from the first day and a six-letter kid will meet letters
they have not been taught.

That is intended: this is the mode about *finding* words, and you cannot find
a word out of letters you were never shown. It's safe for progression because
Alphabet Soup records no per-key data, so unfamiliar tiles can't reach the
unlock engine. Whether it's *pleasant* is the open question.

Watch for: a beginner who stares at a bowl of unknown letters and quits, or
who hunts happily for the two or three words they can see. Also whether they
type a letter they don't know and go looking for it on the keyboard — that
would be the best possible outcome and the reason to keep it this way.

If it's wrong: the fallback isn't the old gate but a bias — seed bowls from
words weighted toward the kid's unlocked letters, so a beginner gets a mostly
familiar bowl with a couple of new tiles in it. `FULL_ALPHABET` in
`modes/soup.py` is the single place the pool is chosen.

## 9. Is Mystery Word's reveal threshold in the right place?

**Phase 6.** Half the distinct letters showing, then you spell the whole
word.

Watch for: kids stuck at the spelling step with no idea, or kids who never
need to guess a letter at all.

If it's wrong: `REVEAL_SHARE` in `modes/mystery.py`.

## 10. Do the growth stages land at the right months?

**Phase 7.** 10 / 30 / 75 days, paired with 12 / 20 / 26 letters. Simulated,
never observed.

Watch for: a kid who loses interest before the first stage-up, which is the
failure that matters.

If it's wrong: `GROWTH_DAYS` and `GROWTH_LETTERS` in `core/cat.py`.

## 11. Are the contest bars beatable at each tier?

**Phase 8.** Beginner is 8 wpm at 80%; Champion is 40 wpm. Deliberately
generous at the bottom.

Watch for: a kid who cannot clear the Beginner Cup. That is a broken ladder,
not a challenge.

If it's wrong: the bars are a table at the top of `core/contests.py`.

## 12. Does a wall of milestone popups land, or annoy?

**Phase 8.** A kid who has been playing for months trips several milestones
at once the first time the feature runs — nine, in simulation.

Watch for: clicking through without reading. If so, they should be
summarised into one screen rather than queued.

## 13. Does switching cats feel safe? **siblings**

**Phase 9.** A shelved cat is in stasis: locked exactly as it was, ageless,
never hungry. That is the promise. Whether a kid *believes* it is another
matter.

Watch for: reluctance to switch, or checking on the other cat repeatedly to
make sure it's alright. Either means the reassurance isn't landing, and the
words matter more than the mechanic.

## 14. Is a second cat a status object between siblings? **siblings**

**Phase 9.** The known risk. One kid has two cats, another has one, and the
whole design has avoided ranking siblings everywhere else.

Watch for: comparison, or a younger sibling deciding the game isn't for
them.

If it's wrong: the second cat should be visible only inside its own
profile, never in the shared picker.

---

## Questions the simulation already answered

Don't spend playtest time on these — they're settled, and by arithmetic
rather than opinion.

- **Can a beginner ever progress?** Yes. A 5 wpm hunt-and-peck kid unlocks
  their seventh letter around simulated day 60. This was catastrophically
  broken until Phase 8's retune and no playtest would have diagnosed it —
  it looked like "the game is hard", not "the gate is arithmetically
  unreachable".
- **Is the win condition reachable?** Yes. The 5→40 wpm journey persona
  masters all 26 letters by simulated day 600.
- **Can a kid afford the shop?** Comfortably, at every ability level.

Re-run `python3 tools/simulate.py` after changing any tuning constant. Both
gate bugs this project has had were of the same shape — *one element
blocking everything* — and both were invisible to the test suite.
