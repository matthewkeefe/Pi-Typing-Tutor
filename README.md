# Typing Tutor

An offline, gamified typing tutor for kids. Pure Python 3 standard library —
no pip installs, no network, nothing to phone home. Built to be the only thing
a Raspberry Pi 5 does.

```
python3 main.py
```

Needs an 80x24 terminal minimum. Save data lands in `./data/profiles.json`;
override the location with `$TYPING_TUTOR_DATA`.

---

## Testing on a Mac

It runs as-is. macOS ships Python 3 with `curses` built in, so there's nothing
to install:

```bash
cd typing_tutor
python3 main.py
```

Terminal.app opens at exactly 80x24, which is the minimum, so you're fine —
but if you've shrunk the window, the app now says so and redraws live while you
drag it bigger. `Cmd -` shrinks the font if you'd rather gain room that way.

Two things worth knowing:

- **Delete vs Backspace.** macOS sends `0x7F` where Linux consoles send `0x08`.
  Both are handled, so backspace works the same in both places.
- **Colors.** If everything comes out monochrome, your `TERM` is off. `echo $TERM`
  should say `xterm-256color` in Terminal.app or iTerm2.

The Mac and the Pi run identical code, so whatever you tune on the Mac —
word lists, difficulty, passages — carries over unchanged.

---

## Getting to a single SD card

The end state is one card you push into the Pi and it just goes. Two ways there.

### Path A — Pi OS Lite + the installer (an evening)

This is the one to do first, and it already meets your bar: wifi is off before
Linux even boots, and turning it back on means editing the card on another
machine.

1. **On the Mac**, install Raspberry Pi Imager. Choose *Raspberry Pi OS Lite
   (64-bit)*, pick your card, and in the gear menu set a hostname, enable SSH,
   and create your own admin user. Write it.
2. **Boot the Pi** with a keyboard, monitor, and an ethernet cable. Log in as
   your admin user.
3. **Copy this folder over** — over ethernet from the Mac:
   ```bash
   scp -r typing_tutor youruser@raspberrypi.local:~/
   ```
   Or just put it on the card's boot partition from the Mac and move it after.
4. **Run the installer:**
   ```bash
   cd ~/typing_tutor
   sudo ./install-pi.sh
   sudo reboot
   ```

That card is now the finished product. It boots straight into the tutor, has no
wifi, no Bluetooth, no shell prompt, and no reachable virtual terminals. Unplug
the ethernet and hand it to the kids.

**To duplicate or back up the card**, pull it and clone it on the Mac:

```bash
diskutil list                                  # find the card, e.g. /dev/disk4
diskutil unmountDisk /dev/disk4
sudo dd if=/dev/rdisk4 of=~/typing-tutor.img bs=4m status=progress
```

Note the `r` in `rdisk4` — the raw device is many times faster. Write it back to
a fresh card with Raspberry Pi Imager's "Use custom" option. Now one card became
as many as you have kids.

### Path B — Buildroot (a weekend, only if you want the kernel-level lock)

Buildroot outputs `output/images/sdcard.img` directly, which is the purest version
of what you asked for: flash it, insert it, done, with no wireless code compiled
into the kernel at all.

The catch on a Mac is that Buildroot needs a Linux host. On Apple Silicon, run an
arm64 Ubuntu VM (UTM, Lima, or Docker Desktop) — it's native, so it's fast. Build
inside the VM, copy the `.img` out, and flash from the Mac.

Details are in the kernel-symbol table further down. Worth doing only if Path A's
"someone could re-edit the card" gap actually bothers you.

---

## The modes

**Rocket Builder** — level based. Seven lesson levels, seven rocket parts. Clear a
level's word drill at 85%+ accuracy and the next part gets welded onto the ship:
engine bell, fuel tanks, nose cone, fins, viewport, then fuel and ignition. Finish
all seven and it launches off the top of the screen, then resets so they can build
a faster one. Mistakes must be backspaced before you can continue.

**Dino Chomp** — endless, score based. Letters drift in from the right; type one and
the dino chomps the nearest match. Three lives, everything speeds up as the score
climbs, combos multiply points. This is the mode that builds raw reaction speed on
individual keys.

**Platform Jumper** — accuracy focused. Each platform has a word. Type it perfectly
and your character leaps to the next one. **There is no backspace here on purpose** —
one wrong key and you fall, losing a life and your streak. Ten platforms per run;
clear it without falling for the perfect-run badge. This is the mode that teaches
"get it right the first time," which is what actually raises WPM long-term. Your
cat is the jumper, drawn from its own genes.

