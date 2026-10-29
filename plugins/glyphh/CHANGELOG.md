# The glyphh plugin's changelog

Newest first. The version is `.claude-plugin/plugin.json`'s and the marketplace's.

## 1.4.0 — 2026-10-29

The glyphh command. A new skill, glyphh-cli, does the Ada skill's work through the shell with `glyphh` (the Python
SDK 3.5.0's command, `pip install glyphh`) when the connector's `ada_*` tools are not there, or when a file, a
script or many cases from a file suit a command better. It runs on an API key: the skill asks you to run
`glyphh login` and paste one yourself, never in the chat.

## 1.3.0 — 2026-10-28

Typed outputs and discriminated unions (Ada kernel 3.15.0, on `ada-1-2-beta`).

- The Ada skill writes a named output's `kind` when the case calls for one: `score` for ordered levels, `noul` for
  yes or no, `number` for an amount (`number: {min, max, step}`), `many` for several labels at once, `choice` (the
  default) otherwise. It uses `when: {output, in}` for a question that only applies on one branch of another (a
  discriminated union), so the branch not taken answers `applies: false` instead of a guess.
- It reads each kind's answer to you: a noul's `p`, a number's expected `value`, a score's expected `level`, a many
  output's list. These specs run on `ada-1-2-beta` only; the skill says so and offers a backtest first.
- `references/spec.md`: the kinds, `when`, and how they count against the cloud's limits.

## 1.2.0 — 2026-10-23

Ada versions (contract 5): the skill says which Ada version a model runs, offers a newer stable with a backtest
first (`ada_backtest` with `ada`, then `ada_upgrade` only when you agree, and how to roll back), explains betas and
warns of deprecations; the panel shows each model's Ada version.
