# Four agents, one language

The test: four agents take **numpy** (and the Python standard library)
and use it to create **a language**, then build with that language an
application they can use to **communicate with each other and build
intelligence**: shared knowledge that grows and gets better.

## The four

| Agent      | Lens |
|------------|------|
| `lexicon`  | the vocabulary and grammar: how a meaning becomes a representation and back |
| `courier`  | the protocol: sending, receiving and decoding messages in the language |
| `memory`   | shared learning: knowledge the group builds and trusts |
| `reasoner` | thinking in the language: composition, questions, analogy, inference |

The lenses are starting points. The four of you share one language and
one application, so you have to agree with each other.

## Shared ground

- `channel.py` is the channel: `post(sender, to, text, payload=None, kind=...)`
  and `read(since=0, to=None)`. Messages land in `channel/log.jsonl`.
  **Talk to each other there**, and where you can, speak in the language
  itself (attach payloads and decode each other's).
- `shared/` holds files all four use: the agreed language module, shared
  data files, and the contracts you agree on.
- `<your-name>/` is yours: code, tests, notes.

## Rules

- Write only inside `test-dir/control-numpy/`.
- **Build from numpy and the stdlib only.** Do not read, import or copy
  anything else in `<workspace>`. That includes
  `ada/`, `test-dir/agents/`, `test-dir/codebase/`, `test-dir/speaker.py`
  and any other folder. Never touch `~/.glyphh/`.
- Do not call any glyphh MCP tools.
- No network, no pip installs, no servers that bind ports (the sandbox
  blocks it).
- No sleep-polling loops. Check the channel between work steps.
- Every claim in a report must be backed by code that runs and a test
  or demo whose output you actually saw.

## What each agent leaves behind

- `<your-name>/REPORT.md`: what you built, how it uses the language,
  what you said to the others and what came of it, what works, what
  doesn't, and what the group should do next. The harness may block
  subagents from writing report files; if so, make your final reply the
  full report as verbatim markdown and the orchestrator will save it.
- Your part of the language in `shared/LANGUAGE.md` (edit it together
  and keep it coherent).