**Yarn Chase** — the same accuracy lesson with nothing at stake. Type a word
perfectly and your cat pounces on the toy; miss a letter and the toy just wiggles
away, resetting the streak and nothing else. No lives, no falls, and the round is
always ten flicks however it goes. It exists for the kid who freezes under Platform
Jumper's pressure: same habit, taught by making a good word feel good instead of
making a bad one cost something. Words come from the adaptive engine, so it drills
weak keys. Owning a toy from the shop changes what your cat chases.

**Pantry Defense** — endless, score based. Mice sneak in from the right, each
carrying a word; type it and the cat swats them away. Let one reach the food bowl
and it costs a life, three lives and the run is over. The stakes are score-only:
a mouse that gets through never eats fish, never touches your streak, never undoes
a day's care. Losing here should feel like losing a game, not like losing progress.
Words come from the adaptive engine and get longer as your alphabet grows.

**Alphabet Soup** — the only mode that trains word *construction* rather than
copying. Six or seven letters float in the cat's bowl; make as many words as you
can before the soup cools. Every other mode shows you what to type — this one
makes you find it, which is spelling and vocabulary. A word that isn't in the list
gets a slurp and nothing else: no lost time, no lost score, no lost fish, because
guessing is how you find words. The soup cooling ends the round and scores it;
there's no way to lose, only to stop. Appears once you've unlocked twelve letters —
below that the word list can't build a bowl worth solving.

**Mystery Word** — the cat paws at a covered dish with a word written under
the lid. Guess letters to reveal it, and once enough is showing, spell the whole
thing out to open the dish. Every other mode shows you the target and asks you to
copy it; this one hides it, so you're producing a word from partial information —
spelling from deduction, which nothing else here trains. Six wrong guesses ends
the round with a "maybe tomorrow" and the dish still covered. Nothing is lost, and
nothing gets drawn on a gallows.

**Whisker Quiz** — the cat asks a question, you type the answer. Reading
comprehension plus typing, and the questions live in `data/quiz.txt`, so it becomes
whatever you put in there. Matching forgives case and spacing, and a question can
list several right answers so nobody is marked wrong for typing "eight" instead of
"8". Miss one and the cat shows you the answer and asks it again later. No lives.
Delete the file and the mode quietly disappears.

**Memorize** — repetition with progressive occlusion. Straight repetition just teaches
copying, so each successful pass blanks out more of the text:

| Pass | Hidden |
|------|--------|
| 1    | 0%     |
| 2    | 25%    |
| 3    | 50%    |
| 4    | 75%    |
| 5    | 90%    |
| 6    | 100%   |

Finish the blind pass and it counts as memorized. `TAB` peeks for 1.5 seconds — it
doesn't fail you, it just gets counted so you can see how much scaffolding was needed.

Passages come from `data/passages.txt` (one per line). Put their spelling list,
times tables, or a poem in there and it becomes the drill.

### Load your own quiz

`data/quiz.txt` works the same way, one `question|answer` per line:

```
What is 2 plus 2?|4;four
What is the capital of France?|paris
```

Semicolons separate answers that should all be accepted — `4;four` so a kid isn't
marked wrong for spelling out a number. Matching ignores case and surrounding
spaces. Lines starting with `#` are comments, malformed lines are skipped rather
than crashing, and an empty file just hides the quiz.

The shipped set is a starting point, not a curriculum: delete it and drop in this
week's spelling words. Keep answers to a word or two — a long answer turns a quiz
back into a transcription drill, which every other mode already does.

---

## Progression and badges

Every profile tracks day streaks, total words, best WPM, best accuracy, and per-mode
bests. 22 badges cover daily habit (3/7/30-day streaks), speed (15/25/40/60 WPM),
accuracy, and per-mode milestones. New badges pop up immediately when earned —
that immediate feedback is most of why kids come back.

Multiple kids can share one device; each gets their own profile from the opening
screen.

---

## Deploying to the Pi 5

Two paths depending on how tamper-proof you need it.

### Firmware-level wifi kill (what `install-pi.sh` does for you)

For reference, these are the pieces the installer puts in place:

