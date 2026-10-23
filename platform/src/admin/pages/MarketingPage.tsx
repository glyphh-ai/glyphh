import { useState } from 'react';
import { useAdminMarketing, useAdminTraffic } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Card, CopyField, EmptyState, LoadingCard, Select, TextField } from '@/ui';
import { n } from '../parts';
import { referrersByKey, TopCard, tops, why } from '../traffic';
import styles from '../admin.module.css';

const site = 'https://glyphh.ai';

const periods = [
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: '365', label: 'Last year' },
];

export type Tags = { path: string; source: string; medium: string; campaign: string; content: string };

/**
 * A glyphh.ai link with its campaign tags, as the website keeps them (its middleware.js: utm_* in the glyphh_src cookie
 * for 90 days) and the server stores them on the account a visitor then signs up for. Lower case, spaces as dashes.
 */
export function taggedUrl({ path, source, medium, campaign, content }: Tags): string {
  const clean = (value: string) => value.trim().toLowerCase().replace(/\s+/g, '-');
  const page = `/${path.trim().replace(/^\/+/, '')}`;
  const tags = Object.entries({ utm_source: source, utm_medium: medium, utm_campaign: campaign, utm_content: content })
    .map(([k, v]) => [k, clean(v)] as const)
    .filter(([, v]) => v);
  const query = new URLSearchParams(tags.map(([k, v]) => [k, v])).toString();
  return `${site}${page === '/' ? '/' : page}${query ? `?${query}` : ''}`;
}

/** Sign-ups and paid conversions by where they came from, and a builder for the tagged links that feed it. */
export function MarketingPage() {
  const [days, setDays] = useState(90);
  const sources = useAdminMarketing(days);
  return (
    <div className={styles.page}>
      <PageHeader title="Marketing links" description="Where sign-ups came from: the tags on the glyphh.ai link a visitor arrived on, kept with their new account." />
      <LinkBuilder />
      <div className={styles.filters}>
        <Select label="Signed up" value={String(days)} options={periods} onChange={(e) => setDays(Number(e.target.value))} />
      </div>
      {sources.isPending && <LoadingCard />}
      <ApiErrorNotice error={sources.error} />
      {sources.data?.length === 0 && <EmptyState icon="flag" title="No sign-ups in this period" />}
      {sources.data && sources.data.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Sign-ups by source">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Medium</th>
                  <th>Campaign</th>
                  <th className={styles.num}>People</th>
                  <th className={styles.num}>Orgs</th>
                  <th className={styles.num}>Paid</th>
                  <th className={styles.num}>Paying now</th>
                  <th className={styles.num}>Conversion</th>
                </tr>
              </thead>
              <tbody>
                {sources.data.map((r) => (
                  <tr key={`${r.source}|${r.medium}|${r.campaign}`}>
                    <td>{r.source}</td>
                    <td>{r.medium}</td>
                    <td>{r.campaign}</td>
                    <td className={styles.num}>{n(r.people)}</td>
                    <td className={styles.num}>{n(r.orgs)}</td>
                    <td className={styles.num}>{n(r.paid)}</td>
                    <td className={styles.num}>{n(r.paying)}</td>
                    <td className={styles.num}>{r.orgs ? `${Math.round((100 * r.paid) / r.orgs)}%` : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <ReferrerCard days={days} />
    </div>
  );
}

/** Visitors by the site that sent them, beside sign-ups by source, when Cloudflare's plan gives referrers (his order, 2026-10-23). */
function ReferrerCard({ days }: { days: number }) {
  const traffic = useAdminTraffic(days);
  const data = traffic.data;
  if (!data) return <ApiErrorNotice error={traffic.error} />;
  const given = data.zones.filter((z) => tops(z, 'referrers').note === null);
  const none = data.zones[0] ? why(data.zones[0].available.referrers) : 'Nothing pulled yet.';
  const note = !data.connected ? 'Cloudflare is not connected.' : given.length === 0 ? none : null;
  const from = given.some((z) => tops(z, 'referrers').from) ? 'From Web Analytics' : null;
  return <TopCard title="Visitors by referrer" label="Referrer" rows={referrersByKey(given)} note={note} from={from} />;
}

function LinkBuilder() {
  const [tags, setTags] = useState<Tags>({ path: '/', source: '', medium: '', campaign: '', content: '' });
  const set = (key: keyof Tags) => (e: { target: { value: string } }) => setTags((t) => ({ ...t, [key]: e.target.value }));
  const url = taggedUrl(tags);
  return (
    <Card>
      <h2 className={styles.cardTitle}>Make a tagged link</h2>
      <div className={styles.form}>
        <div className={styles.filters}>
          <TextField label="Page" placeholder="/ or /code" value={tags.path} onChange={set('path')} />
          <TextField label="Source" placeholder="reddit, google, newsletter" value={tags.source} onChange={set('source')} />
          <TextField label="Medium" placeholder="cpc, social, email" value={tags.medium} onChange={set('medium')} />
          <TextField label="Campaign" placeholder="launch-2026" value={tags.campaign} onChange={set('campaign')} />
          <TextField label="Content" hint="Optional: which ad or post" value={tags.content} onChange={set('content')} />
        </div>
        <CopyField label="Tagged link" value={url} />
      </div>
    </Card>
  );
}
