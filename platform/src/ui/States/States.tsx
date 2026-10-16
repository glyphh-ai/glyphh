import type { ReactNode } from 'react';
import { Icon, type IconName } from '../Icon/Icon';
import styles from './States.module.css';

/** Nothing here yet: what goes here, and the action that adds the first one. */
export function EmptyState({ icon, title, children, action }: { icon: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <span className={styles.emptyIcon}>
        <Icon name={icon} size={20} />
      </span>
      <h3 className={styles.emptyTitle}>{title}</h3>
      {children && <p className={styles.emptyText}>{children}</p>}
      {action}
    </div>
  );
}

/** A refusal from the server, with its trace id to quote. */
export function ErrorNotice({ message, traceId, action }: { message: string; traceId?: string; action?: ReactNode }) {
  return (
    <div className={styles.error} role="alert">
      <Icon name="alert" />
      <div className={styles.errorBody}>
        <p>{message}</p>
        {traceId && <p className={styles.trace}>Trace {traceId}</p>}
      </div>
      {action}
    </div>
  );
}

/** Grey placeholders in the shape of what is loading. */
export function Skeleton({ height = 16, width = '100%' }: { height?: number; width?: number | string }) {
  return <span className={styles.skeleton} style={{ height, width }} aria-hidden="true" />;
}

export function LoadingCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className={styles.loadingCard} aria-busy="true" aria-label="Loading">
      <Skeleton height={18} width="40%" />
      {Array.from({ length: lines - 1 }, (_, i) => (
        <Skeleton key={i} height={12} width={i % 2 ? '55%' : '75%'} />
      ))}
    </div>
  );
}
