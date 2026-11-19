import type { Traffic, TrafficPart, TrafficTop, TrafficZone } from '@/api/admin';
import { stamp } from '@/lib/format';
import { Card } from '@/ui';
import { n } from './parts';
import styles from './admin.module.css';

/** Glyphh's own sites' traffic, from Cloudflare as the server's hourly pull kept it (his order, 2026-10-23). */

/** "2026-10-23" as "23 Oct". */
export const dayLabel = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

export const lastPulled = (traffic: Traffic) => (traffic.pulled_at ? `Last pulled ${stamp(traffic.pulled_at)} UTC` : 'Not pulled yet');

type Kind = 'pages' | 'referrers';

/**
 * A zone's pages or referrers, for one hostname or all of them: Cloudflare's edge numbers when the plan gives them,
 * else Web Analytics' when it is on, else none and the reason.
 */
export function tops(zone: TrafficZone, kind: Kind, host?: string): { rows: TrafficTop[]; from: string | null; note: string | null } {
  const edge = zone.available[kind];
  const rum = zone.available.rum;
  const pick = (rows: TrafficTop[]) => (host ? rows.filter((r) => r.host === host) : rows);
  if (edge?.ok) return { rows: pick(zone[kind]), from: null, note: null };
  if (rum?.ok) return { rows: pick(kind === 'pages' ? zone.rum_pages : zone.rum_referrers), from: 'From Web Analytics', note: null };
  return { rows: [], from: null, note: why(edge) };
}

/** Why a part has nothing: Cloudflare's words, or that it was never pulled. */
export const why = (part: TrafficPart | undefined) => `Not provided by this zone’s Cloudflare plan${part?.note ? `: ${part.note}` : ''}.`;

/** A list of the most common keys (countries, pages, referrers), or why there is none. */
export function TopCard({
  title,
  label,
  rows,
  note,
  from,
  showHost = false,
}: {
  title: string;
  label: string;
  rows: TrafficTop[];
  note?: string | null;
  from?: string | null;
  showHost?: boolean;
}) {
  const count = from ? 'Page loads' : 'Requests';
  return (
    <Card>
      <h2 className={styles.cardTitle}>{title}</h2>
      {from && <p className={styles.meta}>{from}</p>}
      {note ? (
        <p className={styles.meta}>{note}</p>
      ) : rows.length === 0 ? (
        <p className={styles.meta}>None in this period.</p>
      ) : (
        <div className={styles.tableBox}>
          <table className={styles.table} aria-label={title}>
            <thead>
              <tr>
                <th>{label}</th>
                {showHost && <th>Host</th>}
                <th className={styles.num}>{count}</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 20).map((r) => (
                <tr key={`${r.host}|${r.key}`}>
                  <td className={styles.mono}>{r.key}</td>
                  {showHost && <td>{r.host}</td>}
                  <td className={styles.num}>{n(r.n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
