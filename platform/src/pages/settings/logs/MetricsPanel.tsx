import { useMetrics } from '@/api/queries';
import type { RuntimeMetrics, RuntimeNode } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, duration } from '@/lib/format';
import { Chip, LoadingCard } from '@/ui';
import { Live } from './Live';
import { NothingSent } from './NothingSent';
import { linkText, runtimeName } from './telemetry';
import styles from './Logs.module.css';

const count = (n: number | null | undefined) => (typeof n === 'number' ? n.toLocaleString('en-GB') : 'Not sent');

function precedentsText(m: RuntimeMetrics): string {
  if (typeof m.precedents !== 'number') return 'Not sent';
  return typeof m.cap === 'number' ? `${count(m.precedents)} of ${count(m.cap)}` : count(m.precedents);
}

/** Each node's latest metrics: runs, time spent running, precedents against its cap, its link and what it dropped. */
export function MetricsPanel({ nodes }: { nodes: RuntimeNode[] | undefined }) {
  const metrics = useMetrics();
  const runtimes = metrics.data?.runtimes ?? [];

  return (
    <>
      <Live>Each node’s latest</Live>
      {metrics.isPending && <LoadingCard />}
      <ApiErrorNotice error={metrics.error} />
      {metrics.data && runtimes.length === 0 && <NothingSent title="No metrics yet" />}
      {runtimes.length > 0 && (
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
              {runtimes.map((m, i) => {
                const runtime = runtimeName(m.runtime_id, m.runtime, nodes);
                const full = typeof m.precedents === 'number' && typeof m.cap === 'number' && m.precedents >= m.cap;
                return (
                  <tr key={`${m.runtime_id ?? ''}/${m.node_id ?? i}`}>
                    <th scope="row">
                      <span className={styles.node}>{m.node_id ?? runtime}</span>
                      {m.node_id && <span className={styles.source}>{runtime}</span>}
                    </th>
                    <td>{count(m.runs)}</td>
                    <td>{typeof m.run_seconds === 'number' ? duration(m.run_seconds) : 'Not sent'}</td>
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
                    <td>{typeof m.drops === 'number' && m.drops > 0 ? <Chip tone="amber">{count(m.drops)}</Chip> : count(m.drops)}</td>
                    <td>{m.at ? ago(m.at) : 'Not sent'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
