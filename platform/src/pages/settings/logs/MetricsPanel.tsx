import { useMetrics } from '@/api/queries';
import type { MetricPoint, RuntimeNode } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { ago, duration } from '@/lib/format';
import { Chip, LoadingCard } from '@/ui';
import { Live } from './Live';
import { NothingSent } from './NothingSent';
import { byNode, linkText, runtimeName, sourceText, type NodeMetrics } from './telemetry';
import styles from './Logs.module.css';

const count = (n: number | null) => (n === null ? 'Not sent' : n.toLocaleString('en-GB'));

function precedentsText(m: NodeMetrics): string {
  if (m.precedents === null) return 'Not sent';
  return m.cap === null ? count(m.precedents) : `${count(m.precedents)} of ${count(m.cap)}`;
}

/**
 * Each node's latest metrics, from the latest point of each of its series: runs (and those not done), time spent
 * running, precedents against the cap, the link's state and what the drains dropped. Series rrotor sends that have no
 * column are listed below as they came.
 */
export function MetricsPanel({ nodes }: { nodes: RuntimeNode[] | undefined }) {
  const metrics = useMetrics();
  const points = metrics.data?.metrics ?? [];
  const rows = byNode(points);
  const other = rows.flatMap((row) => row.other);

  return (
    <>
      <Live>Each series’ latest</Live>
      {metrics.isPending && <LoadingCard />}
      <ApiErrorNotice error={metrics.error} />
      {metrics.data && points.length === 0 && <NothingSent title="No metrics yet" />}
      {rows.length > 0 && (
        <div className={styles.tableBox}>
          <table className={styles.table} aria-label="Metrics by node">
            <thead>
              <tr>
                <th scope="col">Node</th>
                <th scope="col">Runs</th>
                <th scope="col">Run time</th>
                <th scope="col">Precedents</th>
                <th scope="col">Link</th>
                <th scope="col">Dropped</th>
                <th scope="col">Sent</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                const runtime = runtimeName(m.runtime_id, m.runtime, nodes);
                const full = m.precedents !== null && m.cap !== null && m.precedents >= m.cap;
                return (
                  <tr key={m.key}>
                    <th scope="row">
                      <span className={styles.node}>{m.node_id ?? runtime}</span>
                      {m.node_id && <span className={styles.source}>{runtime}</span>}
                    </th>
                    <td>
                      {count(m.runs)}
                      {m.failed ? <span className={styles.source}>{`${count(m.failed)} not done`}</span> : null}
                    </td>
                    <td>{m.run_seconds === null ? 'Not sent' : duration(m.run_seconds)}</td>
                    <td>
                      {precedentsText(m)}
                      {full && (
                        <>
                          {' '}
                          <Chip tone="amber">Full</Chip>
                        </>
                      )}
                    </td>
                    <td>{linkText(m.link)}</td>
                    <td>{m.dropped !== null && m.dropped > 0 ? <Chip tone="amber">{count(m.dropped)}</Chip> : count(m.dropped)}</td>
                    <td>{m.at ? ago(m.at) : 'Not sent'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {other.length > 0 && (
        <List label="Other series">
          {other.map((p, i) => (
            <Row key={`${p.name}-${i}`} title={<span className={styles.code}>{p.name}</span>} meta={otherMeta(p, nodes)} actions={<span>{pointValue(p)}</span>} />
          ))}
        </List>
      )}
    </>
  );
}

function pointValue(p: MetricPoint): string {
  const value = typeof p.value === 'number' ? p.value.toLocaleString('en-GB') : 'Not sent';
  const unit = p.unit && p.unit !== '1' ? ` ${p.unit}` : '';
  return p.kind === 'histogram' && typeof p.count === 'number' ? `${value}${unit} over ${p.count.toLocaleString('en-GB')}` : `${value}${unit}`;
}

function otherMeta(p: MetricPoint, nodes: RuntimeNode[] | undefined): string {
  const parts = [sourceText(runtimeName(p.runtime_id, p.runtime, nodes), p.node_id)];
  const attributes = Object.entries(p.attributes ?? {}).map(([name, value]) => `${name}=${String(value)}`);
  if (attributes.length) parts.push(attributes.join(', '));
  return parts.join(' · ');
}
