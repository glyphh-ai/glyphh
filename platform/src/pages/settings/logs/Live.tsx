import type { ReactNode } from 'react';
import { ApiError } from '@/api/client';
import { liveEvery } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Chip, ErrorNotice } from '@/ui';
import styles from './Logs.module.css';

/** That the list is read again on its own while the page is open. */
export function Live({ children = 'Newest first' }: { children?: string }) {
  return (
    <p className={styles.live}>
      <Chip tone="green" dot>
        Live
      </Chip>
      {children}, read again every {liveEvery / 1000} seconds. Times in UTC.
    </p>
  );
}

/** The next page back, by the server's cursor. */
export function Older({ more, loading, onMore }: { more: boolean; loading: boolean; onMore: () => void }) {
  if (!more) return null;
  return (
    <div className={styles.older}>
      <Button onClick={onMore} loading={loading}>
        Load older
      </Button>
    </div>
  );
}

/** Anything else the server sent with a line or an event, shown as it came. */
export function Details({ fields }: { fields: Record<string, unknown> }): ReactNode {
  if (Object.keys(fields).length === 0) return null;
  return (
    <details className={styles.details}>
      <summary>Details</summary>
      <pre className={styles.pre}>{JSON.stringify(fields, null, 2)}</pre>
    </details>
  );
}

/**
 * A refusal of a read. One of a cursor (422 `reason: cursor`, a cursor no page gave) is the paging gone stale: start
 * again from the newest.
 */
export function ReadError({ error, onRestart }: { error: unknown; onRestart: () => void }) {
  if (error instanceof ApiError && error.detail.reason === 'cursor') {
    return (
      <ErrorNotice
        message="The older pages could not be found. Start again from the newest."
        traceId={error.traceId}
        action={
          <Button size="sm" onClick={onRestart}>
            Start again
          </Button>
        }
      />
    );
  }
  return <ApiErrorNotice error={error} />;
}
