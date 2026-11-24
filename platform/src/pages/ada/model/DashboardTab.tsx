import { useMemo, useState, type ReactNode } from 'react';
import { useAdaStats, type AdaJob, type AdaModel, type ModelStats, type OutputAnswers, type SpecOutput } from '@/api/ada';
import { Chart, type Series } from '@/components/Chart';
import { ago, date, plural } from '@/lib/format';
import { outputOf } from '@/lib/spec';
import { useInk } from '@/lib/tokens';
import { Card, Chip, LoadingCard, ProgressBar, Select, type ChipTone } from '@/ui';
import usageStyles from '@/pages/settings/usage/meters.module.css';
import { AdaErrorNotice } from '../AdaErrorNotice';
import styles from '../ada.module.css';

const n = (value: number) => value.toLocaleString('en-GB');
const share = (part: number, whole: number) => `${Math.round((100 * part) / whole)}%`;
/** 2026-10-22 as 22 Oct. */
const dayText = (day: string) => date(`${day}T00:00:00Z`).split(' ').slice(0, 2).join(' ');
/** The default output, as the spec helpers name it. */
const DEFAULT = 'default';
/** The most outcomes an output's chart shows; the rest are one bar. */
const OUTCOMES_SHOWN = 12;
const SAMPLED = 'Estimated from a sample: this model is too big to count on every look.';

const kindText: Record<string, string> = { import: 'Import', export: 'Export', learn: 'Learn', calibrate: 'Calibrate', reencode: 'Re-encode', backtest: 'Backtest' };
const stateTone: Record<string, ChipTone> = { done: 'green', failed: 'red', running: 'blue', queued: 'neutral', awaiting: 'neutral' };
const stateText: Record<string, string> = { done: 'Done', failed: 'Failed', running: 'Running', queued: 'Queued', awaiting: 'Waiting for the file' };

/** Nothing to draw yet, said in a line where the chart will be. */
function Nothing({ children }: { children: string }) {
  return <p className={styles.nothing}>{children}</p>;
}

function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <Card>
      <div className={styles.stack}>
        <div>
          <h2 className={styles.cardTitle}>{title}</h2>
          {note && <p className={styles.meta}>{note}</p>}
        </div>
        {children}
      </div>
    </Card>
  );
}

/** One output's decides in the window; nothing decided when it has none. */
function answersOf(stats: ModelStats, output: string): OutputAnswers {
  const found = (stats.answers ?? []).find((a) => (a.output ?? DEFAULT) === output);
  return found ?? { output, decided: 0, asked: 0, sure: Array<number>(10).fill(0), days: stats.days.map(() => ({ decided: 0, asked: 0 })) };
}

/** The outputs a model decides as its spec names them (the default one when it has one, or nothing else), then any that
 * answered under a name the spec no longer has. */
function outputNames(model: AdaModel, stats: ModelStats): string[] {
  const named = Object.keys(model.spec.outputs ?? {});
  const answered = (stats.answers ?? []).map((a) => a.output ?? DEFAULT);
  const spec = named.length && !model.spec.output && !answered.includes(DEFAULT) ? named : [DEFAULT, ...named];
  return [...spec, ...answered.filter((a) => !spec.includes(a))];
}

const outputText = (name: string) => (name === DEFAULT ? 'The outcome' : name);
const pct = (p: number) => `${Math.round(100 * p)}%`;

/** When an output asks a person, from its spec: by cost (ask), by confidence (ask_below), both, or only with nothing to go on. */
function askNote(output: SpecOutput | undefined): string {
  const cost = output?.ask;
  const bar = output?.ask_below;
  const lead = 'The share of a day’s decides that asked a person';
  if (cost !== undefined && bar !== undefined) return `${lead}: every outcome’s expected cost was above ${cost}, or the top probability under ${pct(bar)}.`;
  if (cost !== undefined) return `${lead}: every outcome’s expected cost was above ${cost}.`;
  if (bar !== undefined) return `${lead}: the top probability was under ${pct(bar)}.`;
  return `${lead}. This output sets neither ask nor ask_below, so it asks only when it has nothing to go on.`;
}

/** Reads a day, decides apart from the other reads (query, probabilities, facts). */
function ReadsChart({ stats }: { stats: ModelStats }) {
  const ink = useInk();
  const { labels, series, total } = useMemo(() => {
    const decides = stats.days.map((d) => d.reads.decide);
    const others = stats.days.map((d) => d.reads.query + d.reads.probabilities + d.reads.facts);
    const series: Series[] = [
      { label: 'Decide', data: decides, color: ink.series[0] },
      { label: 'Other reads', data: others, color: ink.series[2] },
    ];
    return { labels: stats.days.map((d) => dayText(d.day)), series, total: decides.concat(others).reduce((a, b) => a + b, 0) };
  }, [stats.days, ink]);
  if (!total) return <Nothing>No reads in these days yet. Decides and other reads show here as they are made.</Nothing>;
  return <Chart kind="bar" stacked label="Reads a day: decides and other reads" labels={labels} series={series} />;
}

