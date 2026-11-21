import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { modelReads, type VersionChange } from '@/api/ada';
import { JobProgress } from '../JobProgress';
import styles from '../ada.module.css';

const jobText: Record<string, string> = {
  reencode: 'Rewriting the cases for version',
  calibrate: 'Calibrating version',
};

/** What a new version or a rollback did: live at once, or a job (a re-encode or a calibration) to wait for. */
export function ChangeResult({ model, change }: { model: string; change: VersionChange }) {
  const client = useQueryClient();
  const refresh = useCallback(() => {
    for (const queryKey of modelReads(model)) void client.invalidateQueries({ queryKey });
  }, [client, model]);

  if (!change.job) return <p className={styles.good} role="status">Version {change.version} is live.</p>;
  const label = `${jobText[change.job.kind] ?? 'Making version'} ${change.version}`;
  return (
    <JobProgress id={change.job.id} label={label} onDone={refresh}>
      {() => (
        <p className={styles.good} role="status">
          Version {change.version} is live.
        </p>
      )}
    </JobProgress>
  );
}
