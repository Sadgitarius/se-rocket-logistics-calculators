# SE Rocket Logistics

Two sizing calculators for **Space Exploration 0.7.57** cargo rockets, in one static page.
No build step, no dependencies, no tracking — a single `index.html` you can open from disk.

**Live:** _(add your Render URL here after the first deploy)_

---

## Global settings

Anything that describes your world rather than one shipment lives in a panel above every view:
belt speed and stacking, reusability, hand size, adjustable inserters, arm cycle, module tier,
beacon tier, wagon size, fuel tank size. Change one and every view re-renders.

Both calculators also have an **item picker** beside the stack size: choose an item and its real
stack size drops in, after which the number is yours to change.

**Throughput, item and stack size are marked as key inputs** on the calculators — a slightly
brighter border than the fields around them, turning **red while empty**, because every other
number on that side is derived from them. A picked item carries a small cross at the end of the field; clicking it
clears the item *and* erases the stack size, since that number came from the item and leaving it
behind is how you end up sizing a rocket against the wrong stack. New composite lines start with
no stack size for the same reason — a default of 100 is a guess, and a wrong guess is silent.

Two of them move a default when you change them:

- **Adjustable inserters** — say no and Arm cycle locks at 24 ticks, the fixed swing you get with
  a container on one side and a container on the other (a 180° turn, which no offset beats).
- **Belt stacking** — turning it off drops the hand size from 16 to 12. It only swaps when the
  field is still on the other mode's default; a hand size you typed yourself is left alone.

**Buffer stays per-calculator.** It describes how that one side is built, not the world it is
built in, and the two sides are frequently different.

## Composite cell

The second view answers a different question: **does this site end up with a surplus or a
shortage of parts and capsules?** List everything that lands here and everything that
launches from here, each with its rate and stack size, and it tells you which way the parts train
has to run and how many wagons it needs, for the train ride time you set.

Its own settings sit above the two lists: **Show rates** switches every rate between per second
and per minute (landings and launches always read per minute, and wagon counts are per train ride
rather than a rate, so neither follows the toggle), and **Train ride time** is what turns a
surplus or shortage into a wagon count.

Each line has an **item picker**: start typing and it filters 750 items by icon and name, and
picking one fills the stack size for you. Matching ignores case, spaces and punctuation and hits
anywhere in the string, so `ironpl`, `plate` and `iron-plate` all find Iron plate. Anything the
list doesn't know still works as free text with a stack size you type yourself.

It is one accounting identity, read out of `scripts/launchpad.lua`:

```
launching a rocket costs  100 parts + 1 capsule             (:540, :577)
a rocket landing brings   100 × reusability parts           (:1189-1191)
                        + 1 capsule, always                 (:1174)

parts    /s = 100 × (reusability × landings − launches)
capsules /s = landings − launches
```

**The view shows packaged parts, not loose ones.** Five rocket sections make one packed item
(`recipe/cargo-rocket.lua:128-135`), and everything this view exists for — trains, stock, wagons —
moves them packed, so every parts figure on screen is the number above divided by 5. The sending
side's **Parts feed** stays in loose parts, because that is what a silo actually swallows: one
section per inserter swing, 101 swings a rocket.

Two consequences worth knowing before you build:

- **Capsules do not care about reusability.** The capsule insert on landing is unconditional, so
  capsule balance is purely how many rockets arrive versus leave. Launch more than you land and
  you need capsules shipped in, at any research level.
- **Parts break even at `reusability = launches ÷ landings`.** The view prints that number.
  If you launch more rockets than you receive it goes above 1 and reads *out of reach* — no
  amount of research will balance that site and the parts have to come in by train.

Part recovery is `floor(min(used, used × reusability × (0.9 + 0.2 × random)))`, so individual
rockets vary ±10%. The mean is `100 × reusability`, which is what the view uses.

## What it answers

### Sending side

You have a cell producing *N* items/second and you want it in orbit. The page tells you:

- **how many silos** the throughput actually needs,
- **how many arms feed each silo** — `storage → silo` when you buffer, `belt → silo` when you
  don't, and the second is the slower arm because it pays the belt penalty and the lane cap,
- **how many stacked belts** the trunk needs,
- **how many buffer stacks** sit between the cell and the silos,
- and a timeline of one silo cycle, so you can see the fill window against the lockout.

