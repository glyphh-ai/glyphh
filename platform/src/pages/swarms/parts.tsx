import { Link } from 'react-router';
import type { BotRun } from '@/api/bots';
import { useAnswerSwarmRun, type ChangedFile, type SwarmRunStatus, type TurnStatus } from '@/api/swarms';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, stamp } from '@/lib/format';
import { Button, Chip, Icon, type ChipTone } from '@/ui';
import bs from '../bots/bots.module.css';
import styles from './swarms.module.css';

export const swarmPath = (slug: string) => `/swarms/${encodeURIComponent(slug)}`;
export const swarmRunPath = (slug: string, id: string) => `${swarmPath(slug)}?run=${encodeURIComponent(id)}`;

const turnTones: Record<TurnStatus, ChipTone> = {
  running: 'blue',
  open: 'amber',
  unchanged: 'neutral',
  merging: 'blue',
  merged: 'green',
  conflict: 'red',
  rejecting: 'blue',
  rejected: 'neutral',
  failed: 'red',
  cancelled: 'neutral',
};
const turnWords: Record<TurnStatus, string> = {
  running: 'Working',
  open: 'Waits for you',
  unchanged: 'No changes',
  merging: 'Merging',
  merged: 'Merged',
  conflict: 'Conflict',
  rejecting: 'Closing',
  rejected: 'Rejected',
  failed: 'Failed',
  cancelled: 'Cancelled',
};
export function TurnChip({ status }: { status: TurnStatus }) {
  return <Chip tone={turnTones[status]}>{turnWords[status]}</Chip>;
}

const runTones: Record<SwarmRunStatus, ChipTone> = { running: 'blue', needs_input: 'amber', done: 'green', failed: 'red' };
const runWords: Record<SwarmRunStatus, string> = { running: 'Running', needs_input: 'Needs you', done: 'Done', failed: 'Failed' };
export function SwarmRunChip({ status }: { status: SwarmRunStatus }) {
  return <Chip tone={runTones[status]}>{runWords[status]}</Chip>;
}

/** What a pull request changed, a line a file: its path, lines added and taken out. */
function Files({ files }: { files: ChangedFile[] }) {
  if (files.length === 0) return null;
  return (
    <ul className={styles.files} aria-label="Files changed">
      {files.map((f) => (
        <li key={f.path}>
          <span className={styles.code}>{f.path}</span>
          <span className={styles.added}>+{f.added ?? 0}</span>
          <span className={styles.removed}>−{f.removed ?? 0}</span>
        </li>
      ))}
    </ul>
  );
}

export type PullRequest = { pr_url: string | null; number: number | null; title: string; branch: string; files: ChangedFile[]; said: string };

/**
 * A turn's pull request: its number and title (a link to it on GitHub), its branch, the files it changed and what the
 * bot said; while the run waits on it, merged or rejected here.
 */
export function PullRequestCard({ pr, runId, waiting }: { pr: PullRequest; runId: string; waiting: boolean }) {
  const answer = useAnswerSwarmRun();
  const busy = answer.isPending;
  return (
    <section className={styles.pr} aria-label={`Pull request #${pr.number ?? ''}`}>
      <div className={`${bs.spread} ${styles.prHead}`}>
        {pr.pr_url ? (
          <a href={pr.pr_url} target="_blank" rel="noreferrer" className={styles.prTitle}>
            <Icon name="github" size={14} /> #{pr.number} {pr.title}
          </a>
        ) : (
          <span className={styles.prTitle}>{pr.title}</span>
        )}
        <span className={`${bs.muted} ${styles.code}`}>{pr.branch}</span>
      </div>
      <Files files={pr.files} />
      {pr.said && <p className={styles.said}>{pr.said}</p>}
      {waiting && (
        <>
          <div className={bs.row}>
            <Button variant="primary" icon="check" disabled={busy} loading={busy && answer.variables?.answer === 'merge'} onClick={() => answer.mutate({ id: runId, answer: 'merge' })}>
              Merge
            </Button>
            <Button variant="ghost" icon="close" disabled={busy} loading={busy && answer.variables?.answer === 'reject'} onClick={() => answer.mutate({ id: runId, answer: 'reject' })}>
              Reject
            </Button>
          </div>
          <ApiErrorNotice error={answer.error} />
        </>
      )}
    </section>
  );
}

const text = (v: unknown) => (typeof v === 'string' ? v : '');

/** A swarm's pull request as the approvals queue lists it: whose, which swarm and task, merged or rejected in place. */
export function SwarmWaiting({ run }: { run: BotRun }) {
  const d = run.data;
  const pr: PullRequest = {
    pr_url: text(d.pr_url) || null,
    number: typeof d.number === 'number' ? d.number : null,
    title: text(d.title),
    branch: text(d.branch),
    files: Array.isArray(d.files) ? (d.files as ChangedFile[]) : [],
    said: text(d.said),
  };
  const slug = run.swarm_slug ?? '';
  return (
    <article className={bs.waiting} aria-label={`${slug}: ${run.question?.question ?? 'waiting'}`}>
      <div className={bs.spread}>
        <span className={bs.row}>
          <Link to={swarmRunPath(slug, run.id)} className={bs.botLink}>
            {slug}
          </Link>
          <span className={bs.muted} title={stamp(run.created_at)}>
            Swarm · “{run.input}” · {ago(run.created_at)}
          </span>
        </span>
      </div>
      <p className={bs.questionText}>{run.question?.question}</p>
      <PullRequestCard pr={pr} runId={run.id} waiting />
    </article>
  );
}
