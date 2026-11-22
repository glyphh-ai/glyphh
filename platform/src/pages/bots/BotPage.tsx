import { Link, useParams, useSearchParams } from 'react-router';
import { useBot } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import { mascotSrc } from '@/bots/cat/mascots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { Icon, LoadingCard, panelId, tabId, Tabs, type Tab } from '@/ui';
import { gateNames } from './ada';
import { GatesTab } from './GatesTab';
import { OverviewTab } from './OverviewTab';
import { RunChip } from './parts';
import { RunsTab } from './RunsTab';
import { SettingsTab } from './SettingsTab';
import { ToolsTab } from './ToolsTab';
import cs from '../connections/connections.module.css';
import look from './look.module.css';

type TabId = 'overview' | 'runs' | 'gates' | 'tools' | 'settings';
const tabs: ReadonlyArray<Tab<TabId>> = [
  { id: 'overview', label: 'Overview' },
  { id: 'runs', label: 'Decisions' },
  { id: 'gates', label: 'Ada gates' },
  { id: 'tools', label: 'Tools' },
  { id: 'settings', label: 'Settings' },
];

/**
 * One bot, in the Glyphh Bot app's look, built around Ada: its cat and what it is; Overview (what waits on you, its
 * latest decisions, its gates, what it watches and its tools in Claude), every decision (its runs, run and corrected
 * there), its gates in full, the tools it may use, and Settings (the editor, with the model, permission mode, voice
 * and the loop as JSON under Advanced, and deleting it). `?tab=loop` opens Settings with Advanced open.
 */
export function BotPage() {
  const { name: slug = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const bot = useBot(slug);
  const asked = params.get('tab');
  const tab: TabId = asked === 'loop' ? 'settings' : tabs.some((t) => t.id === asked) ? (asked as TabId) : 'overview';
  const b = bot.data;
  const tools = b ? b.connections.reduce((n, c) => n + c.tools.length, 0) : 0;

  return (
    <div className={look.page}>
      <Link to="/bots" className={cs.back}>
        <Icon name="arrowLeft" size={14} /> Bots
      </Link>
      <header className={look.head}>
        <div className={look.headCat}>
          {b?.mascot ? (
            <img src={mascotSrc(b.mascot)} width={96} height={96} alt="" />
          ) : (
            <Cat look={b?.look} size={92} mode="full" busy={b?.last_run?.status === 'running'} />
          )}
        </div>
        <div className={look.headText}>
          <span className={look.label}>Glyphh bot</span>
          <h1 className={look.title}>{b?.name ?? slug}</h1>
          <p className={look.sub}>{b ? (b.summary ?? 'A bot') : ' '}</p>
          {b && (
            <div className={look.facts}>
              {b.last_run && <RunChip status={b.last_run.status} />}
              <span className={look.pill}>{plural(gateNames(b).length, 'Ada gate')}</span>
              <span className={look.pill}>{plural(tools, 'tool')}</span>
              {b.schedule_summary && b.schedule?.every !== 'off' && <span className={look.pill}>{b.schedule_summary}</span>}
            </div>
          )}
        </div>
        {b && (
          <div className={look.actions}>
            <Link to="?tab=runs" className={look.primary}>
              Run now
            </Link>
            <Link to="?tab=settings" className={look.chip}>
              Settings
            </Link>
          </div>
        )}
      </header>
      {bot.isPending && <LoadingCard lines={6} />}
      <ApiErrorNotice error={bot.error} />
      {b && (
        <>
          <div className={look.tabs}>
            <Tabs label="Bot" tabs={tabs} value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} />
          </div>
          <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)}>
            {tab === 'overview' && <OverviewTab bot={b} />}
            {tab === 'runs' && <RunsTab bot={b} />}
            {tab === 'gates' && <GatesTab bot={b} />}
            {tab === 'tools' && <ToolsTab bot={b} />}
            {tab === 'settings' && <SettingsTab key={b.updated_at} bot={b} advanced={asked === 'loop'} />}
          </div>
        </>
      )}
    </div>
  );
}
