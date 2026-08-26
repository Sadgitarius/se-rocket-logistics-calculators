# SE Rocket Logistics Calculators

Two sizing calculators for **Space Exploration 0.7.57** cargo rockets, in one static page.
No build step, no dependencies, no tracking — a single `index.html` you can open from disk.

**Live:** _(add your Render URL here after the first deploy)_

---

## What it answers

### Sending side

You have a cell producing *N* items/second and you want it in orbit. The page tells you:

- **how many silos** the throughput actually needs,
- **how many stack inserters** to feed each silo, and how many to feed the buffer off belts,
- **how many stacked belts** the trunk needs,
- **how many buffer stacks** sit between the cell and the silos,
- and a timeline of one silo cycle, so you can see the fill window against the lockout.

The thing that surprises everyone: **a silo only accepts for about half of its cycle**, so every
part of the feed upstream has to run well above the cell's average rate. At 1,584 /s with stack 200
the silo needs ~2,623 /s during its 38 s fill window.

### Receiving side

A rocket lands, dumps 500 slots into a pad, and leaves. The page tells you:

- **how many landing pads** the consumption needs,
- **how much buffer storage** to keep outside the pad so a late rocket never starves the belts,
- **how many arms pad → storage** (this side has to be faster than storage → belt) and **storage → belt**,
- **landing interval**, belts out, and the section/capsule return rate your reusability level implies.

## The Buffer toggles

Each section has a **Buffer** switch in its header, on by default.

- **Sending, off** — you have no storage between the cell and the silos, so the cell can only push
  while a silo is open. The page solves for the actual effective throughput with the silos staggered.
  Frequently **one more silo replaces the entire buffer**: at 1,408 /s and stack 50, three silos lose
  9% and four lose nothing, against 845 stacks of chests.
- **Receiving, off** — the pad's own 500 cargo slots are your buffer, and they are empty for the
  whole 5 s landing sequence, so the belts stop dead for 5 s of every interval. The penalty scales
  with cargo *density*, so a small rocket landing often hurts more than a big one landing rarely —
  the inverse of the sending side.

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

Belt trunk figures assume the white deep-space belt: 90 items/s loose, **360 stacked**.

## Running it locally

Open `index.html` in a browser. That's the whole procedure — no server needed.

If you want one anyway:

```sh
python -m http.server 8000
# then http://localhost:8000
```

## Deploying to Render

It is a static site with nothing to build. `render.yaml` in this repo covers it; if you set it up
by hand in the dashboard instead:

- **New → Static Site**, point it at this repo
- **Build Command:** _(leave empty)_
- **Publish Directory:** `.`

Then put the resulting URL into the `og:url` meta tag near the top of `index.html` so Discord
unfurls the link with a proper card.

## License

[The Unlicense](LICENSE) — public domain. Take any part of it, in any form, for anything, with or
without credit. If you build something better on top of it, no need to ask.
