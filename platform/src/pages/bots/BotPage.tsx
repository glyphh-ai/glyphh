import { Link, useParams, useSearchParams } from 'react-router';
import { useBot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Icon, LoadingCard, panelId, tabId, Tabs, type Tab } from '@/ui';
import { GatesTab } from './GatesTab';
import { LoopTab } from './LoopTab';
import { OverviewTab } from './OverviewTab';
import { CatTile, RunChip } from './parts';
import { RunsTab } from './RunsTab';
import { SettingsTab } from './SettingsTab';
import { ToolsTab } from './ToolsTab';
import cs from '../connections/connections.module.css';
import styles from './bots.module.css';

type TabId = 'overview' | 'loop' | 'tools' | 'runs' | 'gates' | 'settings';
const tabs: ReadonlyArray<Tab<TabId>> = [
  { id: 'overview', label: 'Overview' },
  { id: 'loop', label: 'Loop & skills' },
  { id: 'tools', label: 'Tools' },
  { id: 'runs', label: 'Runs' },
  { id: 'gates', label: 'Gates' },
  { id: 'settings', label: 'Settings' },
];

/**
 * One bot, a tab each (`?tab=`): its instructions and model, its loop (the spec) and skills, the tools it may use per
 * connection, its runs (answered, cancelled or corrected there), what its gates learned, and deleting it.
 */
export function BotPage() {
  const { name: slug = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const bot = useBot(slug);
  const asked = params.get('tab') as TabId | null;
  const tab: TabId = tabs.some((t) => t.id === asked) ? asked! : 'overview';

  return (
    <div className={cs.page}>
      <Link to="/bots" className={cs.back}>
        <Icon name="arrowLeft" size={14} /> Bots
      </Link>
      <div className={cs.hero}>
        <CatTile look={bot.data?.look} size={64} busy={bot.data?.last_run?.status === 'running'} />
        <div className={cs.heroText}>
          <h1 className={cs.title}>{bot.data?.name ?? slug}</h1>
          <p className={cs.muted}>{bot.data ? (bot.data.summary ?? 'A bot') : ' '}</p>
        </div>
        <div className={cs.heroActions}>{bot.data?.last_run && <RunChip status={bot.data.last_run.status} />}</div>
      </div>
      {bot.isPending && <LoadingCard lines={6} />}
      <ApiErrorNotice error={bot.error} />
      {bot.data && (
        <>
          <Tabs label="Bot" tabs={tabs} value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} />
          <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)} className={`${cs.panel} ${styles.tabBody}`}>
            {tab === 'overview' && <OverviewTab key={bot.data.updated_at} bot={bot.data} />}
            {tab === 'loop' && <LoopTab key={bot.data.updated_at} bot={bot.data} />}
            {tab === 'tools' && <ToolsTab bot={bot.data} />}
            {tab === 'runs' && <RunsTab bot={bot.data} />}
            {tab === 'gates' && <GatesTab bot={bot.data} />}
            {tab === 'settings' && <SettingsTab bot={bot.data} />}
          </div>
        </>
      )}
    </div>
  );
}
