# Horizon

How far ahead, and how far back, can Ada read along a thread of cases?

**As far as the series allows, and no further.** On a control whose best possible answer is known, Ada reads at that
ceiling at every lead, ahead and back, and its forecasts stop saying anything exactly where the series stops being
predictable. On 44 years of daily AAPL and three years of hourly AAPL, with the last 40% held out, the direction of
the price is not predictable at any lead; how big the next move will be is, a little, for weeks; and the recent past
is readable from the present for about three steps.

## The control: a ring with a known table

6,000 cases of a 12-state chain whose transition table is fixed, the last 2,400 held out. "Best possible" is worked
out from the table alone.

| Steps | Ahead: Ada | Best possible | It stays | Base rates | Back: Ada | Best possible |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 76.4% | 76.2% | 76.4% | 25.8% | 76.4% | 76.2% |
| 2 | 61.1% | 61.6% | 57.8% | 25.9% | 61.8% | 61.6% |
| 3 | 51.9% | 53.0% | 43.4% | 25.9% | 53.0% | 53.0% |
| 5 | 38.4% | 38.6% | 27.6% | 26.0% | 38.2% | 38.6% |
| 8 | 29.3% | 30.1% | 21.9% | 25.8% | 30.8% | 30.1% |
| 12 | 26.8% | 26.6% | 20.9% | 25.8% | 28.0% | 26.6% |
| 20 | 25.5% | 25.2% | 25.4% | 25.6% | 25.0% | 25.2% |

The bits Ada's probabilities say over the base rates fall from 1.0 at one step to 0.02 at eight and 0.00 at twelve:
the horizon of this series, found without being told. The beam (one step at a time, the mass spreading again at
every step) arrives at the same answers as each step read on its own.

## AAPL, the last 40% held out

Daily: 11,273 days (1981 to 2026), 4,510 held out. Hourly: 4,987 bars (2023 to 2026), 1,995 held out. Each case is
asked as of its own time.

**Direction ahead: nothing.** Daily, one day on: Ada 50.5%, always-up 53.3%. Hourly, one bar on: 50.6% against
50.5%. No lead is better; over 20 and 60 days Ada is 11 and 15 points worse than always-up, which is the drift.

**Size of the move ahead: a little, for a long time.** Whether a step moves 2% or more (daily; 0.5% hourly). Hourly,
Ada is 1.2 to 2.0 points more often right than the base rates at every lead out to 35 bars. Daily its accuracy is the
base rates' (79.6% against 79.9%) but its probabilities say 0.11 bits more at one day, 0.07 at 20 and 0.05 at 60, all
several standard errors from zero: it knows which days are the risky ones, not which way they go.

**Back: about three steps.** The direction of the day before is in the case (99.8%); two days back 80.7%, three
69.9%, five 57.9%, and nothing at ten. Hourly: 66.3%, 65.8%, 58.9% at one, two and three bars, nothing at seven.

**The halt.** With the halt chosen inside the first 60% (0.05 bits daily), the loop keeps acting on 63% of the
one-day size forecasts, which are 82.5% right, and halts on the rest, which are 74.6% right. On direction it halts on
72% at one day and on everything by ten: it stops where there is nothing to say.

**The beam on market data.** Every day is its own situation, so the mass spreads over 25 precedents at each step
and a beam three wide cuts 99% of it. It reads no better than each step on its own. The beam earns its keep where
situations repeat, as in the ring.

## Baseball, the last 40% held out

The first 480 games of the 2023 season, 35,816 plate appearances, each game a thread, 14,327 held out (every second
one asked). A case is a plate appearance just ended and the state the next one starts from: outs, bases, inning,
half, the lead, the lineup spot, and whether batter and pitcher are same-handed.

**Ahead: nothing from the game state alone.** Whether the next batter reaches base: Ada 66.1%, the base rates 66.9%.
The kind of result: 42.8% against 44.4%. Whether a run scores on the next plate appearance is the one thing the
state tells (runners on, outs): 90.8% against 90.3% and 0.04 bits, gone two plate appearances on. The model knows
nothing of who is batting or pitching, which is where a plate appearance is decided.

**Back: two plate appearances.** Whether the last batter reached: 73.7% against 66.8%; the one before, 71.0% against
67.6%; nothing at three.

The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may
contact Retrosheet at www.retrosheet.org. `data/retrosheet/2023plays.csv` is its parsed play-by-play
(retrosheet.org/downloads/plays/2023plays.zip).

## The test

- `series.py`: the cases. A case's outcomes say how things stood at its own time (today went up; today's move was
  big); what follows a case is the case after it. Nothing is labelled with its future.
- `run.py`: the first 60% is learned from (`Model.learn_thread`); whether to learn pairs of roles and the halt are
  chosen on the last quarter of that 60%; then every held-out case is asked with `before` its own time, so no case
  from then on is read, as a precedent or as a step after one.
- Against two readers that need no model: the base rates so far, and "it stays as it is".
- Standard errors are from blocks of neighbouring cases (20, or twice the lead), since neighbours share their
  precedents and most of their future.
- Probabilities are mixed with 2% of the base rates before they are scored in bits.

```
python run.py ring
python run.py aapl-daily      # about 50 minutes
python run.py aapl-hourly     # about 12 minutes
```

`data/` holds the two exports (`ada_export`, jsonl) of the Ada Cloud models `aapl-daily` and `aapl-hourly`.
`results/` holds each run's table and its numbers.
