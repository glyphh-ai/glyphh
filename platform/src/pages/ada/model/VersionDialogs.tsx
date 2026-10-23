import { useState, type ReactNode } from 'react';
import {
  useActivate,
  useAdaReleases,
  useAdaVersion,
  usePutSpec,
  useVersionDiff,
  useVersionNote,
  type AdaModel,
  type AdaVersion,
  type SpecChange,
  type VersionChange,
} from '@/api/ada';
import { date, plural, stamp } from '@/lib/format';
import { isBeta } from '@/lib/releases';
import { specText } from '@/lib/spec';
import { autoSummary, changeText, learnedText } from '@/lib/versions';
import { Button, Chip, CodeBlock, Dialog, LoadingCard, TextField } from '@/ui';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { AdaName } from '../AdaRelease';
import { ChangeResult } from './ChangeResult';
import styles from '../ada.module.css';

const pct = (v: number | null | undefined) => (v === null || v === undefined ? null : `${(v * 100).toFixed(1)}%`);

/** Where a version's stored cases stand, in a sentence. */
export function storeText(version: AdaVersion): string {
  const { status, drop_after: after } = version.store;
  if (status === 'active') return version.active ? 'The live stored cases.' : 'It reads the live stored cases: making it live is at once.';
  if (status === 'dropped') return 'Its stored cases were dropped: it can’t be made live again.';
  if (status === 'making') return 'Its stored cases are being written (or a re-encode never finished: the next one drops them).';
  if (!after) return 'Its stored cases are kept apart, for a rollback.';
  if (new Date(after).getTime() <= Date.now()) return 'Its stored cases are kept apart; the next re-encode may drop them.';
  return `Its stored cases are kept apart until at least ${date(after)}; the next re-encode after that drops them.`;
}

