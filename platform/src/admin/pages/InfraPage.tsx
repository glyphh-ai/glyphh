import { useAdminInfra, type Infra, type Latency } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Chart } from '@/components/Chart';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, duration } from '@/lib/format';
import { Button, Card, Chip, LoadingCard } from '@/ui';
import { Alerts, bytes, hourLabel, ms, n, Stat } from '../parts';
import styles from '../admin.module.css';

/** What the server measures of itself: Ada's queues and workers, latency, errors by route, jobs, Postgres, Redis. */
export function InfraPage() {
  const infra = useAdminInfra();
  const data = infra.data;
  const refresh = (
    <Button icon="undo" onClick={() => void infra.refetch()}>
      Refresh
    </Button>
  );
  return (
    <div className={styles.page}>
      <PageHeader title="Infrastructure" description="Measured by the server itself, as of this page’s loading." actions={refresh} />
      {infra.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={infra.error} />
      {data && <InfraBody data={data} />}
    </div>
  );
}

function InfraBody({ data }: { data: Infra }) {
  const used = Object.values(data.database.connections).reduce((a, b) => a + b, 0);
  const share = data.http.total ? (100 * data.http.c5xx) / data.http.total : 0;
  return (
    <>
      <Card>
        <h2 className={styles.cardTitle}>Alerts</h2>
        <Alerts alerts={data.alerts} />
      </Card>
      <div className={styles.stats}>
        <Stat label="Read latency p95" value={ms(data.read.last_5m.p95)} note={`Last 5 minutes, ${n(data.read.last_5m.n)} reads`} />
        <Stat label="Requests, last hour" value={n(data.http.total)} note={`${share.toFixed(1)}% 5xx`} />
        <Stat
          label="Minute tick"
          value={data.tick.last_at ? ago(data.tick.last_at) : 'Not run'}
          note={data.tick.age_seconds === null ? 'No beat since Redis started' : `${duration(data.tick.age_seconds)} ago`}
        />
        <Stat label="Database" value={bytes(data.database.size_bytes)} note={`${n(used)} of ${n(data.database.max_connections)} connections`} />
        <Stat label="Redis memory" value={bytes(data.redis.used_bytes)} note={`${n(data.redis.keys)} keys, peak ${bytes(data.redis.peak_bytes)}`} />
      </div>
      <QueuesCard data={data} />
      <div className={styles.charts}>
        <LatencyCard title="Ada read latency" latency={data.read} />
        <LatencyCard title="API latency" latency={data.api} />
        <Card>
          <h2 className={styles.cardTitle}>Requests and 5xx, by hour</h2>
          <Chart
            kind="bar"
            label="Requests and 5xx by hour"
            labels={data.http.hourly.map((h) => hourLabel(h.hour))}
            series={[
              { label: 'Requests', data: data.http.hourly.map((h) => h.total) },
              { label: '5xx', data: data.http.hourly.map((h) => h.c5xx) },
            ]}
          />
        </Card>
      </div>
      <RoutesCard data={data} />
      <JobsCard data={data} />
      <DatabaseCard data={data} />
    </>
  );
}

function QueuesCard({ data }: { data: Infra }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>Ada queues and workers</h2>
      {!data.ada_cloud && <p className={styles.meta}>Ada Cloud is off: no worker is expected.</p>}
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Queues">
          <thead>
            <tr>
              <th>Stream</th>
              <th className={styles.num}>Length</th>
              <th className={styles.num}>Waiting</th>
              <th className={styles.num}>In hand</th>
              <th className={styles.num}>Workers alive</th>
            </tr>
          </thead>
          <tbody>
            {data.queues.map((q) => (
              <tr key={q.stream}>
                <td className={styles.mono}>{q.stream}</td>
                <td className={styles.num}>{n(q.length)}</td>
                <td className={styles.num}>{n(q.lag)}</td>
                <td className={styles.num}>{n(q.pending)}</td>
                <td className={styles.num}>
                  <Chip tone={q.alive > 0 ? 'green' : data.ada_cloud ? 'red' : 'neutral'} dot>{`${q.alive} of ${q.consumers}`}</Chip>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function LatencyCard({ title, latency }: { title: string; latency: Latency }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>{title}</h2>
      <p className={styles.meta}>
        {`Last hour: p50 ${ms(latency.last_hour.p50)}, p95 ${ms(latency.last_hour.p95)}, p99 ${ms(latency.last_hour.p99)} over ${n(latency.last_hour.n)} requests.`}
      </p>
      <Chart
        kind="line"
        label={`${title} by hour, in milliseconds`}
        labels={latency.hourly.map((h) => hourLabel(h.hour))}
        series={[
          { label: 'p50', data: latency.hourly.map((h) => h.latency.p50) },
          { label: 'p95', data: latency.hourly.map((h) => h.latency.p95) },
          { label: 'p99', data: latency.hourly.map((h) => h.latency.p99) },
        ]}
      />
    </Card>
  );
}

function RoutesCard({ data }: { data: Infra }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>Requests by route, last hour</h2>
      {data.http.routes.length === 0 ? (
        <p className={styles.meta}>No requests in the last hour.</p>
      ) : (
        <div className={styles.tableBox}>
          <table className={styles.table} aria-label="Requests by route">
            <thead>
              <tr>
                <th>Route</th>
                <th className={styles.num}>Requests</th>
                <th className={styles.num}>4xx</th>
                <th className={styles.num}>5xx</th>
              </tr>
            </thead>
            <tbody>
              {data.http.routes.map((r) => (
                <tr key={`${r.method} ${r.route}`}>
                  <td className={styles.mono}>{`${r.method} ${r.route}`}</td>
                  <td className={styles.num}>{n(r.total)}</td>
                  <td className={styles.num}>{n(r.c4xx)}</td>
                  <td className={styles.num}>{r.c5xx > 0 ? <Chip tone="red">{n(r.c5xx)}</Chip> : '0'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

const seconds = (value: number | null) => (value === null ? '–' : duration(value));

function JobsCard({ data }: { data: Infra }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>Ada jobs, last 7 days</h2>
      {data.jobs.length === 0 ? (
        <p className={styles.meta}>No jobs in the last 7 days.</p>
      ) : (
        <div className={styles.tableBox}>
          <table className={styles.table} aria-label="Jobs">
            <thead>
              <tr>
                <th>Kind</th>
                <th className={styles.num}>Jobs</th>
                <th className={styles.num}>Failed</th>
                <th className={styles.num}>Unfinished</th>
                <th className={styles.num}>p50</th>
                <th className={styles.num}>p95</th>
              </tr>
            </thead>
            <tbody>
              {data.jobs.map((j) => (
                <tr key={j.kind}>
                  <td>{j.kind}</td>
                  <td className={styles.num}>{n(j.total)}</td>
                  <td className={styles.num}>{n(j.failed)}</td>
                  <td className={styles.num}>{n(j.unfinished)}</td>
                  <td className={styles.num}>{seconds(j.p50_seconds)}</td>
                  <td className={styles.num}>{seconds(j.p95_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function DatabaseCard({ data }: { data: Infra }) {
  const { database } = data;
  return (
    <Card>
      <h2 className={styles.cardTitle}>Postgres</h2>
      <p className={styles.meta}>
        {`Every org’s Ada schemas together: ${bytes(database.ada_bytes)}. Connections: ${Object.entries(database.connections)
          .map(([state, count]) => `${count} ${state}`)
          .join(', ')}.`}
      </p>
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Largest tables">
          <thead>
            <tr>
              <th>Table</th>
              <th className={styles.num}>Size</th>
            </tr>
          </thead>
          <tbody>
            {database.tables.map((t) => (
              <tr key={t.name}>
                <td className={styles.mono}>{t.name}</td>
                <td className={styles.num}>{bytes(t.bytes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