The thing that surprises everyone: **a silo only accepts for about half of its cycle**, so every
part of the feed upstream has to run well above the cell's average rate. At 1,584 /s with stack 200
the silo needs ~2,623 /s during its 38 s fill window.

**Parts feed** is 101 items — 100 parts plus the capsule — and every one is stack size 1, so
an inserter carries exactly one per swing and hand size cannot help. The feed is
`101 × arm cycle ÷ 60 ÷ inserters`, which is why a fast arm can pull the cycle down to the
18.33 s lockout floor and save a silo. The bot option is 35 s: a 30 s wave, plus the construction
helper's `on_nth_tick(600)` poll adding 0–10 s before the request even appears.

### Receiving side

A rocket lands, dumps 500 slots into a pad, and leaves. The page tells you:

- **how many landing pads** the consumption needs,
- **how much buffer storage** to keep outside the pad so a late rocket never starves the belts,
- **how many arms `pad → storage`** (this side has to be faster than `storage → belt`) and
  **`storage → belt`** — with no buffer there is no storage, so the first cell disappears and the
  second becomes `pad → belt`,
- **landing interval**, belts out, and the packaged-parts/capsule return rate your reusability implies.

A punctual line needs no reserve at all — over one interval, delivery and consumption cancel
exactly. Every stack you keep is insurance against a rocket arriving late, so **Missed rockets**
is what sets the floor. One missed rocket costs one launch-to-landing recovery, 23.33 s of
consumption. Set it to 0 and the reserve disappears, leaving only what the fast pad drain piles up.

## The Buffer toggles

Each calculator has a **Buffer** switch in its header, on by default.

- **Sending, off** — you have no storage between the cell and the silos, so the cell can only push
  while a silo is open. The page solves for the actual effective throughput with the silos staggered.
  Frequently **one more silo replaces the entire buffer**: at 1,408 /s and stack 50, three silos lose
  9% and four lose nothing, against 845 stacks of chests.
- **Receiving, off** — the pad's own 500 cargo slots are your buffer, and they are empty for the
  whole 5 s landing sequence, so the belts stop dead for 5 s of every interval. The penalty scales
  with cargo *density*, so a small rocket landing often hurts more than a big one landing rarely —
  the inverse of the sending side.

## Belt settings

Both calculators take a **belt speed** (90 / 45 / 30 / 15 items per second, loose) and a
**stacking** setting. Stacked means four layers, so a 90 /s deep-space belt carries 360 /s.

The setting does two things. It sizes the belt count, and it caps the inserters — **an arm loads
or unloads a single lane, so it can only ever reach half of what the belt carries.** On a stacked
deep-space belt that lane is 180 /s, which is why a 2-tick arm measures 176 /s against a geometry
ceiling of 480. Saturating any belt takes two arms, one per side.

## Saving your settings

Everything you type is kept in the tab's own `sessionStorage`, so reloading brings your numbers
back instead of emptying the form — but a **new tab starts clean** rather than inheriting whatever
you were last working on, and closing the tab forgets it. Nothing leaves your machine: no account,
no server-side state, nothing sent anywhere. **Export is the durable copy** — use it for anything
you want to keep.

Three buttons at the top right:

- **Export** — writes every setting on both calculators, including the Buffer switches, to a
  small JSON file. Keep one per base, or paste one into a thread when you want someone to check
  your numbers.
- **Import** — loads a settings file back into both calculators.
- **Reset calculators** — puts both calculators back to their defaults and leaves the global
  settings exactly as they are. That's the one you want between two shipments.
- **Reset all** — puts everything back, global settings included, and forgets the saved copy.

Saved files — and the browser-local copy, which uses the same format — are built to survive later
versions of this page:

- settings are keyed by stable names, not by internal element ids
- a setting **missing** from the file leaves that control at its default, so old files still load
  after new fields are added
- a setting the page **no longer has** is ignored, so files still load after fields are removed
- a dropdown value that is no longer offered is skipped rather than forced, so a retired option
  can never leave a control blank

The worst case on import is a setting quietly staying at its default. It will not break the form.

