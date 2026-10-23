import { Fragment } from 'react';
import type { GitHubCounts, GitHubRepo, GitHubTraffic, Traffic, TrafficPart, TrafficTop, TrafficZone } from '@/api/admin';
import { stamp } from '@/lib/format';
import { Card } from '@/ui';
import { n, Stat } from './parts';
import styles from './admin.module.css';

/**
 * Glyphh's own sites' traffic, from Cloudflare as the server's hourly pull kept it (his order, 2026-10-23): what the
 * dashboard, the Traffic page and Marketing links share.
 */

/** "2026-10-23" as "23 Oct". */
export const dayLabel = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

/** A change against the period before: +12%, −5%, or a dash when there was nothing before. */
export function change(value: number | null): string {
  if (value === null) return '–';
  const pct = Math.round(value * 100);
  return `${pct > 0 ? '+' : pct < 0 ? '−' : ''}${Math.abs(pct)}%`;
}

/** A share as a percentage to one place: 1.4%. */
export const share = (value: number | null) => (value === null ? '–' : `${(value * 100).toFixed(1)}%`);

export const lastPulled = (traffic: Traffic) => (traffic.pulled_at ? `Last pulled ${stamp(traffic.pulled_at)} UTC` : 'Not pulled yet');

/** Every zone's days added together: visitors (daily uniques) and page views. */
export function allZones(zones: TrafficZone[]): Array<{ day: string; uniques: number; page_views: number }> {
  const days = new Map<string, { day: string; uniques: number; page_views: number }>();
  for (const point of zones.flatMap((z) => z.series)) {
    const found = days.get(point.day) ?? { day: point.day, uniques: 0, page_views: 0 };
    found.uniques += point.uniques;
    found.page_views += point.page_views;
    days.set(point.day, found);
  }
  return [...days.values()].sort((a, b) => a.day.localeCompare(b.day));
}

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

/** Referrers across every zone, added up by the referring site. */
export function referrersByKey(zones: TrafficZone[]): TrafficTop[] {
  const found = new Map<string, number>();
  for (const row of zones.flatMap((z) => tops(z, 'referrers').rows)) found.set(row.key, (found.get(row.key) ?? 0) + row.n);
  return [...found.entries()].map(([key, count]) => ({ host: '', key, n: count })).sort((a, b) => b.n - a.n || a.key.localeCompare(b.key));
}

/** A small line of daily values, for a screen reader named by its label. */
export function Sparkline({ label, values }: { label: string; values: number[] }) {
  const width = 160;
  const height = 32;
  const top = Math.max(1, ...values);
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - (v / top) * (height - 4)).toFixed(1)}`).join(' ');
  return (
    <svg className={styles.sparkline} role="img" aria-label={label} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** One of a repository's figures: GitHub's last 14 days, the days kept added up since tracking began, and a sparkline. */
function RepoStat({ repo, label, field }: { repo: GitHubRepo; label: string; field: keyof GitHubCounts }) {
  const kept = repo.since ? `${n(repo.total[field])} since ${dayLabel(repo.since)} (daily, added up)` : 'No days kept yet';
  return (
    <Stat
      label={`${repo.name}: ${label}, last 14 days`}
      value={n(repo.last_14[field])}
      note={
        <>
          {kept}
          <Sparkline label={`${repo.name}: ${label} by day`} values={repo.series.map((d) => d[field])} />
        </>
      }
    />
  );
}

/** Each public repository's unique visitors and unique cloners from GitHub, beside the visitor to sign-up rate (his order, 2026-10-23). */
export function GitHubStats({ github }: { github: GitHubTraffic }) {
  if (!github.connected) return <Stat label="GitHub" value="–" note="GitHub is not connected." />;
  if (github.repos.length === 0) return <Stat label="GitHub" value="–" note="Not pulled yet." />;
  return github.repos.map((repo) => (
    <Fragment key={repo.name}>
      <RepoStat repo={repo} label="unique visitors" field="view_uniques" />
      <RepoStat repo={repo} label="unique cloners" field="clone_uniques" />
    </Fragment>
  ));
}

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
