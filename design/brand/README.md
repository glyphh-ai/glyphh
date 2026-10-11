# Brand assets

Everything here is the source artwork for Claude Design. Upload it to the design-system project.

- `logo/`: the Glyphh logo and mascot, as on glyphh.ai (light and dark versions, the favicon).
- `cats/`: the 16 super power faces, each the Glyphh cat with one or two parts changed (eyes, ears, tail, an antenna, a cape, a bolt). `01-glyphh` is Glyphh itself; `02-side-eye` is the face a new super power wears until one is picked.
- `moods/`: Glyphh's moods. A mood changes the eye, so a cat shows what its super power is doing: idle, thinking, generating, done, listening, error, curious, sleepy, playful, dizzy.
- `glyphh-alive.svg`: Glyphh with its motion, as a reference: open it in a browser.

## Motion

- **Blink:** every 5 s, the eye squashes to a tenth of its height and back (the last 8% of the cycle).
- **Hop:** now and then (every 4 to 9 s on the site), a squash, a 7px hop, a squash on landing and a small bounce.
- **Ring and comet** (the site's hero): the cat sits in a glowing ring whose rim turns slowly (14 s a turn); at random moments a bright comet sweeps once round the ring (1.5 s), shedding dust that drifts outward.
- **Pop in:** a cat appears scaled from 0.6 and turned -8°, settling in 0.6 s.
- All of it stops for people who turn motion off.

## Colour today

Every cat is drawn in Glyphh ink (`#0b0a0f`) inside a white sticker border, and stays black and white: a super power's colour fills only its eye (the white parts inside the `eye` group). Glyphh's own eye stays white. See `../DECISIONS.md`.
