import { Link, useParams, useSearchParams } from 'react-router';
import { useBot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { LoadingCard, panelId, tabId, Tabs, type Tab } from '@/ui';
import { ModelsTab } from './ModelsTab';
import { OverviewTab } from './OverviewTab';
import { CatTile } from './parts';
import { RunsTab } from './RunsTab';
import { SettingsTab } from './SettingsTab';
import { ToolsTab } from './ToolsTab';
import styles from './bots.module.css';

type TabId = 'overview' | 'tools' | 'models' | 'runs' | 'settings';
const tabs: ReadonlyArray<Tab<TabId>> = [
  { id: 'overview', label: 'Overview' },
  { id: 'tools', label: 'Tools' },
  { id: 'models', label: 'Ada models' },
  { id: 'runs', label: 'Runs' },
  { id: 'settings', label: 'Settings' },
];

/** One bot, a tab each (`?tab=`): what it is, the tools it may use per connection, its Ada models, its runs, its limits. */
export function BotPage() {
  const { name: slug = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const bot = useBot(slug);
  const asked = params.get('tab') as TabId | null;
  const tab: TabId = tabs.some((t) => t.id === asked) ? asked! : 'overview';

  return (
    <>
      <Link to="/bots" className={styles.back}>
        ← Bots
      </Link>
      <div className={styles.row}>
        {bot.data && <CatTile look={bot.data.look} size={64} busy={bot.data.last_run?.status === 'running'} />}
        <div className={styles.grow}>
          <PageHeader title={bot.data?.name ?? slug} description={bot.data?.summary ?? undefined} />
        </div>
      </div>
      {bot.isPending && <LoadingCard />}
      <ApiErrorNotice error={bot.error} />
      {bot.data && (
        <>
          <Tabs label="Bot" tabs={tabs} value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} />
          <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)}>
            {tab === 'overview' && <OverviewTab key={bot.data.updated_at} bot={bot.data} />}
            {tab === 'tools' && <ToolsTab bot={bot.data} />}
            {tab === 'models' && <ModelsTab key={bot.data.updated_at} bot={bot.data} />}
            {tab === 'runs' && <RunsTab bot={bot.data} />}
            {tab === 'settings' && <SettingsTab key={bot.data.updated_at} bot={bot.data} />}
          </div>
        </>
      )}
    </>
  );
}