```bash
# applied by the firmware before Linux boots -- the radio never comes up
echo "dtoverlay=disable-wifi" | sudo tee -a /boot/firmware/config.txt
echo "dtoverlay=disable-bt"   | sudo tee -a /boot/firmware/config.txt

# second layer: the driver modules can't load even if the overlay is removed
sudo tee /etc/modprobe.d/no-wireless.conf <<'EOF2'
blacklist brcmfmac
blacklist brcmutil
blacklist cfg80211
blacklist btbcm
blacklist hci_uart
EOF2
```

Plus autologin on tty1 to an unprivileged `typist` user whose `.bash_profile`
runs the tutor in a `while true` loop, and `NAutoVTs=1` so Ctrl+Alt+F2 through
F6 don't exist. Quitting the app just restarts it; there is no shell to reach.

### Kernel-level wifi removal — Buildroot

This is the one where wifi isn't disabled, it *doesn't exist* in the kernel binary.

```bash
git clone https://gitlab.com/buildroot.org/buildroot.git
cd buildroot
ls configs/ | grep -i raspberrypi     # confirm the Pi 5 defconfig name
make raspberrypi5_defconfig
```

**Packages** (`make menuconfig`):
- `BR2_PACKAGE_PYTHON3` — the interpreter
- `BR2_PACKAGE_NCURSES` plus the terminfo data, or curses won't initialize.
  Setting `TERM=linux` on the console is the lightest option.

**Kernel** (`make linux-menuconfig`) — turn these *off*:

| Symbol | What it kills |
|--------|---------------|
| `CONFIG_WLAN` | master switch for all wireless LAN drivers |
| `CONFIG_CFG80211` | the 802.11 configuration stack |
| `CONFIG_MAC80211` | the softMAC stack |
| `CONFIG_BRCMFMAC` | the Pi's Broadcom FullMAC wifi driver |
| `CONFIG_BRCMUTIL` | its support library |
| `CONFIG_BT` | the entire Bluetooth subsystem |

Leave these *on* so you keep ethernet for maintenance:
- `CONFIG_NET`
- the Pi 5 ethernet driver. Note this differs from the Pi 4 — the Pi 5's NIC hangs
  off the RP1 southbridge and uses the Cadence GEM driver (`CONFIG_MACB`), not the
  `CONFIG_BCMGENET` driver you'd use on a Pi 4. Confirm against `dmesg | grep -i eth`
  on a stock Pi 5 image before you strip anything.

Also delete the wifi firmware blobs from the rootfs — with no driver they're inert,
but there's no reason to ship them.

**Boot straight into the app.** BusyBox inittab:

```
::sysinit:/bin/mount -t proc proc /proc
::sysinit:/bin/mount -o remount,rw /
::sysinit:/bin/mount -a
tty1::respawn:/usr/bin/env TERM=linux TYPING_TUTOR_DATA=/data /usr/bin/python3 /opt/typing_tutor/main.py
```

`respawn` means quitting the app just restarts it — there's no shell to drop to.
Do **not** add getty entries for tty2–tty6, or Ctrl+Alt+F2 hands them a prompt.

**Storage layout.** Mount the rootfs read-only so a yanked power cord can't corrupt
it, and give the save data its own small ext4 partition mounted at `/data`
(hence `TYPING_TUTOR_DATA=/data` above). `profiles.py` already writes atomically
via a temp file and `os.replace()`, and quarantines a corrupt save rather than
crashing, so a bad shutdown mid-write costs at most the last session.

---

## Structure


```
main.py               entry point, profile picker, menu, stats, badge screens
install-pi.sh         one-shot Pi lockdown + autostart installer
core/lessons.py       7 progressive levels, home row -> sentences
core/engine.py        shared WPM/accuracy measurement + per-key capture
core/adaptive.py      per-key confidence, letter unlocks, word generator
core/cat.py           cat genetics from one seed, ASCII poses, idle behaviour
core/profiles.py      JSON save data, day streaks, atomic writes
core/badges.py        22 badge definitions and award logic
core/ui.py            curses helpers: colors, menus, per-char typing display
core/fx.py            ASCII particle effects: sparks, confetti, splashes, purrs
core/shop.py          item catalog, weekly rotation, fish economy, treat effects
core/wordlist.py      shared word-list access: loading, filtering, bowl building
modes/rocket.py       level-based ship builder
modes/dino.py         endless letter chomper
modes/platformer.py   accuracy-focused jumper (the cat is the jumper)
modes/yarn.py         accuracy drill with no lives and nothing to lose
modes/pantry.py       word arcade: shoo mice off the food bowl
modes/soup.py         anagram word-builder (unlock-gated at 12 letters)
modes/mystery.py      hidden-word deduction, then spell it out
modes/quiz.py         type-the-answer trivia from data/quiz.txt
modes/memorize.py     progressive-occlusion repetition drill
modes/feed.py         the Food task: adaptive weak-key drill, as fishing
modes/care.py         care board + the Water / Pets / Clean activities
data/passages.txt     your own memorize content
data/words.txt        curated kid-appropriate word list (see its header)
data/quiz.txt         your own quiz questions -- swap in a spelling list
tools/build_words.py  regenerates data/words.txt from curated vocabulary
tests/                stdlib unittest suite for the non-curses code
```