/** The share of a day's decides that asked a person. */
function AskedChart({ stats, answers }: { stats: ModelStats; answers: OutputAnswers }) {
  const ink = useInk();
  const { labels, series } = useMemo(
    () => ({
      labels: stats.days.map((d) => dayText(d.day)),
      series: [{ label: 'Asked a person', data: answers.days.map((d) => (d.decided ? d.asked / d.decided : null)), color: ink.series[1] }],
    }),
    [stats.days, answers, ink],
  );
  if (!answers.decided) return <Nothing>No decides in these days yet.</Nothing>;
  return <Chart kind="line" percent label="Share of decides that asked a person, a day" labels={labels} series={series} />;
}

/** How sure the window's decides were: the decided outcome's probability, in tenths. */
function SureChart({ answers }: { answers: OutputAnswers }) {
  const ink = useInk();
  const { labels, series } = useMemo(
    () => ({
      labels: answers.sure.map((_, i) => `${i * 10}–${i * 10 + 10}%`),
      series: [{ label: 'Decides', data: answers.sure, color: ink.accent }],
    }),
    [answers.sure, ink],
  );
  if (!answers.sure.some(Boolean)) return <Nothing>No decides in these days yet.</Nothing>;
  return <Chart kind="bar" label="Decides by how sure they were" labels={labels} series={series} />;
}

/** The precedents held, by the day of each case, added up. */
function GrowthChart({ stats }: { stats: ModelStats }) {
  const ink = useInk();
  const { labels, series } = useMemo(() => {
    let held = 0;
    const totals = stats.growth.map((g) => (held += g.n));
    return { labels: stats.growth.map((g) => date(`${g.day}T00:00:00Z`)), series: [{ label: 'Precedents', data: totals, color: ink.accent }] };
  }, [stats.growth, ink]);
  if (!stats.growth.length) return <Nothing>No precedents yet. Import or record cases and they show here.</Nothing>;
  return <Chart kind="line" label="Precedents over time, by each case’s date" labels={labels} series={series} />;
}

/** Precedents by outcome, a chart for each output: its most common outcomes, the rest as one bar; ungraded ones apart. */
function OutcomesCharts({ stats }: { stats: ModelStats }) {
  const ink = useInk();
  const outputs = useMemo(() => {
    const byOutput = new Map<string, Array<{ value: string; n: number }>>();
    for (const row of stats.outcomes) {
      const name = row.output ?? '';
      if (!byOutput.has(name)) byOutput.set(name, []);
      byOutput.get(name)!.push({ value: row.value ?? 'Ungraded', n: row.n });
    }
    const other = new Map((stats.others ?? []).map((o) => [o.output ?? '', o]));
    return [...byOutput]
      .filter(([name, rows]) => name || rows.some((r) => r.value !== 'Ungraded'))
      .map(([name, rows]): [string, Array<{ value: string; n: number }>] => {
        const shown = rows.slice(0, OUTCOMES_SHOWN);
        const rest = rows.slice(OUTCOMES_SHOWN);
        const values = rest.length + (other.get(name)?.values ?? 0);
        const count = rest.reduce((sum, r) => sum + r.n, 0) + (other.get(name)?.n ?? 0);
        return [name, values ? [...shown, { value: `Other (${plural(values, 'outcome')})`, n: count }] : shown];
      });
  }, [stats.outcomes, stats.others]);
  if (!stats.precedents) return <Nothing>No precedents yet.</Nothing>;
  if (!outputs.length) return <Nothing>No precedent has an outcome yet.</Nothing>;
  return (
    <>
      {outputs.map(([name, rows]) => (
        <div key={name}>
          {outputs.length > 1 && <h3 className={styles.label}>{name || 'Outcome'}</h3>}
          <Chart
            kind="bar"
            across
            label={`Precedents by ${name || 'outcome'}`}
            labels={rows.map((r) => r.value)}
            series={[{ label: 'Precedents', data: rows.map((r) => r.n), color: ink.accent }]}
            height={Math.max(120, 28 * rows.length + 40)}
          />
        </div>
      ))}
    </>
  );
}

