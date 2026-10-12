# How this build runs

The standing orders for every agent on the Glyphh build. Chris decides; the coordinator leads; nobody improvises.

## The order of every change

1. **Architecture first.** A change to what the system does goes into `server/docs/architecture.md` before anything else, in the doc's voice, on a branch landed on main.
2. **Then the board.** The design agent draws it in `glyphh/design/screens` (every state, desktop 1440 and phone 390, dark and light) and records the decision in `glyphh/design/DESIGN.md`.
3. **Then the build.** Engineers build to the landed architecture and the drawn board. Never the other way round, and never a step skipped, however small the change.

## The design is the spec

- A screen is done when it matches its board **to the pixel**: layout, sizes, spacing, tokens, type, copy, icons, every state. The proof is a pixel diff of the board's frame against the rendered page in the platform's test suite, not the builder's word.
- **Nothing is invented.** No section, step, state, control or copy that the board does not draw. If a board lacks a state, the state is the library component for it exactly as the Components board draws it.
- **One component library**, `platform/ui`. Empty, loading, error, toast, dialog, pagination, fields, buttons, the rail, the page head: the library's, unchanged, the same on every page. Where a board and the library disagree, the board wins and the library is changed to match it.
- A gap in a board (a state the system needs that is not drawn) goes back to the design agent through the coordinator. It is not filled in by the engineer.

## Who owns what

- **Server Engineer:** `server/` (the data model, API, MCP, the SDKs in `glyphh/sdk`). The architecture doc is theirs to keep.
- **Rrotor Engineer:** `rrotor/`, and the server side of the machine link on `rrotor/slice-N` branches.
- **UI Engineers:** `platform/`, one worktree each, one page family at a time.
- **UI Design:** `glyphh/design/`.
- Nobody edits another's repo. A need from another repo is a message to the coordinator.

## Landing

- Work in a worktree on a branch; land on main by fast-forward only when the suite is green at 100% and, for a page, its pixel test passes. Never push in this session.
- The dev server at :5173 serves platform main; Chris tests there. Half-built work never reaches main.
- A server change that alters a table needs the dev database reset; say so in the report.

## Reporting

After each finished piece, one message to the coordinator: the commit, what it is, the tests, the end-to-end or pixel result, and anything taken one way (one line each, no questions). Decisions nobody can make go into the architecture's Open list with the way taken.
