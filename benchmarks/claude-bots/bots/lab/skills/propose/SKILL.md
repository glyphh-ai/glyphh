---
name: propose
description: How the lab proposes experiments
---

Answer with a JSON array of 4 proposals and nothing else:

```json
[{"question": "Does writing tests first make Haiku pass more bugfix tasks?",
  "arms": [{"strategy": "tests_first", "model": "haiku"}, {"strategy": "plain", "model": "haiku"}],
  "kinds": ["bugfix"]}]
```

- Two arms, differing in exactly one thing: the strategy or the model.
- Strategies: `plain`, `tests_first`, `plan_first`, `edge_cases`. Models: `haiku`, `sonnet`, `opus`.
- Kinds: `bugfix`, `implement`, `multifile` (three tasks each, judged by hidden tests).
- Build on what was found: follow up a decisive result (does it hold on another kind, or another model?), and don't
  repeat a question already answered. Favour questions whose answer would change how someone works: whether a cheaper
  model is enough, whether a strategy is worth its cost.
