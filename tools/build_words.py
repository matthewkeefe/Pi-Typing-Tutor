#!/usr/bin/env python3
"""
Build data/words.txt for Pi Typing Tutor (issue #25, referenced by #24).

Curated kid-appropriate vocabulary. Spelling is cross-checked against the
public-domain Webster's Second International list at /usr/share/dict/web2,
used as an ADVISORY typo check rather than a gate: web2 is a 1934 dictionary
and is missing plenty of ordinary modern words ("box", "proud", "mom",
"cookie", and most plurals). Anything web2 does not know must be listed
explicitly in KNOWN_MODERN below, so an unrecognised word is either a
reviewed exception or a build failure -- never a silent drop.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "data", "words.txt"))

HEADER = """\
# Pi Typing Tutor -- kid-appropriate word list
#
# Used by Alphabet Soup (modes/soup.py) to validate the words a kid builds,
# and by Mystery Word (modes/mystery.py) as its hidden-word pool.
#
# FORMAT
#   One lowercase word per line. Blank lines and lines starting with '#'
#   are ignored. Loaded once into a set at startup -- see modes/soup.py.
#   Safe to edit by hand: add or remove lines, order does not matter.
#
# CONTENTS
#   {count} words, {minlen}-{maxlen} letters, a-z only. Concrete and
#   picturable vocabulary for roughly ages 6-11, grouped during curation by
#   theme (animals, food, home, nature, actions, describing words, and so
#   on) so the selection stays auditable.
#
# SOURCE AND LICENSE
#   The vocabulary selection is original to this project and is released
#   under the same MIT license as the rest of the tutor (see LICENSE).
#
#   Spelling was cross-checked against Webster's Second International as
#   distributed with FreeBSD/macOS at /usr/share/dict/web2. That list is
#   public domain: its 1934 copyright has lapsed (see /usr/share/dict/README).
#   No text from web2 is reproduced here -- it was used only to catch typos.
#
#   web2 is a 1934 dictionary and is missing many ordinary modern words
#   ("box", "proud", "mom", "cookie") along with most plurals, so it was
#   used as an advisory check rather than a filter. Words it does not know
#   are listed explicitly in tools/build_words.py (KNOWN_MODERN) and were
#   reviewed by hand.
#
# REGENERATING
#   python3 tools/build_words.py
#   The curated vocabulary lives in that script, grouped by theme, together
#   with the exclusion list and the reviewed modern-word allowlist. Edit
#   there if you want the grouping preserved; edit this file directly for
#   one-off changes.
#
# NOTE FOR IMPLEMENTERS (issue #25)
#   Not every 6-7 letter word makes a usable Alphabet Soup bowl. About one
#   seed in five yields fewer than 5 findable words (repeated letters are
#   the usual cause -- "banana", "church", "raisin"). Filter candidate seeds
#   by actual yield at generation time, as #25's acceptance criterion says.
#   The early alphabet is also thin: with the starting six letters (enitrl)
#   only 2 seeds clear the bar, so this mode needs an unlock gate. See the
#   analysis posted on issue #25.
"""

ANIMALS = """
ant ape bat bear bee beetle bird bison bug bull bunny calf camel cat catfish
cheetah chick chimp clam cobra colt cow coyote crab crane cricket crow cub
deer dingo dog dolphin donkey dove dragon duck eagle eel elk emu ewe falcon
fawn ferret finch firefly fish flea foal fox frog gecko gerbil gibbon giraffe
goat goose gopher gorilla grub gull hamster hare hawk hen heron hippo hog
hornet horse hound husky iguana jaguar jay kitten koala ladybug lamb lark
lemur leopard lion lizard llama lobster locust magpie mammoth meerkat mink
mole mongoose monkey moose moth mouse mule newt octopus opossum ostrich otter
owl ox oyster panda panther parrot peacock pelican penguin pigeon piglet pig
pony poodle porpoise puffin pup puppy python quail rabbit raccoon ram rat
raven reindeer rhino robin rooster salmon sardine scorpion seal shark sheep
shrimp skunk sloth slug snail snake sparrow spider squid squirrel starfish
stork swallow swan tadpole termite tiger toad tortoise trout tuna turkey
turtle viper vulture walrus wasp weasel whale wolf wombat worm zebra
"""

FOOD = """
apple apricot bacon bagel baker banana barley basil bean beet berry biscuit
bread broccoli broth brownie bun butter cabbage cake candy carrot cashew
celery cereal cheese cherry chili chip chowder cider cinnamon clover cocoa
coconut cookie corn crab cracker cranberry cream crumb crust cucumber
cupcake curry custard date dessert dinner dough dumpling egg fig flour fruit
garlic ginger grain granola grape gravy hazelnut honey jam jelly juice kale
ketchup kiwi lemon lentil lettuce lime loaf lunch mango maple marmalade meal
melon milk mint muffin mushroom mustard noodle nutmeg oat oatmeal olive onion
orange pancake papaya parsley pasta pastry pea peach peanut pear pecan pepper
pickle picnic pie pizza plum popcorn potato pretzel prune pudding pumpkin
radish raisin raspberry rice roll salad salsa salt sandwich sauce sausage
scone sesame sherbet snack soup spice spinach sprout squash stew strudel
sugar sundae supper syrup taco tart toast tomato tortilla turnip vanilla
waffle walnut wheat yam yogurt
"""

BODY = """
ankle arm back beard bone brain cheek chest chin curl dimple ear elbow eye
eyelid face finger fist foot freckle hair hand head heart heel hip jaw knee
knuckle leg lip lung mouth muscle nail neck nerve nose palm pulse rib
shoulder shin skin skull smile spine stomach thumb toe tongue tooth waist
wrist
"""

FAMILY = """
aunt baby boy brother buddy child classmate cousin dad daughter family father
friend girl grandma grandpa guest kid man mom mother nanny neighbor nephew
niece parent partner pal sister son teen twin uncle woman
"""

HOME = """
attic bag basement basket bath bathtub bed bedroom bell blanket blender
board bookcase bottle bowl box broom brush bucket bulb cabinet candle carpet
ceiling cellar chair chimney clock closet couch counter cradle cup cupboard
curtain cushion desk dish doorbell doormat door drawer dresser dryer fan
faucet fence floor flowerpot fork frame freezer furnace garage garden gate
hall hammock hamper handle hanger hinge jar kettle key kitchen knob ladder
lamp lantern lawn lid lock mailbox mat mattress mirror mop mug napkin oven
pan pantry patio pillow pipe plate pole porch pot quilt rake roof room rug
shed shelf shower shutter sink soap sofa spoon stairs stool stove table
teapot toaster towel toy tray tub vase wall window yard
"""

SCHOOL = """
answer alphabet art badge bell binder book chalk chapter chart class clock
club college crayon desk diary drawing eraser essay exam folder glue grade
homework ink lesson letter library lunch map marker math music note notebook
number page paint paper pen pencil poem poster print project question quiz
reading recess report ruler school science scissors sentence spelling story
student study subject tape teacher test title verb vowel word writing
"""

NATURE = """
acorn autumn bark bay beach blossom boulder branch breeze brook bud bush
cactus canyon cave cliff cloud clover coast creek crystal daisy dawn desert
dew dirt dune dusk earth fern field flower fog forest fossil garden grass
gravel grove harvest hedge hill ice iceberg island ivy jungle lagoon lake
leaf lily marsh meadow mist moon moss mountain mud nest oak ocean orchard
palm pasture path pebble petal pine plant pond pool prairie rain rainbow
reef reed ridge river rock root rose sand sapling sea seed shade shell
shore sky snow soil spring star stem stone storm stream summer sun sunset
swamp thorn tide trail tree trunk tulip twig valley vine volcano water wave
weed willow wind winter wood
"""

COLORS = """
amber beige black blue bronze brown copper coral cream crimson gold golden
gray green indigo ivory jade lavender lemon lilac lime magenta maroon mint
navy olive orange peach pearl pink plum purple red rose ruby rust salmon
sand scarlet silver tan teal violet white yellow
"""

CLOTHES = """
apron belt blouse boot bracelet button cap cape cloak coat collar cotton
denim dress glove hat helmet hood jacket jeans linen mitten overall pajamas
pocket poncho ribbon robe sandal sash scarf shirt shoe shorts silk skirt
sleeve slipper sneaker sock suit sweater tie uniform vest wool zipper
"""

TRANSPORT = """
airplane anchor axle balloon barge bike boat bridge bus cab cabin canoe car
cargo cart compass crane deck engine ferry fleet glider harbor highway jeep
journey kayak lane mast motor oar paddle pedal plane propeller raft rail
road rocket rudder sail sailor scooter ship shuttle sled sledge subway taxi
tire track tractor traffic trail train tram truck tunnel van voyage wagon
wheel wing yacht
"""

SPORTS = """
archery ball base basket bat bounce catch coach court dance dive dodge field
game goal golf gym helmet hike hockey hoop hurdle jog jump kick lap medal
net pitch play player pool practice prize race racket rally referee relay
rink run score skate ski slide soccer speed sport sprint stadium swim swing
team tennis throw toss track trophy umpire victory volley whistle win
"""

ACTIONS = """
add admire agree aim allow answer appear arrive ask attach bake balance bark
bathe become begin behave bend bite blend blink blow boil borrow bounce bow
breathe bring brush bubble build bump burn bury buy call camp care carry
carve catch cause change chase chat cheer chew choose chop clap clean climb
close collect color comb combine come cook copy count cover crawl create
cross crouch crumble cry cuddle cut dance decide decorate deliver descend
design dig discover dive divide draw dream dress drift drink drive drop dry
earn eat empty end enjoy enter erase escape examine excite expect explain
explore fall fasten feed feel fetch fill find finish fix flap flash float
flow flutter fly fold follow forget forgive freeze frown gallop gather giggle
give glance glide glow grab greet grin grip grow guard guess guide hand hang
happen harvest hatch heal hear help hide hold hop hope hug hum hunt hurry
imagine improve include invent invite join joke jump keep kick knock know
land laugh lead leap learn leave lend lift listen look love lower make march
mark measure meet melt mend mention mix move nap nibble nod notice obey offer
open order pack paddle paint pass paste pat pause peek peel perch pick plan
plant play please plunge point polish pounce pour practice praise prepare
press pretend print promise protect pull push puzzle quiver race raise reach
read recall receive recite record relax release remember remind remove repair
repeat reply rescue rest return reward ride ring rinse rise roam roar rock
roll rub run rush sail save scamper scatter scoop scramble scratch scrub
search seek select sell send settle shake share shine shiver shout shove
show shrink shuffle sigh sing sink sip sit sketch skip slide slip smell
smile snap sneak sniff snooze snore snuggle solve sort speak spell spill
spin splash spread sprinkle sprout squeak squeeze stack stand stare start
stay steer step stir stop store stretch stroll study sway sweep swim swing
tackle take talk tap taste teach tell thank think throw tickle tidy tiptoe
toss touch trace trade train travel treat trot trust try tuck tumble turn
twirl twist unfold unlock unpack unwrap use visit wade wait wake walk wander
want warm wash watch water wave wear weave weigh welcome whisper whistle
wiggle win wipe wish wobble wonder work worry wrap write yawn zoom
"""

DESCRIBE = """
able active afraid alert alive amazing ancient angry awake basic best big
bitter blank blond bold brave breezy bright brisk broad bumpy busy calm
careful cheerful chilly chubby clean clear clever close cloudy clumsy cold
comfy cool cozy creamy crisp crooked crunchy curious curly cuddly damp
daring dark deep delicate dizzy double dry dull dusty eager early easy elder
empty even exact excited fair fancy fast fearless fine firm flaky flat
fluffy fond fresh friendly frosty full funny fuzzy gentle giant gigantic
glad gleaming glossy graceful grand grateful great greedy grumpy handy happy
hard harmless healthy heavy helpful hidden high hollow honest hopeful hot
huge humble hungry icy jolly joyful kind large late lazy light little lively
lonely long loud lovely loyal lucky main massive mellow merry messy mighty
mild misty modern moist mossy narrow neat new nice nimble noisy odd old open
pale patient perfect plain playful pleasant polite precious pretty prickly
proud puffy quick quiet rapid rare ready real rich right ripe rocky rosy
rough round rusty sandy scaly secret shady shaggy shallow sharp shiny short
shy silent silky silly simple skinny sleek sleepy slender slim slow small
smart smooth snug soft solid sore sour sparkly speedy spicy spotless square
steady steep sticky stiff still stormy strange strong sturdy sudden sunny
sweet swift tall tame tangy tender thick thin thirsty tidy tiny tired tough
tricky true useful usual vast warm weak wet wide wild windy wise witty
wonderful wooden woolly young
"""

TIME = """
afternoon age april august autumn birthday calendar century clock daily date
dawn day daytime december dusk early evening fall february friday future
holiday hour january july june late march midday midnight minute moment
monday month monthly morning night noon november october often past present
saturday season second september soon spring summer sunday sunrise sunset
thursday time today tomorrow tonight tuesday wednesday week weekend weekly
winter year yearly yesterday
"""

PLACES = """
airport alley arena bakery bank barn bay bridge cabin camp campus canyon
capital castle cave cellar chapel church city clinic coast corner cottage
country county court dairy dock dungeon farm field forest fort fountain
gallery garage garden gate harbor haven hill home hospital hotel igloo inn
island jungle kingdom lab lake lane library lighthouse lodge mall market
maze meadow mill mine museum office orchard palace park path pier plaza port
prairie ranch region resort river road school shelter shop shore sidewalk
square stable stadium station store street studio suburb temple theater tent
tower town trail tunnel valley village wharf zoo
"""

THINGS = """
album anchor arrow badge ball balloon bandage banner barrel basket battery
beacon beam bead bell blanket block board bolt bottle bowl bracelet brick
bubble bucket bundle button cable camera candle canvas card cardboard cart
chain chalk chart chest chime clay clip cloth coin comb compass cord costume
crate crayon crown cube dial diamond dice doll domino drum feather flag
flashlight flute frame gadget gear gem gift glitter globe glue guitar hammer
handle harp helmet hinge hook horn jewel jigsaw journal kettle key kite knot
label lace ladder lantern lens lever locket magnet marble mask medal metal
mirror mitten model nail needle net note oar package paddle paint pattern
pearl pebble pedal pencil piano picture pin pipe plank plastic plug pocket
poster pouch present printer prism prize propeller puppet puzzle quilt radio
raft ribbon ring robot rocket rope rubber ruler saddle scale screw scroll
sculpture shield shovel signal silver sketch slate sled spade spring statue
steam steel stencil stick stitch string switch tag tape telescope tent thread
ticket timer token tool torch towel toy treasure trophy trumpet tube violin
wagon wand wheel whistle wire wood wrapper yarn zipper
"""

WEATHER = """
blizzard breeze chill cloud cyclone drizzle drought dust flood fog forecast
frost hail haze heat humid hurricane lightning mist monsoon puddle rain
rainbow season shower sleet slush snow snowfall snowflake storm sunbeam
sunlight sunshine temperature thunder tornado weather wind
"""

FEELINGS = """
brave calm cheer cheerful comfort confident courage curious delight eager
excited fond glad grateful happy hope hopeful joy joyful kindness laughter
love patience peace pride proud relief silly smile surprise thankful thrill
wonder
"""

MUSIC = """
album banjo bass beat bell chime chord chorus concert cymbal drum echo flute
guitar harmony harp horn hymn jazz lyric melody music note opera organ piano
pitch rhythm song sound stage tempo trumpet tune violin voice whistle
"""

STORY = """
adventure castle crown dragon dungeon elf fable fairy giant goblin hero
journey king knight legend magic maiden map mermaid myth ogre pirate prince
princess quest riddle rider royal shield spell sword tale throne treasure
unicorn villain wand warrior witch wizard
"""

SCIENCE = """
acid air atom axis beaker biology bubble carbon cell circuit comet compass
crystal cycle data desert earth echo eclipse energy engine experiment fact
force fossil galaxy gas germ gravity heat lab laser lens light liquid magnet
mass matter meteor method microscope mineral molecule moon motion nature
orbit oxygen planet power pressure prism proof pulley radar reaction robot
rocket sample satellite science solar solid sound space speed star steam
sun telescope test theory tissue vapor volume weight
"""

SHAPES = """
angle arch arrow circle cone corner cube curve cylinder degree diagonal
diamond disk dot edge equal even figure graph half heart hexagon inch line
loop math measure meter number octagon odd oval pair pattern pentagon plus
point prism pyramid ring round shape side size slope solid sphere spiral
square star straight sum third total triangle unit whole width zero
"""

JOBS = """
actor artist author baker banker barber builder captain chef clerk coach
cook dancer dentist doctor driver editor engineer explorer farmer fireman
gardener guard guide hunter inventor judge keeper knight lawyer librarian
mayor mechanic miner musician nurse painter pilot plumber poet police
printer ranger reporter sailor scientist scout sculptor singer soldier
student tailor teacher trainer vet waiter writer
"""

COMMON = """
about above after again ago all almost alone along already also always among
and another any anyone around away back because been before behind being
below beside best better between beyond both bring came can come could
did does done down during each early either else enough even ever every few
first found from front full gave get give given goes going gone good got
great group grew had half hand happen has have here high him his how idea
into item its just keep kept kind knew know large last later least left less
let level like line list little live long look lot made main make many may
maybe mean might mile mind more most move much must name near need never new
next nine none not nothing now number often once one only open order other
our out over own page pair part past people perhaps piece place plan please
point put quite rather reach ready real really rest right room said same saw
say seem seen sell send sent seven several she should side simple since six
size small some soon sort sound spot state stay step still stop such sure
take talk tell ten term than that the their them then there these they thing
think third this those three through time today together told too took top
toward true try turn two under until upon use used very view want was watch
way well went were what when where which while who whole why wide will with
within without word work world would year yes yet you your
"""

GROUPS = {
    "animals": ANIMALS, "food": FOOD, "body": BODY, "family": FAMILY,
    "home": HOME, "school": SCHOOL, "nature": NATURE, "colors": COLORS,
    "clothes": CLOTHES, "transport": TRANSPORT, "sports": SPORTS,
    "actions": ACTIONS, "describe": DESCRIBE, "time": TIME, "places": PLACES,
    "things": THINGS, "weather": WEATHER, "feelings": FEELINGS,
    "music": MUSIC, "story": STORY, "science": SCIENCE, "shapes": SHAPES,
    "jobs": JOBS, "common": COMMON,
}

MIN_LEN, MAX_LEN = 3, 8

# Ordinary English that we still keep away from a 6-11 year old's screen.
# Explicit so the exclusion is reviewable rather than buried in a heuristic.
BLOCKLIST = {
    "blood", "die", "dead", "kill", "gun", "war", "hate", "hell", "damn",
    "drunk", "beer", "wine", "knife", "blade", "sword", "bomb", "gross",
    "stupid", "dumb", "ugly", "fat", "naked", "sick", "dungeon", "villain",
    "witch", "goblin", "ogre",
}

# Words web2 (1934) does not contain but which are unquestionably correct
# modern English. Reviewed by hand; anything NOT on this list that web2
# rejects fails the build as a probable typo.
KNOWN_MODERN = {
    "blond", "bookcase", "box", "brownie", "bunny", "campus", "catfish",
    "hang",
    "chimp", "classmate", "comfy", "cookie", "cupcake", "cyclone", "daytime",
    "doormat", "dryer", "dumpling", "firefly", "fireman", "flashlight",
    "forecast", "granola", "has", "hammock", "jigsaw", "journal", "kayak",
    "ketchup", "kiwi", "ladybug", "librarian", "lighthouse", "locket",
    "mailbox", "mom", "monsoon", "neighbor", "oatmeal", "pajamas", "papaya",
    "pasta", "penguin", "piglet", "pleased", "poncho", "popcorn", "proud",
    "puppy", "radar", "raspberry", "recess", "salsa", "sandwich", "satellite",
    "scooter", "seagull", "sidewalk", "sneaker", "snowfall", "snowflake",
    "snuggle", "sprout", "stairs", "strudel", "suburb", "sundae", "sunbeam",
    "sunrise", "sunset", "taco", "toaster", "tortilla", "trainer", "tram",
    "umpire", "unicorn", "unpack", "unwrap", "vet", "weekend", "weekly",
    "wrapper", "yam", "yogurt", "zoom",
}

WEB2 = "/usr/share/dict/web2"


def load_dictionary():
    if not os.path.exists(WEB2):
        sys.exit("error: %s not found -- cannot spell-check the list" % WEB2)
    with open(WEB2, encoding="latin-1") as fh:
        return {line.strip().lower() for line in fh}


def collect():
    out = {}
    for group, blob in GROUPS.items():
        for word in blob.split():
            word = word.strip().lower()
            if word and word not in out:
                out[word] = group
    return out


def build():
    dictionary = load_dictionary()
    curated = collect()

    kept = []
    dropped = {"length": [], "charset": [], "blocked": []}
    suspect = []

    for word in sorted(curated):
        if not (MIN_LEN <= len(word) <= MAX_LEN):
            dropped["length"].append(word)
            continue
        if not (word.isalpha() and word.isascii() and word.islower()):
            dropped["charset"].append(word)
            continue
        if word in BLOCKLIST:
            dropped["blocked"].append(word)
            continue
        if word not in dictionary and word not in KNOWN_MODERN:
            suspect.append(word)
            continue
        kept.append(word)

    return kept, dropped, suspect


def coverage(words):
    """
    How many words are typeable using only the first N letters of the
    unlock order? This is the acceptance constraint for #25: a letter set
    drawn from the kid's unlocked alphabet must yield >= 5 findable words.
    """
    freq = "enitrlsauodychgmpbkvwfzxqj"
    rows = []
    for n in range(6, 27):
        allowed = set(freq[:n])
        hits = [w for w in words if set(w) <= allowed]
        rows.append((n, freq[:n], len(hits), hits[:6]))
    return rows


def main():
    kept, dropped, suspect = build()

    print("kept: %d words" % len(kept))
    for reason, items in dropped.items():
        if items:
            print("  dropped/%-8s %3d  %s" % (reason, len(items),
                                              " ".join(items[:12])))
    if suspect:
        print("\nFAIL: %d word(s) unknown to web2 and not in KNOWN_MODERN:"
              % len(suspect))
        print("  " + " ".join(suspect))
        return 1

    print("\nlength histogram:")
    for n in range(MIN_LEN, MAX_LEN + 1):
        c = sum(1 for w in kept if len(w) == n)
        print("  %d letters: %4d  %s" % (n, c, "#" * (c // 12)))

    print("\nalphabet coverage (words typeable with first N unlock letters):")
    for n, letters, count, sample in coverage(kept):
        if n <= 12 or n % 4 == 0 or n == 26:
            print("  %2d (%-14s) %5d   %s" % (n, letters[:14], count,
                                              " ".join(sample)))

    header = HEADER.format(count=len(kept), minlen=MIN_LEN, maxlen=MAX_LEN)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(header)
        fh.write("\n")
        for word in kept:
            fh.write(word + "\n")
    print("\nwrote %s (%d words)" % (OUT, len(kept)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
