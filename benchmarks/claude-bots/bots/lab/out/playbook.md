# How Claude does coding work best: what the lab measured

Stands on 8 experiments, $1.78 spent, 57 trials in the table (bugfix 28, implement 21, multifile 15, with Haiku, Sonnet and Opus). Task count and variety are not given. Every trial passed, so pass rate cannot separate any arm; only cost and time differ.

## The rules
- For bugfix tasks like these, use Haiku with the plain strategy. It passed 100% like Sonnet at 9.7x less cost ($0.0026 vs $0.0251 per trial, 6 trials an arm).
- For implement tasks like these, use Haiku with the plain strategy. It passed 100% like Sonnet at 11.5x less cost ($0.0028 vs $0.0323 per trial, 6 trials an arm).
- Time was about the same across models on bugfix and implement (Haiku 18.9–20.5 s, Sonnet 19.6–19.8 s, Opus 22.0–23.8 s per trial), so the choice rests on cost.
- Opus cost $0.071–0.075 per trial on bugfix and implement (3 trials each), about 24x Haiku, with no pass-rate gain seen.

## No difference found
- e3, tests first vs plain, Haiku, bugfix: both 100% (6 trials an arm). Tests first cost more ($0.0038 vs $0.0023) and took longer (23.8 s vs 19.1 s), so skip it for these tasks.

## Not shown
- Multifile (e4, e5) is still open. Haiku, Sonnet and Opus all passed 100% on 3 trials an arm. Haiku cost $0.0031, Sonnet $0.042–0.043, Opus $0.10 per trial. That is a lead for Haiku, not a rule, because 3 trials cannot separate the models.
- Edge-case prompting (e6, Haiku, implement) is open: 100% both ways (3 trials an arm), but it cost about 2x more ($0.0057 vs $0.0029) and took about 2x as long (44.8 s vs 20.5 s). No benefit seen.
- Whether Haiku fails on harder tasks. Every arm hit 100%, so the tasks may be too easy to separate models (a ceiling effect). "Decisive" here means equal pass rate at lower cost on these tasks, not that Haiku is enough in general.
- The table's per-kind trial counts (for example, 12 bugfix plain/haiku trials) are larger than the per-experiment counts, since they pool across experiments. The rules above use the per-experiment numbers.