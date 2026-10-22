import { useEffect, useRef, type ReactNode } from 'react';
import { useAdaJob, type AdaJob } from '@/api/ada';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ErrorNotice, ProgressBar } from '@/ui';
import styles from './ada.module.css';

const stateText: Record<string, string> = {
  awaiting: 'Waiting for the file',
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
};

/**
 * A job as it goes: its state and percent, read every second until it ends; then `onDone` once with the job, and
 * `children` with it (what it made), or the job's own error.
 */
export function JobProgress({ id, label, onDone, children }: { id: string; label: string; onDone?: (job: AdaJob) => void; children?: (job: AdaJob) => ReactNode }) {
  const job = useAdaJob(id);
  const told = useRef(false);
  const data = job.data;

  useEffect(() => {
    if (data?.state === 'done' && !told.current) {
      told.current = true;
      onDone?.(data);
    }
  }, [data, onDone]);

  if (job.error) return <ApiErrorNotice error={job.error} />;
  if (!data) return <p className={styles.meta}>{label}…</p>;
  if (data.state === 'failed') return <ErrorNotice message={data.error?.message ?? 'The job failed.'} />;
  if (data.state === 'done') return <>{children?.(data)}</>;
  const percent = data.percent ?? 0;
  return (
    <div className={styles.form} role="status">
      <div className={styles.leverHead}>
        <span>{label}</span>
        <span className={styles.meta}>
          {stateText[data.state] ?? data.state} · {Math.round(percent)}%
        </span>
      </div>
      <ProgressBar value={percent} max={100} label={label} />
    </div>
  );
}
