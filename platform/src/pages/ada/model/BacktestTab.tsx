import { useState, type FormEvent } from 'react';
import {
  useActivate,
  useAdaLevers,
  useAdaVersions,
  usePatchSettings,
  useStartBacktest,
  type AdaModel,
  type BacktestResult,
  type Candidate,
  type LeverValue,
  type Scores,
  type VersionChange,
} from '@/api/ada';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { changesText, leverFromText, leverProblem, levers as known, outputsOf } from '@/lib/spec';
import { Button, Card, Chip, LoadingCard, Select, TextField } from '@/ui';
import { JobProgress } from '../JobProgress';
import { ChangeResult } from './ChangeResult';
import { draftOf, leverFor, LeverInput, type Draft } from './LeverInput';
import styles from '../ada.module.css';

/** A candidate as it is made: settings changed on the live version, or another version. */
type Draftable = { kind: 'settings'; levers: Array<{ name: string; value: Draft }> } | { kind: 'version'; version: string };

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);
const num = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v.toFixed(3));
const points = (v: number | undefined) => (v === undefined ? null : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)} pts`);
const by = (v: number | undefined) => (v === undefined ? null : `${v > 0 ? '+' : ''}${v.toFixed(3)}`);

function candidateOf(draft: Draftable, live: Record<string, LeverValue>): Candidate | string {
  if (draft.kind === 'version') return draft.version ? { spec_version: Number(draft.version) } : 'Pick a version.';
  const settings: Record<string, LeverValue> = {};
  for (const { name, value } of draft.levers) {
    const lever = leverFor(name, live[name] ?? null);
    const parsed = typeof value === 'boolean' ? value : leverFromText(lever, value);
    const problem = typeof parsed === 'number' && Number.isNaN(parsed) ? 'A number.' : leverProblem(name, parsed);
    if (problem) return `${lever.label}: ${problem}`;
    settings[name] = parsed;
  }
  return Object.keys(settings).length ? { settings } : 'Add a lever to change.';
}

/** What a candidate is, in words. */
export function candidateText(candidate: Candidate): string {
  if (candidate.spec_version !== undefined) return `Version ${candidate.spec_version}`;
  if (candidate.settings && Object.keys(candidate.settings).length) return changesText(candidate.settings);
  return candidate.name ?? 'Candidate';
}

/** The best candidate: the least mean cost when the output prices mistakes, else the most accurate; only if it beats the live one. */
export function winnerOf(result: BacktestResult): number | null {
  const priced = result.active.cost_mean !== undefined;
  const score = (s: Scores) => (priced ? -(s.cost_mean ?? Infinity) : (s.accuracy ?? -Infinity));
  let best: number | null = null;
  result.candidates.forEach((c, i) => {
    if (c.error) return;
    if (score(c) > score(best === null ? result.active : result.candidates[best]!)) best = i;
  });
  return best;
}

/**
 * Backtest: the live version and candidates scored on the model's own newest graded cases, held out of what each
 * learns from; the live model is not touched. The winner can then be made live.
 */
export function BacktestTab({ model }: { model: AdaModel }) {
  const levers = useAdaLevers(model.name);
  const versions = useAdaVersions(model.name);
  const start = useStartBacktest(model.name);
  const [drafts, setDrafts] = useState<Draftable[]>([{ kind: 'settings', levers: [] }]);
  const [newest, setNewest] = useState('200');
  const [output, setOutput] = useState('default');
  const [job, setJob] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const outputs = outputsOf(model.spec);

  if (levers.isPending || versions.isPending) return <LoadingCard lines={4} />;
  if (levers.error || versions.error) return <ApiErrorNotice error={levers.error ?? versions.error} />;
  const live = levers.data.settings;
  const others = versions.data.filter((v) => !v.active && v.ready && !v.gone);

  const update = (i: number, next: Draftable) => setDrafts((all) => all.map((d, j) => (j === i ? next : d)));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const candidates: Candidate[] = [];
    for (const draft of drafts) {
      const made = candidateOf(draft, live);
      if (typeof made === 'string') return setProblem(made);
      candidates.push(made);
    }
    const held = Number(newest);
    if (!Number.isInteger(held) || held < 1) return setProblem('Hold out a whole number of cases, 1 or more.');
    setProblem(null);
    start.mutate({ candidates, holdout: { newest: held }, ...(output === 'default' ? {} : { output }) }, { onSuccess: (made) => setJob(made.id) });
  };

  return (
    <>
      <Card>
        <form className={styles.form} onSubmit={submit}>
          <p className={styles.about}>
            Score changes before they go live: each candidate learns from your cases but the newest, then decides those. The live model is not
            touched.
          </p>
          <div className={styles.row}>
            <TextField label="Hold out the newest" type="number" min={1} value={newest} onChange={(e) => setNewest(e.target.value)} hint="Graded cases" />
            {outputs.length > 1 && (
              <Select label="Output" value={output} onChange={(e) => setOutput(e.target.value)} options={outputs.map((o) => ({ value: o, label: o === 'default' ? 'The outcome' : o }))} />
            )}
          </div>
          {drafts.map((draft, i) => (
            <CandidateEditor
              key={i}
              index={i}
              draft={draft}
              live={live}
              versions={others.map((v) => v.version)}
              onChange={(next) => update(i, next)}
              onRemove={() => setDrafts((all) => all.filter((_, j) => j !== i))}
            />
          ))}
          {problem && <p className={styles.about} role="alert">{problem}</p>}
          <ApiErrorNotice error={start.error} />
          <div className={styles.actions}>
            <Button icon="plus" disabled={drafts.length >= 10} onClick={() => setDrafts((all) => [...all, { kind: 'settings', levers: [] }])}>
              Add a candidate
            </Button>
            <Button variant="primary" type="submit" loading={start.isPending}>
              Run backtest
            </Button>
          </div>
        </form>
      </Card>
      {job && (
        <Card>
          <JobProgress key={job} id={job} label="Backtesting">
            {(done) => <Results model={model} job={done.id} result={done.result as unknown as BacktestResult} />}
          </JobProgress>
        </Card>
      )}
    </>
  );
}

type EditorProps = {
  index: number;
  draft: Draftable;
  live: Record<string, LeverValue>;
  versions: number[];
  onChange: (draft: Draftable) => void;
  onRemove: () => void;
};

function CandidateEditor({ index, draft, live, versions, onChange, onRemove }: EditorProps) {
  const unused = known.filter((lever) => lever.name in live && (draft.kind !== 'settings' || !draft.levers.some((l) => l.name === lever.name)));
  return (
    <div className={styles.candidate} aria-label={`Candidate ${index + 1}`} role="group">
      <div className={styles.candidateHead}>
        <strong>Candidate {index + 1}</strong>
        <Button size="sm" variant="ghost" icon="trash" onClick={onRemove}>
          Remove
        </Button>
      </div>
      <Select
        label="Try"
        value={draft.kind}
        onChange={(e) => onChange(e.target.value === 'version' ? { kind: 'version', version: String(versions[0] ?? '') } : { kind: 'settings', levers: [] })}
        options={[
          { value: 'settings', label: 'The live version with settings changed' },
          ...(versions.length ? [{ value: 'version', label: 'Another version' }] : []),
        ]}
      />
      {draft.kind === 'version' && (
        <Select label="Version" value={draft.version} onChange={(e) => onChange({ kind: 'version', version: e.target.value })} options={versions.map((v) => ({ value: String(v), label: `Version ${v}` }))} />
      )}
      {draft.kind === 'settings' && (
        <>
          {draft.levers.map(({ name, value }) => {
            const lever = leverFor(name, live[name] ?? null);
            return (
              <div key={name} className={styles.leverHead}>
                <LeverInput lever={lever} value={value} onChange={(next) => onChange({ kind: 'settings', levers: draft.levers.map((l) => (l.name === name ? { name, value: next } : l)) })} />
                {lever.kind === 'bool' && <span>{lever.label}</span>}
                <Button size="sm" variant="ghost" onClick={() => onChange({ kind: 'settings', levers: draft.levers.filter((l) => l.name !== name) })}>
                  Remove {lever.label}
                </Button>
              </div>
            );
          })}
          {unused.length > 0 && (
            <Select
              label="Change a lever"
              value=""
              onChange={(e) => {
                const name = e.target.value;
                if (name) onChange({ kind: 'settings', levers: [...draft.levers, { name, value: draftOf(live[name] ?? null) }] });
              }}
              options={[{ value: '', label: 'Choose a lever' }, ...unused.map((l) => ({ value: l.name, label: `${l.label} (now ${String(live[l.name] ?? 'none')})` }))]}
            />
          )}
        </>
      )}
    </div>
  );
}

const columns: Array<{ key: keyof Scores; label: string; show: (v: number | undefined | null) => string; change: (v: number | undefined) => string | null }> = [
  { key: 'accuracy', label: 'Accuracy', show: pct, change: points },
  { key: 'top_accuracy', label: 'Vote accuracy', show: pct, change: points },
  { key: 'ask_rate', label: 'Asks', show: pct, change: points },
  { key: 'accuracy_answered', label: 'Right when it decides', show: pct, change: () => null },
  { key: 'log_loss', label: 'Log-loss', show: num, change: by },
  { key: 'calibration_error', label: 'Calibration error', show: num, change: by },
];

/** Each candidate's numbers beside the live version's, with the change; the winner marked, and made live from here. */
function Results({ model, job, result }: { model: AdaModel; job: string; result: BacktestResult }) {
  const patch = usePatchSettings(model.name);
  const activate = useActivate(model.name);
  const [change, setChange] = useState<VersionChange | null>(null);
  const priced = result.active.cost_mean !== undefined;
  const shown = priced ? [...columns, { key: 'cost_mean' as const, label: 'Mean cost', show: num, change: by }] : columns;
  const winner = winnerOf(result);

  const makeLive = (candidate: Candidate) => {
    if (candidate.spec_version !== undefined) activate.mutate(candidate.spec_version, { onSuccess: setChange });
    else patch.mutate({ changes: candidate.settings ?? {}, note: `Backtest: ${candidateText(candidate)}`, backtest: job }, { onSuccess: setChange });
  };

  const rows: Array<{ name: string; scores: Scores; index: number | null }> = [
    { name: `Live, version ${result.version}`, scores: result.active, index: null },
    ...result.candidates.map((scores, i) => ({ name: candidateText(scores.candidate), scores, index: i })),
  ];

  return (
    <div className={styles.form}>
      <p className={styles.meta}>
        Learned from {result.trained.toLocaleString('en-GB')} cases, scored on the newest {result.held_out.toLocaleString('en-GB')}.
      </p>
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Backtest results">
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              {shown.map((c) => (
                <th key={c.key} scope="col">
                  {c.label}
                </th>
              ))}
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ name, scores, index }) => (
              <tr key={index ?? 'live'}>
                <td>
                  <div className={styles.chips}>
                    <span>{name}</span>
                    {index !== null && index === winner && <Chip tone="green">Best</Chip>}
                  </div>
                  {scores.error && <span className={styles.change}>{scores.error.message}</span>}
                  {typeof scores.learn === 'string' && <span className={styles.change}>Not learned: {scores.learn}</span>}
                </td>
                {shown.map((c) => (
                  <td key={c.key} className={styles.num}>
                    {scores.error ? '—' : c.show(scores[c.key] as number | undefined)}
                    {index !== null && c.change(scores.change?.[c.key]) && <span className={styles.change}>{c.change(scores.change?.[c.key])}</span>}
                  </td>
                ))}
                <td>
                  {index !== null && !scores.error && (
                    <Button size="sm" variant={index === winner ? 'primary' : 'secondary'} loading={patch.isPending || activate.isPending} onClick={() => makeLive(scores.candidate)}>
                      Make live
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ApiErrorNotice error={patch.error ?? activate.error} />
      {change && <ChangeResult model={model.name} change={change} />}
    </div>
  );
}