function JobsTable({ jobs }: { jobs: AdaJob[] }) {
  if (!jobs.length) return <Nothing>No imports, learns or backtests yet.</Nothing>;
  return (
    <div className={styles.tableBox}>
      <table className={styles.table} aria-label="Latest jobs">
        <thead>
          <tr>
            <th>Job</th>
            <th>State</th>
            <th>Started</th>
            <th>By</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{kindText[job.kind] ?? job.kind}</td>
              <td>
                <Chip tone={stateTone[job.state] ?? 'neutral'} dot={job.state === 'running'}>
                  {stateText[job.state] ?? job.state}
                  {job.state === 'running' && job.percent !== null ? ` · ${Math.round(job.percent)}%` : ''}
                </Chip>
              </td>
              <td className={styles.num}>{ago(job.created_at)}</td>
              <td className={styles.mono}>{job.made_by}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** How a model's decides answered, one output at a time when it has several: how many asked a person, and how sure. */
function Answers({ model, stats, window }: { model: AdaModel; stats: ModelStats; window: string }) {
  const names = outputNames(model, stats);
  const [picked, setPicked] = useState('');
  const output = names.includes(picked) ? picked : (names[0] ?? DEFAULT);
  const answers = answersOf(stats, output);
  const pick =
    names.length > 1 ? (
      <Select label="Output" value={output} onChange={(e) => setPicked(e.target.value)} options={names.map((o) => ({ value: o, label: outputText(o) }))} />
    ) : null;
  return (
    <>
      <Panel title="Asked a person" note={askNote(outputOf(model.spec, output))}>
        {pick}
        <AskedChart stats={stats} answers={answers} />
      </Panel>
      <Panel title="How sure" note={`The decided outcome’s probability, ${window}.`}>
        {names.length > 1 && <p className={styles.meta}>{outputText(output)}</p>}
        <SureChart answers={answers} />
      </Panel>
    </>
  );
}

/** The model's dashboard: its usage and health over the last 30 days, from what the server counted and holds. */
export function DashboardTab({ model }: { model: AdaModel }) {
  const stats = useAdaStats(model.name);
  if (stats.isPending) return <LoadingCard lines={4} />;
  if (!stats.data) return <AdaErrorNotice error={stats.error} />;
  const s = stats.data;
  const reads = s.days.reduce((sum, d) => sum + d.reads.decide + d.reads.query + d.reads.probabilities + d.reads.facts, 0);
  const decided = s.days.reduce((sum, d) => sum + d.decided, 0);
  const asked = s.days.reduce((sum, d) => sum + d.asked, 0);
  const cap = s.plan.precedents;
  const window = `the last ${plural(s.days.length, 'day')}`;
  const sampled = (note: string) => (s.estimated ? `${note} ${SAMPLED}` : note);
  return (
    <div className={styles.stack}>
      <div className={styles.stats}>
        <Card>
          <div className={styles.stack}>
            <span className={styles.meta}>Precedents</span>
            <div className={styles.value}>
              <span className={usageStyles.used}>{n(s.precedents)}</span>
              <span className={styles.of}>in this model</span>
            </div>
            {cap.max !== null && <ProgressBar value={Math.min(cap.used, cap.max)} max={cap.max} label="Your org’s precedents" />}
            <span className={styles.meta}>
              {cap.max === null ? `${n(cap.used)} across your org’s models, no limit` : `${n(cap.used)} of ${n(cap.max)} across your org’s models on ${s.plan.plan}`}
            </span>
          </div>
        </Card>
        <Card>
          <div className={styles.stack}>
            <span className={styles.meta}>Reads, {window}</span>
            <span className={usageStyles.used}>{n(reads)}</span>
            <span className={styles.meta}>{decided ? `${n(decided)} decided` : 'No decides yet'}</span>
          </div>
        </Card>
        <Card>
          <div className={styles.stack}>
            <span className={styles.meta}>Asked a person, {window}</span>
            <span className={usageStyles.used}>{decided ? share(asked, decided) : '–'}</span>
            <span className={styles.meta}>{decided ? `${n(asked)} of ${plural(decided, 'decide')}` : 'Shows once decides are made'}</span>
          </div>
        </Card>
        <Card>
          <div className={styles.stack}>
            <span className={styles.meta}>Live version</span>
            <span className={usageStyles.used}>v{s.active.version}</span>
            <span className={styles.meta}>
              {s.active.note ? `${s.active.note} · ` : ''}
              {date(s.active.made_at)}
            </span>
          </div>
        </Card>
      </div>
      <div className={styles.charts}>
        <Panel title="Reads a day" note="Decides apart from the other reads (query, probabilities, facts). UTC days.">
          <ReadsChart stats={s} />
        </Panel>
        <Panel title="Precedents over time" note={sampled('Added up by each case’s date: its own, or when it was recorded.')}>
          <GrowthChart stats={s} />
        </Panel>
        <Answers model={model} stats={s} window={window} />
        <Panel title="Outcomes" note={sampled('The precedents this model holds, by outcome.')}>
          <OutcomesCharts stats={s} />
        </Panel>
        <Panel title="Latest jobs">
          <JobsTable jobs={s.jobs} />
        </Panel>
      </div>
    </div>
  );
}