function Changes({ changes, empty }: { changes: SpecChange[]; empty: string }) {
  if (changes.length === 0) return <p className={styles.meta}>{empty}</p>;
  return (
    <ul className={styles.changes}>
      {changes.map((change) => (
        <li key={change.path}>
          <span className={styles.mono}>{changeText(change)}</span>
          {change.restates && <Chip tone="amber">Rewrites the cases</Chip>}
        </li>
      ))}
    </ul>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

type ViewProps = { model: AdaModel; version: AdaVersion; by: string | null; onClose: () => void };

/** One version whole: who made it and when, the precedents then and now, its store, what it changed, what it learned, its newest backtest, its spec and settings. */
export function ViewDialog({ model, version, by, onClose }: ViewProps) {
  const detail = useAdaVersion(model.name, version.version);
  const releases = useAdaReleases();
  const learned = Object.entries(version.learned ?? {});
  const scores = version.scores;
  const restating = (version.changes ?? []).filter((c) => c.restates);
  return (
    <Dialog
      open
      size="wide"
      onClose={onClose}
      title={`Version ${version.version}${version.active ? ' (live)' : ''}`}
      description={version.note.trim() || autoSummary(version)}
      actions={
        <Button variant="primary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <dl className={styles.facts}>
        <Fact label="Made">
          {stamp(version.made_at)} UTC{by ? `, by ${by}` : ''}
        </Fact>
        <Fact label="Precedents">
          {version.precedents_at === null ? 'Not recorded when it was made' : `${version.precedents_at.toLocaleString('en-GB')} when it was made`}
          {` · ${model.precedents.toLocaleString('en-GB')} now`}
        </Fact>
        <Fact label="Ada">
          <span className={styles.chips}>
            <AdaName name={version.ada} beta={isBeta(releases.data, version.ada)} />
            <span className={styles.meta}>kernel {version.kernel}</span>
          </span>
        </Fact>
        <Fact label="Stored cases">{storeText(version)}</Fact>
        {version.new_store && (
          <Fact label="Re-encoded">
            Its cases were rewritten into a store of its own, for: {restating.map(changeText).join('; ') || 'a change of what a case carries'}.
          </Fact>
        )}
        <Fact label="Learned">
          {learned.length === 0
            ? 'Nothing learned yet'
            : learned.map(([output, entry]) => (
                <span key={output} className={styles.line}>
                  {learned.length > 1 || output !== 'default' ? `${output}: ` : ''}
                  {learnedText(entry)}
                </span>
              ))}
        </Fact>
        <Fact label="Backtest">
          {scores
            ? [
                `Accuracy ${pct(scores.accuracy) ?? '—'}`,
                scores.log_loss !== undefined && `log-loss ${scores.log_loss.toFixed(3)}`,
                scores.ask_rate !== undefined && `asks ${pct(scores.ask_rate)}`,
                scores.cost_mean !== undefined && `mean cost ${scores.cost_mean.toFixed(3)}`,
                scores.n !== undefined && `on ${plural(scores.n, 'held-out case')}`,
                scores.output && scores.output !== 'default' && `output ${scores.output}`,
                scores.at && date(scores.at),
              ]
                .filter(Boolean)
                .join(' · ')
            : 'Not backtested'}
        </Fact>
      </dl>
      <h3 className={styles.groupTitle}>{version.changes === null ? 'Changes' : `Changes from version ${version.version - 1}`}</h3>
      <Changes changes={version.changes ?? []} empty={version.changes === null ? 'The first version.' : 'No change to the spec or settings.'} />
      {detail.isPending && <LoadingCard lines={4} />}
      <AdaErrorNotice error={detail.error} />
      {detail.data && (
        <>
          <h3 className={styles.groupTitle}>Spec</h3>
          <CodeBlock code={specText(detail.data.spec)} label={`version ${version.version}’s spec`} />
          <h3 className={styles.groupTitle}>Settings</h3>
          <CodeBlock code={JSON.stringify(detail.data.settings, null, 2)} label={`version ${version.version}’s settings`} />
        </>
      )}
    </Dialog>
  );
}

type LiveProps = { model: AdaModel; version: AdaVersion; live: number; onClose: () => void; onLive: (change: VersionChange) => void };

/**
 * Making a version live again (a rollback), asked first: its spec, settings and learned weights become live; the
 * cases recorded since stay. A version whose stored cases are kept apart is brought up to date by a job first, shown
 * here as it runs. One whose stored cases were dropped can't be: its spec can be saved as a new version instead.
 */
export function MakeLiveDialog({ model, version, live, onClose, onLive }: LiveProps) {
  const activate = useActivate(model.name);
  const [running, setRunning] = useState<VersionChange | null>(null);
  if (version.store.status === 'dropped') return <DroppedDialog model={model} version={version} onClose={onClose} />;
  const apart = version.store.status === 'kept';
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Make version ${version.version} live?`}
      description={
        <>
          <p>
            Version {version.version}’s spec, settings and learned weights become live, in place of version {live}.
          </p>
          <p>Precedents recorded since stay in the model: cases are not versioned.</p>
          {version.ada !== model.ada && (
            <p>
              It answers on {version.ada}, the Ada it was made with, in place of {model.ada}.
            </p>
          )}
          {apart && <p>Its cases are stored apart, so a job first brings them up to date with every write made since. Version {live} answers until it is done.</p>}
        </>
      }
      actions={
        running ? (
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={activate.isPending}
              onClick={() => activate.mutate(version.version, { onSuccess: (made) => (made.job ? setRunning(made) : onLive(made)) })}
            >
              Make live
            </Button>
          </>
        )
      }
    >
      <AdaErrorNotice error={activate.error} />
      {running && <ChangeResult model={model.name} change={running} />}
    </Dialog>
  );
}

function DroppedDialog({ model, version, onClose }: { model: AdaModel; version: AdaVersion; onClose: () => void }) {
  const detail = useAdaVersion(model.name, version.version);
  const put = usePutSpec(model.name);
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Version ${version.version} can’t be made live`}
      description={
        <>
          <p>Its stored cases were dropped after 7 days unused, and the weights it had learned with them.</p>
          <p>
            You can save its spec and settings as a new version instead: the model’s cases are rewritten for it if they need to be, and it learns
            again from them.
          </p>
        </>
      }
      actions={
        put.data ? (
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={put.isPending}
              disabled={!detail.data}
              onClick={() => put.mutate({ spec: detail.data!.spec, note: `From version ${version.version}` })}
            >
              Save as a new version
            </Button>
          </>
        )
      }
    >
      <AdaErrorNotice error={detail.error ?? put.error} />
      {put.data && <ChangeResult model={model.name} change={put.data} />}
    </Dialog>
  );
}

/** A version's release notes, written again; left empty, the table shows what it changed. */
export function NoteDialog({ model, version, onClose }: { model: AdaModel; version: AdaVersion; onClose: () => void }) {
  const save = useVersionNote(model.name);
  const [note, setNote] = useState(version.note);
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Version ${version.version}’s notes`}
      description="What this version is for. Left empty, the list shows what it changed."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={save.isPending} onClick={() => save.mutate({ version: version.version, note: note.trim() }, { onSuccess: onClose })}>
            Save
          </Button>
        </>
      }
    >
      <TextField label="Release notes" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={autoSummary(version)} autoFocus />
      <AdaErrorNotice error={save.error} />
    </Dialog>
  );
}

/** What making a version live would change from the live one. */
export function CompareDialog({ model, version, live, onClose }: { model: AdaModel; version: AdaVersion; live: number; onClose: () => void }) {
  const diff = useVersionDiff(model.name, version.version);
  return (
    <Dialog
      open
      size="wide"
      onClose={onClose}
      title={`Version ${version.version} against live version ${live}`}
      description={`What making version ${version.version} live would change.`}
      actions={
        <Button variant="primary" onClick={onClose}>
          Close
        </Button>
      }
    >
      {diff.isPending && <LoadingCard lines={3} />}
      <AdaErrorNotice error={diff.error} />
      {diff.data && <Changes changes={diff.data.changes} empty="The same spec and settings as the live version." />}
    </Dialog>
  );
}
