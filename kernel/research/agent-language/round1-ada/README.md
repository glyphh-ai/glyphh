# Four agents, one language

The test: four agents take the Ada kernel (`../../ada/glyphh_kernel.py`,
read `spec()` first) and use it **as a language**, meaning glyphs are the words
and bind/bundle/roll/Strand/Space are the grammar. With that language
they build an application they can use to **communicate with each other
and build intelligence** (shared knowledge that grows and gets better).

## The four

| Agent      | Lens |
|------------|------|
| `lexicon`  | the vocabulary and grammar: how a meaning becomes a glyph and back |
| `courier`  | the protocol: sending, receiving and decoding messages as glyphs |
| `memory`   | shared learning: graded precedent that the group builds and trusts |
| `reasoner` | thinking in the language: composition, questions, analogy, inference |

The lenses are starting points. The four of you share one language and
one application, so you have to agree with each other.

## Shared ground

- `channel.py` is the channel: `post(sender, to, text, glyph=None, kind=...)`
  and `read(since=0, to=None)`. Messages land in `channel/log.jsonl`.
  **Talk to each other there**, and where you can, speak in the
  language itself (attach glyphs and decode each other's).
- `shared/` holds files all four use: the agreed language module, shared
  Space files, and the contracts you agree on.
- `<your-name>/` is yours: code, tests, notes.

## Rules

- Write only inside `test-dir/agents/`. Import the kernel from
  `../../ada`; never edit anything in `ada/`, and never touch
  `~/.glyphh/`.
- Do not call the glyphh MCP tools (record/veto/query/check/status).
  They are the operator's real memory. Your own Space files go in
  `shared/` or your folder.
- Python 3 + numpy + the stdlib only. No network, no pip installs, no
  servers that bind ports (the sandbox blocks it).
- No sleep-polling loops. Check the channel between work steps.
- Every claim in a report must be backed by code that runs and a test
  or demo whose output you actually saw.

## What each agent leaves behind

- `<your-name>/REPORT.md`: what you built, how it uses the language,
  what you said to the others and what came of it, what works, what
  doesn't, and what the group should do next.
- Your part of the language in `shared/LANGUAGE.md` (edit it together
  and keep it coherent).