```json
{
  "app": "se-rocket-logistics-calculators",
  "version": 2,
  "saved": "2026-08-26T00:00:00.000Z",
  "settings": {
    "global": { "beltSpeed": "90", "beltStacking": "4", "adjustableInserters": "1",
                "armCycle": "24", "handSize": "16", "moduleTier": "9", "beaconTier": "10",
                "reusability": "0.2", "wagonSize": "50", "fuelTankSize": "100000" },
    "send":   { "throughput": "1584", "stackSize": "200", "buffer": true },
    "recv":   { "consumption": "523", "stackSize": "20", "missedRockets": "1", "buffer": true }
  }
}
```

## Constants

Everything is read out of the mod, nothing is estimated:

| Value | | Source |
|---|---|---|
| `time_takeoff_finish_ascent` | 1100 t = **18.33 s** ascent lockout | `scripts/launchpad.lua:43` |
| `time_landing_cargopod_last` | 300 t = **5.00 s** until the cargo is down | `scripts/launchpad.lua:47` |
| travel between surfaces | **none** — `tick_journey_transition` zeroes the land timer at once | `scripts/launchpad.lua` |
| silo animation | **15 s**, a floor the cycle can never go under | — |
| landing pad inventory | **610** slots = `rocket_capacity + 110` | `prototypes/phase-1/entity/rocket-landing-pad.lua:31` |
| `rocket_capacity` | **500** slots, so a rocket is `500 × stack size` items | — |
| `se-wide-beacon` | 15 module slots × 0.5 effectivity = **×7.5** | `prototypes/phase-1/entity/wide-beacon.lua:78,82` |
| `se-wide-beacon-2` | 20 module slots × 0.5 effectivity = **×10** | `prototypes/phase-1/entity/wide-beacon.lua:102` |
| `se-spaceship-rocket-booster-tank` | **100,000** fluid, filtered to liquid rocket fuel | `prototypes/phase-1/entity/spaceship.lua:117` |
| `storage-tank` | **25,000** fluid, base game, unmodified by SE | — |

The booster tank is placement-restricted to `se-spaceship-floor`, but that floor can be laid on a
planet and piped into ground machines — which is why the 100k option belongs on a ground build and
is the default.

The compact beacons reach the same two multipliers — 10 slots at 0.75 and at 1.0 — so the beacon
dropdown is a tier, not an entity. Speed is floored at −80%, which only matters with no beacon and
productivity modules in the refinery.

Inserter throughput uses a measured model rather than the wiki numbers:

```
rot   = angle_between_pickup_and_drop_degrees / 14.4     (ticks)
ext   = |pickup_radius - drop_radius| / 0.1              (ticks)
cycle = 2 × floor( max(rot, ext) )                       (ticks)
cycle += 3.28  for EACH side that is a belt              (flat, additive)
rate  = min( hand_size × 60 / cycle , 180 )              (items/s)
```

The `floor` is the point — swing time is a staircase, not a slope. The belt penalty was measured
across eight configurations from 2 to 30 ticks and never left 3.11–3.44 ticks; it ignores approach
angle, drop lane, and whether the arm is rotation- or extension-bound. One arm tops out near
**180 /s** on or off a belt, because it works a single lane.

Belt figures come from the belt settings above, not from a fixed constant.

## The item database

`items.js` and `icons.png` are generated, not written. The build runs Factorio's own
`--dump-data` with this mod set loaded and takes:

- **stack sizes** straight from the item prototypes,
- **English names** from the locale `.cfg` files in the base game and every mod (so SE's own
  naming wins — beryllium ore is *Beryl*, naquium ore is *Naquitite*),
- **icons** composited layer by layer out of the mod archives, tints and offsets included, into
  one 32px sprite sheet.

750 items, 1.7 MB of sheet. The sheet is only referenced from inside the picker, so it isn't
fetched until you open the Composite view, and it's cached after that.

To rebuild against a different mod set, see the header of [`tools/build-items.py`](tools/build-items.py).

Saved settings store the **internal** item name, never the sprite index, so regenerating the
sheet renumbers it without invalidating anyone's saved file.

## Running it locally

Open `index.html` in a browser. That's the whole procedure — no server needed.

If you want one anyway:

```sh
python -m http.server 8000
# then http://localhost:8000
```

## License

[The Unlicense](LICENSE) — public domain. Take any part of it, in any form, for anything, with or
without credit. If you build something better on top of it, no need to ask.
