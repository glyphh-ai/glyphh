# Games

Games plays games over Claude, with sound, to pass the time while
Claude works: Missile Command, Chickn, Blocks, Rocks and Dash. Each is
endless and gets harder as it goes, with your top score to beat.

```
/games
/games blocks
```

Games works in Claude Code on a Mac. It's a one-time $8 per machine:
`/games unlock` buys it. For effects, see Drips (`/drips`).

## Requirements

- **macOS** and the **Xcode Command Line Tools**, which bring Swift
  (`xcode-select --install`). Games builds its small overlay program
  with them, to play games over Claude's window or the whole screen.

## Install

In Claude Code, run:

```
/plugin marketplace add glyphh-ai/glyphh
/plugin install games@glyphh
```

## Commands

| Command | What it does |
|---|---|
| `/games` | Lists the games, with your best at each |
| `/games <name>` | Starts a game: `missiles`, `chickn`, `blocks`, `rocks` or `dash` |
| `/games unlock` | Buys Games: $8, once, for this machine |
| `/games key <licence>` | Unlocks Games with a licence bought on another Mac |

## Missile Command

`/games missiles` (or `missile`) starts a game of Missile Command over
Claude's window. Missiles streak down from the top at all angles and
speeds, some aimed at your three turrets on the ground. Click where you
want a blast: the nearest ready turret fires an interceptor to that point,
and it bursts into a blast that grows, then fades. Any missile it touches
is destroyed (and can take its neighbours with it). A missile that reaches
the ground leaves a crater; one that hits a turret knocks it out. Each
turret takes a moment to reload.

There are no levels and no end to the sky: it starts gentle and never
stops getting harder. More missiles come, faster and more at once, your
blasts shrink and your turrets reload slower, and before long some split
in flight. Each kill is worth more the harder it gets. The game is over
when your last turret goes. **Esc** quits at once.

## Chickn

`/games chickn` (or `chicken`) starts Chickn over Claude's window. Hop a
pixel chicken as far as it will go: across roads of cars and trucks that
whoosh past, over rivers on creaking logs, and past rail lines, whose bell
rings just before a train screams through. Trees on the grass are in the
way. Hop with the arrow keys or **W A S D**, or click where you want to
hop. Your score is the farthest lane you reach.

The farther you go, the harder it gets: faster, denser traffic, shorter
logs, more trains, and a world that creeps forward faster, so standing
still is never safe. The game is over when a car or a train hits the
chicken, it lands in the water, a log carries it off the edge, or the world
creeps past it. **Esc** quits at once.

## Blocks

`/games blocks` (or `block`) starts Blocks over Claude's window. Pieces of
four squares fall into a well 12 wide; fill a row all the way across and it
clears. **Left** and **Right** move a piece (hold them to slide it), **Up**
or **X** turns it, **Z** turns it back, **Down** drops it faster and
**Space** drops it at once. **C** holds a piece for later, and **P**
pauses. A mark on the floor shows where the piece will land.

The more rows you clear, the faster the pieces fall, with no end. Clearing
several rows at once scores more, and every row is worth more the faster
it goes. The game is over when there's no room for the next piece. **Esc**
quits at once.

## Rocks

`/games rocks` (or `rock`) starts Rocks over Claude's window. Fly a ship
through a field of drifting rocks: **Left** and **Right** turn, **Up**
thrusts, **Space** fires (hold it to keep firing) and **Down** jumps you
somewhere else in a hurry. Space wraps around at the edges. A shot rock
breaks in two, and the pieces break again, until they are dust; the
smaller the rock, the more it is worth. From the third wave a saucer comes
now and then and shoots back.

You have three ships, and one more every 10,000 points. Clear the field and
the next wave comes, with more rocks, moving faster, and a saucer that aims
better each time. **P** pauses and **Esc** quits at once.

## Dash

`/games dash` starts Dash over Claude's window. Your block runs on its own
to a beat; **Space**, **Up** or a click jumps, and holding it jumps again
the moment you land. Clear the spikes and land on the blocks: a spike, or
running into the side of a block, ends the run. Your score is how far you
got, and your best stands on the course as a chequered flag to pass.

The course is the same every run, so you can learn it, and it never ends.
The farther you go, the faster you run and the quicker the beat. **P**
pauses and **Esc** quits at once.

## Playing a game

Each game keeps your top score. Missile Command, Blocks and Rocks show it as the
score to beat; Dash plants it on the course as a flag; Chickn draws it as a chequered line across the lane you reached, and
says **NEW BEST!** when you cross it. Your top scores are kept by Games, so
they stay through restarts and updates.

While a game is on, its overlay takes the mouse and keyboard (it has to,
to hear your clicks and keys); every other effect lets clicks through as
always. 
Every game has sound, made as it plays. Press **M** to mute or unmute;
Games remembers it where it can.

## Where games play

Open `/config` and find **Where games play** under Games:
**claude-window** (the default) plays them over the window Claude runs in;
**fullscreen** over the whole screen under the pointer. **Sounds** turns
every game's sound off (a game's M key still turns it back on).

## Buying it

Games is a one-time $8 for each machine: no account, no
subscription, no trial. Until you buy it, `/games` lists the games but
doesn't start one. Run `/games unlock`: Stripe's checkout opens in your
browser; pay there, and Games unlocks on its own a few seconds
later. On another Mac, run `/games key <licence>` with the licence from the
first. Your licence is checked on your Mac, with a signature, and Glyphh
Arcade never calls home once it holds one.

## Where things are kept

Everything stays on your machine: your licence and your top scores in
Claude Code's store for Games, and the overlay program in
`~/Library/Caches/glyphh-overlay` (shared with Drips).

## For developers

Each game is one file in `hooks/arcade/games/` that builds its whole page,
listed once in `hooks/arcade/games/index.ts`. The overlay (`hooks/overlay/`)
and the unlock (`hooks/unlock/`) are copies of the shared modules in the
source repository: change the source and sync, never the copy.