Adding a mode means writing a `play(stdscr, profile)` that returns a session
summary dict and adding it to `ARCADE` in `main.py`. That one list feeds both
the free-play menu and the care board's Play choices.

A mode can also define `available(profile)` to hide itself when it has nothing
to offer — Alphabet Soup uses it below twelve unlocked letters. Keep it cheap;
it runs every time the menu is drawn. Modes without the hook are always shown.

Run the tests with `python3 -m unittest discover -s tests`.

## The adaptive engine

`core/adaptive.py` is a stdlib port of keybr's mechanism, and it runs quietly
under the modes rather than as a screen of its own:

- Every drill keystroke a mode reports (`sess.keystroke(correct, ch=expected)`)
  becomes per-key statistics: how often that key is missed, how long it takes.
  Modes that don't pass `ch` are unaffected.
- Each key gets a 0..1 confidence blending speed and accuracy. At 0.8 it's
  **green** — mastered.
- Kids start with six letters (`e n i t r l`). When all of them are green,
  exactly one new letter unlocks, down the English frequency list.
- Drill words are pronounceable pseudo-words generated from an English bigram
  table, restricted to the unlocked letters, with the kid's weakest letter
  worked into every word.

You can watch all of it on the stats screen: the keyboard heatmap paints
mastered keys green, unlocked-but-learning yellow, and not-yet-reached blue.
Dino Chomp uses the same data to spawn the letters a kid is worst at.

Old save files pick this up automatically — the profile gains `keys` and
`alphabet` on first load.

## The cat

Making a new player hatches one. An egg wobbles on screen, the kid's first
keystrokes crack it open, and out comes a kitten they get to name. ESC skips
the drill at any point — the cat is theirs either way, because a kid should
never be trapped in a ceremony. Saves made before the cat existed get offered
a hatch on their next login, and can decline.

The whole animal comes from one integer seed, so a cat costs four bytes of
save data and is reconstructable forever. Fur, eyes, ears, build, tail,
colours and personality are all drawn from that seed, and personality steers
what the cat does when it's idling on the menu — a sleepy cat naps, a
mischievous one pounces.

Every trait is **lateral**: different, never better. There are no rare cats
and no good genes. Siblings share this device and will absolutely compare,
so there is nothing here for the game to rank.

Cats double as profile icons — the little `(o.o)` face beside each name in
the picker is that kid's own cat, in that cat's colours.

## The daily loop

The cat greets your kid on arrival and says what it would like today. Care
comes first, then the arcade opens:

| Task | What they do | What it actually trains |
|---|---|---|
| **Food** | Fishing: type a word, a fish arcs into the bowl | Their weakest keys — the core of it |
| **Water** | Fill the bowl without spilling; a mistake sloshes and the word restarts | Accuracy before speed |
| **Pets** | Type a soothing phrase smoothly; a steadier rhythm purrs louder | Even cadence |
| **Play** | Any game they like, their pick | Autonomy — plus whatever they chose |
| **Clean** | Litter scoop: numbers and punctuation | The keys nobody practises |

All five together run about ten minutes, and the kid picks the order. That
last part matters more than it sounds: structure with real choices inside it
is what the research found actually moves motivation at this age.

Doing all five opens free play for the day and earns a fish bonus. Fish come
from **words typed**, never from scores — showing up on a bad day pays the
same as a good one. Stats, Badges, Switch player and Quit are never gated,
and ESC always backs out of anything.

Nothing in the care activities can be failed. No lives, no timers, no score
penalties. The worst available outcome is stopping early, and whatever was
done still counts.

## The shop

Fish buy toys, treats, decorations and litter. New things appear each week
plus one pick of the day, and the cat has an opinion about all of it.

