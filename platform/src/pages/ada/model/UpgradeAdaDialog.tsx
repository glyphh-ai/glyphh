import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { adaFix, useAdaReleases, useStartBacktest, useUpgradeAda, type AdaModel, type AdaReleases, type BacktestResult } from '@/api/ada';
import { defaultTarget, notesPath, optionText, releaseOf, targetsFor } from '@/lib/releases';
import { Button, Dialog, LoadingCard, Select, TextField } from '@/ui';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { JobProgress } from '../JobProgress';
import { ScoresTable } from './BacktestTab';
import { ChangeResult } from './ChangeResult';
import styles from '../ada.module.css';

const pct = (v: number | undefined) => (v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);

/** What a chosen version is beside the one the model runs: a beta, older (a downgrade), answer-changing. */
function aboutTarget(releases: AdaReleases, target: string, current: string): string {
  const all = releases.versions;
  const at = all.findIndex((r) => r.name === target);
  const now = all.findIndex((r) => r.name === (releaseOf(releases, current)?.name ?? current));
  const release = all[at]!;
  const parts: string[] = [];
  if (release.beta) parts.push('A beta: never the default, chosen only by name.');
  if (now !== -1 && at > now) parts.push(`Older than ${current}: a downgrade.`);
  const changes = all.slice(Math.min(at, now === -1 ? at : now), Math.max(at, now === -1 ? at : now)).some((r) => r.changes_answers);
  parts.push(changes ? `It can answer differently from ${current}: backtest it on your cases first.` : `It answers as ${current} does.`);
  return parts.join(' ');
}

/** The backtest in a line: the target's accuracy against the live version's. */
function verdict(result: BacktestResult, current: string, target: string): string {
  const candidate = result.candidates[0];
  if (!candidate) return '';
  if (candidate.error) return `${target} could not be scored: ${candidate.error.message}`;
  return `On your newest ${result.held_out.toLocaleString('en-GB')} cases, ${candidate.ada ?? target} was right ${pct(candidate.accuracy)} of the time, against ${pct(result.active.accuracy)} on ${result.active.ada ?? current}.`;
}

type Props = { model: AdaModel; live: number; current: string; initial: string; onClose: () => void };

/**
 * Moving a model to another Ada: choose the version (the latest stable first; betas labelled; older ones allowed,
 * never a deprecated or retired one), backtest the live spec on it against the live version, see the change, then
 * upgrade: a new version re-encoded on it, live once its job is done. The way back is the version before, made live.
 */
export function UpgradeAdaDialog({ model, live: liveNow, current: currentNow, initial, onClose }: Props) {
  // Where the model stood when the dialog opened: once an upgrade is live, the way back is still to that version.
  const [{ live, current }] = useState({ live: liveNow, current: currentNow });
  const releases = useAdaReleases();
  const start = useStartBacktest(model.name);
  const upgrade = useUpgradeAda(model.name);
  const [picked, setPicked] = useState(initial);
  const [newest, setNewest] = useState('200');
  const [job, setJob] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const targets = releases.data ? targetsFor(releases.data, current) : [];
  const target = targets.some((t) => t.name === picked) ? picked : releases.data ? defaultTarget(releases.data, current) : '';
  const release = releases.data && releaseOf(releases.data, target);

  const choose = (name: string) => {
    setPicked(name);
    setJob(null);
    start.reset();
    upgrade.reset();
  };

  const backtest = (event: FormEvent) => {
    event.preventDefault();
    const held = Number(newest);
    if (!Number.isInteger(held) || held < 1) return setProblem('Hold out a whole number of cases, 1 or more.');
    setProblem(null);
    start.mutate({ ada: target, holdout: { newest: held } }, { onSuccess: (made) => setJob(made.id) });
  };

  const error = upgrade.error ?? start.error;
  const latest = adaFix(error);
  const fix = latest && latest !== target && targets.some((t) => t.name === latest) && (
    <Button size="sm" onClick={() => choose(latest)}>
      Choose {latest}
    </Button>
  );

  const done = Boolean(upgrade.data);
  return (
    <Dialog
      open
      size="wide"
      onClose={onClose}
      title="Upgrade Ada"
      description={`${model.name} runs on ${current}. Choose a version, backtest it on your cases, then upgrade.`}
      actions={
        done ? (
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            {target && (
              <Button
                variant={job ? 'primary' : 'secondary'}
                loading={upgrade.isPending}
                onClick={() => upgrade.mutate({ ada: target, ...(job ? { backtest: job } : {}) })}
              >
                Upgrade to {target}
              </Button>
            )}
          </>
        )
      }
    >
      {releases.isPending && <LoadingCard lines={3} />}
      <AdaErrorNotice error={releases.error} />
      {releases.data && targets.length === 0 && <p className={styles.about}>There is no other Ada version to move to.</p>}
      {releases.data && release && (
        <div className={styles.form}>
          <Select label="Move to" value={target} disabled={done || upgrade.isPending} onChange={(e) => choose(e.target.value)} options={targets.map((r) => ({ value: r.name, label: optionText(r, releases.data) }))} />
          <p className={styles.summary}>{release.summary}</p>
          <p className={styles.about}>
            {aboutTarget(releases.data, target, current)} <Link to={notesPath(target)}>Read its release notes</Link>
          </p>

          <h3 className={styles.label}>1. Backtest</h3>
          <form className={styles.row} onSubmit={backtest}>
            <TextField label="Hold out the newest" type="number" min={1} value={newest} onChange={(e) => setNewest(e.target.value)} hint="Graded cases" />
            <Button type="submit" variant={job ? 'secondary' : 'primary'} loading={start.isPending} disabled={done}>
              Backtest against {target}
            </Button>
          </form>
          {problem && (
            <p className={styles.about} role="alert">
              {problem}
            </p>
          )}
          {job && (
            <JobProgress key={job} id={job} label={`Backtesting ${target}`}>
              {(finished) => {
                const result = finished.result as unknown as BacktestResult;
                return (
                  <>
                    <p className={styles.about}>{verdict(result, current, target)}</p>
                    <ScoresTable result={result} />
                  </>
                );
              }}
            </JobProgress>
          )}

          <h3 className={styles.label}>2. Upgrade</h3>
          <p className={styles.about}>
            Upgrading makes a new version: the live spec and settings on {target}, its cases re-encoded and learned again with it. Version {live}{' '}
            answers until it is done.
          </p>
          <p className={styles.about}>
            To go back, make version {live} live again from this tab: it runs on {current}, as it does now.
          </p>
          <AdaErrorNotice error={error} action={fix || undefined} />
          {upgrade.data && <ChangeResult model={model.name} change={upgrade.data} />}
        </div>
      )}
    </Dialog>
  );
}
