import { useState } from 'react';
import { useAdminTraffic, type Traffic } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Chart } from '@/components/Chart';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Card, EmptyState, LoadingCard, Select } from '@/ui';
import { dayLabel, lastPulled, TopCard, tops } from '../traffic';
import styles from '../admin.module.css';

const periods = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
];

/** Each domain and the hostnames Cloudflare saw under it: "glyphh.ai" the whole domain, "glyphh.ai|docs.glyphh.ai" one host. */
function places(traffic: Traffic) {
  return traffic.zones.flatMap((z) => [
    { value: z.name, label: `${z.name} (whole domain)` },
    ...z.hosts.map((h) => ({ value: `${z.name}|${h.host}`, label: h.host })),
  ]);
}

/** Glyphh's own sites' traffic by domain or hostname, from Cloudflare (his order, 2026-10-23). */
export function TrafficPage() {
  const [days, setDays] = useState(30);
  const [place, setPlace] = useState('');
  const traffic = useAdminTraffic(days);
  const data = traffic.data;
  return (
    <div className={styles.page}>
      <PageHeader title="Traffic" description={data ? `Glyphh’s own sites, from Cloudflare. ${lastPulled(data)}.` : 'Glyphh’s own sites, from Cloudflare.'} />
      {traffic.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={traffic.error} />
      {data && !data.connected && (
        <EmptyState icon="eye" title="Cloudflare is not connected">
          The server has no Cloudflare token (GLYPHH_CLOUDFLARE_API_TOKEN).
        </EmptyState>
      )}
      {data?.connected && data.zones.length === 0 && (
        <EmptyState icon="eye" title="Nothing pulled yet">
          The server pulls Cloudflare’s numbers once an hour.
        </EmptyState>
      )}
      {data && data.zones.length > 0 && (
        <>
          <div className={styles.filters}>
            <Select label="Domain" value={place || data.zones[0]!.name} options={places(data)} onChange={(e) => setPlace(e.target.value)} />
            <Select label="Period" value={String(days)} options={periods} onChange={(e) => setDays(Number(e.target.value))} />
          </div>
          <Place traffic={data} place={place || data.zones[0]!.name} />
        </>
      )}
    </div>
  );
}

function Place({ traffic, place }: { traffic: Traffic; place: string }) {
  const [zoneName, host] = place.split('|');
  const zone = traffic.zones.find((z) => z.name === zoneName) ?? traffic.zones[0]!;
  const hostSeries = host ? zone.hosts.find((h) => h.host === host) : undefined;
  const labels = zone.series.map((d) => dayLabel(d.day));
  const pages = tops(zone, 'pages', host);
  const referrers = tops(zone, 'referrers', host);
  return (
    <>
      <Card>
        <h2 className={styles.cardTitle}>{host ?? zone.name}, by day</h2>
        {hostSeries ? (
          <Chart
            kind="line"
            label={`Requests and visits to ${host} by day`}
            labels={labels}
            series={[
              { label: 'Requests', data: hostSeries.series.map((d) => d.requests) },
              { label: 'Visits', data: hostSeries.series.map((d) => d.visits) },
            ]}
          />
        ) : (
          <Chart
            kind="line"
            label={`Visitors and page views on ${zone.name} by day`}
            labels={labels}
            series={[
              { label: 'Visitors', data: zone.series.map((d) => d.uniques) },
              { label: 'Page views', data: zone.series.map((d) => d.page_views) },
            ]}
          />
        )}
        {host && <p className={styles.meta}>Cloudflare counts a hostname’s requests and visits, not its unique visitors.</p>}
      </Card>
      <div className={styles.charts}>
        <TopCard title={host ? `Top countries, all of ${zone.name}` : 'Top countries'} label="Country" rows={zone.countries} />
        <TopCard title="Top pages" label="Page" rows={pages.rows} from={pages.from} note={pages.note} showHost={!host} />
        <TopCard title="Top referrers" label="Referrer" rows={referrers.rows} from={referrers.from} note={referrers.note} showHost={!host} />
      </div>
    </>
  );
}