Browsing is never gated and never costs anything — window shopping with an
empty pocket is a perfectly good thing for a kid to do. If they can't afford
something the game says *"20 more fish and it's yours"* and reminds them
nothing here ever goes away for good.

- **Toys and decorations** are permanent. Decor shows up beside the cat on
  the menu, so a shelf of stuff is the visible record of months of care.
- **Treats** are consumables the kid chooses to use before a game: forgive
  your first slip in Platform Jumper, get one dropped combo back in Dino
  Chomp, or 30 seconds of double score. No treat ever types anything for
  anybody or skips practice — they're buffers and bonuses only.
- **Litter tiers** are streak insurance, bought *before* you need it. Clumping
  covers one missed day, self-raking deluxe covers two.
- **The Deluxe Cat Tree** costs 900 fish and is always on the shelf, for a kid
  who wants something to save towards.

There's no gambling anywhere in it: no loot boxes, no random rewards, no
spinning anything. You see the price and you get the thing. Stock rotates but
nothing expires, so missing a week costs nothing.

## The wary cat

Leave the cat alone for several days and it greets you from across the room
with its ears half-back. Before it'll accept a cuddle or a game it wants a
moment of slow, even typing — the same rhythm drill as Pets, in costume.
Rush it and it swats and steps back; go gently and it comes closer, then
bumps its head against your hand.

This is honest — real cats are exactly like this — but it is carefully
bounded, because the moment a kid comes back after a lapse is precisely
where they decide whether to keep playing:

- **A swat costs seconds and nothing else.** No lives, no score, no fish, no
  streak, no progress. There is nothing in the wary state that can subtract.
- **It's always winnable.** The distance is hard-capped and the steadiness
  needed drops with every attempt until anyone clears it. Worst case is under
  a minute.
- **The cat is wary, never hostile** — "not yet, slow down", never rejection.
- **A comeback day ends warmer than a normal one.** Finish the care board
  after a wary spell and there's an extra fish gift and *"Mochi missed you."*

### What happens when nobody plays for a week

The gauges empty and the cat sleeps and misses you. That's the whole of it.
Fish, badges, streak records, tricks and growth are all exactly where they
were left — absence freezes progress, it never reverses it, and coming back
is a reunion rather than a telling-off. There is no death, no sickness, and
no guilt messaging anywhere in this game, by design.

## Tuning it for your kids

- **Word lists** — `core/lessons.py`, the `LEVELS` list. Swap in their spelling words.
- **Mastery pace** — `core/adaptive.py`, the tuning block at the top: `GREEN`
  (how good counts as mastered), `TARGET_MS`/`FLOOR_MS` (what fast means for
  your kid), `MIN_SAMPLES` (evidence needed before a key can go green).
- **How busy the screen is** — `core/fx.py`, `MAX_PARTICLES` (drop it for a
  calmer screen, or to nothing at all — every effect is additive and the game
  plays identically without them).
- **Shop prices** — `core/shop.py`, the `price` on each `CATALOG` entry. A full
  care day earns roughly 50 fish, so most things are a day or two of showing up.
- **How patient the wary cat is** — `modes/care.py`, `WARY_START_DISTANCE` and
  `WARY_MERCY` (how fast the bar drops so it stays winnable).
- **Care pace** — `core/cat.py`, `GAUGE_FULL_HOURS` / `GAUGE_EMPTY_HOURS` (how
  fast a gauge drifts down) and `modes/care.py`, `WATER_WORDS` / `CLEAN_LINES`
  / `PURR_REPEATS` (how long each care task runs).
- **Rocket pass threshold** — `modes/rocket.py`, the `85.0` in `play()`.
- **Dino difficulty ramp** — `modes/dino.py`, `_speed_for()` and `_spawn_gap()`.
- **Platformer harshness** — `modes/platformer.py`, `RUN_LENGTH` and `LIVES`.
- **Yarn Chase length** — `modes/yarn.py`, `FLICKS`.
- **Pantry difficulty ramp** — `modes/pantry.py`, `speed_for()`, `spawn_gap()`,
  `max_on_screen()` and `max_word_len()`.
- **Mystery Word patience** — `modes/mystery.py`, `MAX_WRONG` and `REVEAL_SHARE`.
- **Quiz round length** — `modes/quiz.py`, `ROUND` and `RETRY_LIMIT`.
- **Occlusion ramp** — `modes/memorize.py`, `REVEAL_SCHEDULE`.
