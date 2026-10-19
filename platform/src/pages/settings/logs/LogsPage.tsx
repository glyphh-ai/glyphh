import { useSearchParams } from 'react-router';
import { useRuntimeNodes } from '@/api/queries';
import { panelId, tabId, Tabs, type Tab } from '@/ui';
import { SettingsTitle } from '../SettingsTitle';
import { AuditPanel } from './AuditPanel';
import { LogsPanel } from './LogsPanel';
import { MetricsPanel } from './MetricsPanel';
import styles from './Logs.module.css';

type View = 'logs' | 'audit' | 'metrics';
const views: ReadonlyArray<Tab<View>> = [
  { id: 'logs', label: 'Logs' },
  { id: 'audit', label: 'Audit' },
  { id: 'metrics', label: 'Metrics' },
];

/**
 * What the org's runtimes send Glyphh when someone turns on rrotor's server logs (`RROTOR_SERVER_LOGS=on`): log lines,
 * audit events and metrics, newest first and read again every 10 seconds. By default a runtime sends nothing, and the
 * page says where the data is and how to see it. The tab is in the address (`?tab=audit`), so it can be linked to.
 */
export function LogsPage() {
  const [params, setParams] = useSearchParams();
  const asked = params.get('tab');
  const view: View = views.find((tab) => tab.id === asked)?.id ?? 'logs';
  const nodes = useRuntimeNodes().data?.nodes;

  return (
    <>
      <SettingsTitle title="Logs">What your runtimes send Glyphh, if you turn it on: their logs, audit events and metrics.</SettingsTitle>
      <div className={styles.page}>
        <Tabs label="What to show" tabs={views} value={view} onChange={(id) => setParams(id === 'logs' ? {} : { tab: id }, { replace: true })} />
        <div role="tabpanel" id={panelId(view)} aria-labelledby={tabId(view)} className={styles.panel}>
          {view === 'logs' && <LogsPanel nodes={nodes} />}
          {view === 'audit' && <AuditPanel nodes={nodes} />}
          {view === 'metrics' && <MetricsPanel nodes={nodes} />}
        </div>
      </div>
    </>
  );
}
