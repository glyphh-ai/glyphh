import type { ReactNode } from 'react';
import type { Alert } from '@/api/admin';
import { Button, Card, Chip, type ChipTone } from '@/ui';
import styles from './admin.module.css';

export const n = (value: number) => value.toLocaleString('en-GB');

/** 1.2 GB, 340 MB, 12 KB. */
export function bytes(value: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

/** A time in milliseconds, or a dash when nothing was measured. */
export const ms = (value: number | null) => (value === null ? '–' : `${n(Math.round(value))} ms`);

/** "2026102314" (an hour, UTC) as "14:00". */
export const hourLabel = (hour: string) => `${hour.slice(8, 10)}:00`;

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <Card>
      <div className={styles.statLabel}>{label}</div>
      <div className={styles.statValue}>{value}</div>
      {note && <div className={styles.statNote}>{note}</div>}
    </Card>
  );
}

const statusTones: Record<string, ChipTone> = { active: 'green', trialing: 'blue', past_due: 'amber', unpaid: 'red', canceled: 'neutral' };

/** A subscription's status as Stripe last said it; `none` is not subscribed. */
export function BillingChip({ status }: { status: string }) {
  if (status === 'none') return <Chip>Not subscribed</Chip>;
  return <Chip tone={statusTones[status] ?? 'neutral'}>{status.replace('_', ' ')}</Chip>;
}

/** The alerts at the top of the dashboard and the infrastructure page; a line when all is well. */
export function Alerts({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) return <p className={styles.allClear}>No alerts: every threshold is clear.</p>;
  return (
    <ul className={styles.alerts} aria-label="Alerts">
      {alerts.map((alert) => (
        <li key={alert.code} className={alert.severity === 'critical' ? `${styles.alert} ${styles.critical}` : styles.alert}>
          <Chip tone={alert.severity === 'critical' ? 'red' : 'amber'}>{alert.severity === 'critical' ? 'Critical' : 'Warning'}</Chip>
          {alert.message}
        </li>
      ))}
    </ul>
  );
}

/** Previous and Next over a list the server pages by offset. */
export function Pager({ offset, limit, total, onMove }: { offset: number; limit: number; total: number; onMove: (offset: number) => void }) {
  if (total <= limit) return null;
  return (
    <div className={styles.pager}>
      <span>{`${n(offset + 1)} to ${n(Math.min(offset + limit, total))} of ${n(total)}`}</span>
      <div className={styles.pagerButtons}>
        <Button size="sm" disabled={offset === 0} onClick={() => onMove(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button size="sm" disabled={offset + limit >= total} onClick={() => onMove(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  );
}
