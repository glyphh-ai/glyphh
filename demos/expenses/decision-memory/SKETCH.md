# Decision memory: sketch for approval

Nothing is created yet. Approving this means: create the Ada model `decision-memory`, an API key for the hook,
and the hook script plus its entry in `.claude/settings.json`.

## How it works

1. You tell Claude a decision ("we use pnpm, not npm", "dark mode tokens live on :root").
2. Claude records it in Ada with `ada_record` (data below, outcome = the decision's kind), and appends
   `{ id, decision }` to `decision-memory/decisions.jsonl` — Ada's receipts give a precedent's id, sim and outcome,
   not its text, so the text lives here, keyed by Ada's id.
3. On every prompt, a `UserPromptSubmit` hook sends the prompt to `ada.decide("decision-memory", ...)`, takes the
   receipts above a similarity floor, looks their ids up in `decisions.jsonl`, and prints them; Claude Code adds
   what the hook prints to the prompt's context.

## Model spec

```json
{
  "name": "decision-memory",
  "layers": [{
    "name": "decision",
    "segments": [{
      "name": "about",
      "roles": [
        { "name": "ref", "key_part": true, "similarity_weight": 0 },
        { "name": "project", "similarity_weight": 0.3 },
        { "name": "area" },
        { "name": "text", "text_encoding": "bag_of_words", "similarity_weight": 1 }
      ]
    }]
  }],
  "output": { "ask_below": 0.5 }
}
```

- `project`: the repo name, so decisions from this repo rank first but others still show.
- `area`: e.g. tooling, style, architecture, process — also the outcome recorded, so `decide` says which kind
  of decision the prompt touches.
- `text`: the decision in your words; the prompt is matched against it word by word.

## Hook (`decision-memory/hook.mjs`)

```js
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { Ada } from '@glyphh-ai/glyphh';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const FLOOR = 0.35; // receipts less similar than this are left out

const input = JSON.parse(await readFile(0, 'utf8')); // { prompt, cwd, ... }
const project = path.basename(input.cwd);
const d = await new Ada().decide('decision-memory', { decision: { about: { project, text: input.prompt } } });

const known = new Map((await readFile(path.join(HERE, 'decisions.jsonl'), 'utf8'))
  .split('\n').filter(Boolean).map((l) => JSON.parse(l)).map((r) => [r.id, r.decision]));
const hits = d.receipts.filter((r) => r.sim >= FLOOR && known.has(r.id)).slice(0, 5);

if (hits.length) {
  console.log('Decisions Chris has made that may bear on this prompt:');
  for (const r of hits) console.log(`- ${known.get(r.id)} (${r.outcome}, sim ${r.sim.toFixed(2)})`);
}
```

Any error exits quietly so a bad network never blocks a prompt.

## Settings (`.claude/settings.json`)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/decision-memory/hook.mjs\"" }] }
    ]
  }
}
```

The key goes in `GLYPHH_API_KEY` in your shell, not in the repo.

## Open questions

- Every prompt costs one Ada read against your plan's month.
- Project-only (this repo's settings) or global (`~/.claude/settings.json`, so every repo sees it)?
