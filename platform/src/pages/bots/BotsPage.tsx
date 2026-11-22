import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useBotPlaces, useBotSearch, useBots, type Bot } from '@/api/bots';
import { useBotTemplates, type BotTemplate } from '@/api/botTemplates';
import { botTemplatePath } from '@/pages/templates/BotTemplates';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { useUrlSearch } from '@/components/SearchPaged';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, plural } from '@/lib/format';
import { Button, Chip, EmptyState, Skeleton, Tabs, TextField } from '@/ui';
import { BotMaker } from './BotMaker';
import { NewBotDialog } from './NewBotDialog';
import { botPath, CatTile, RunChip } from './parts';
import cs from '../connections/connections.module.css';
import styles from './bots.module.css';

type View = 'yours' | 'browse';
const TABS = [
  { id: 'yours', label: 'Yours' },
  { id: 'browse', label: 'Browse' },
] as const;

/** Cards standing in for what is loading, so nothing jumps when it lands. */
function Placeholders({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <li key={i} aria-hidden="true">
          <div className={styles.card}>
            <Skeleton height={68} width={68} />
            <div className={styles.cardBody}>
              <Skeleton height={16} width="50%" />
              <Skeleton height={12} width="90%" />
              <Skeleton height={12} width="40%" />
            </div>
          </div>
        </li>
      ))}
    </>
  );
}

/** A bot in the list: its cat, name and what it has, its last run, its next one, and (off Glyphh cloud) where it runs. */
function BotCard({ bot, place }: { bot: Bot; place?: string }) {
  const title = `bot-${bot.slug}`;
  const tools = bot.connections.reduce((n, c) => n + c.tools.length, 0);
  return (
    <li>
      <Link to={botPath(bot.slug)} className={styles.card} aria-labelledby={title}>
        <CatTile look={bot.look} mascot={bot.mascot} busy={bot.last_run?.status === 'running'} />
        <div className={styles.cardBody}>
          <h2 id={title} className={styles.name}>
            {bot.name}
          </h2>
          {bot.summary && <p className={styles.summary}>{bot.summary}</p>}
          <span className={styles.muted}>
            {plural(tools, 'tool')} · {plural(bot.gate_models.length, 'gate')} · {plural(Object.keys(bot.skills).length, 'skill')}
          </span>
          {bot.last_run ? (
            <span className={styles.row}>
              <RunChip status={bot.last_run.status} />
              <span className={styles.muted}>{ago(bot.last_run.created_at)}</span>
            </span>
          ) : (
            <span className={styles.muted}>Never run</span>
          )}
          {bot.next_run && <span className={styles.muted}>Next run {bot.next_run}</span>}
          {bot.runs_on && (
            <span className={styles.place}>
              <Chip tone="violet">On {place ?? 'your machine'}</Chip>
            </span>
          )}
        </div>
      </Link>
    </li>
  );
}

function TemplateCard({ template, have }: { template: BotTemplate; have: boolean }) {
  const title = `template-${template.slug}`;
  return (
    <li>
      <Link to={botTemplatePath(template.slug)} className={styles.card} aria-labelledby={title}>
        <CatTile look={template.look} />
        <div className={styles.cardBody}>
          <h2 id={title} className={styles.name}>
            {template.name}
          </h2>
          <p className={styles.summary}>{template.summary}</p>
          <span className={styles.muted}>
            {template.required_apps.length ? `Needs ${template.required_apps.map((a) => a.name).join(', ')}` : 'Needs no connections'} ·{' '}
            {plural(template.gates.length, 'gate')}
          </span>
          {have && <span className={cs.added}>Added</span>}
        </div>
      </Link>
    </li>
  );
}

/** The org's bots the server finds for what is typed (`GET /v1/bots?q=`). */
function Yours({ q, onMake, onAi }: { q: string; onMake: () => void; onAi: () => void }) {
  const found = useBotSearch(q.trim());
  const places = useBotPlaces();
  const named = new Map((places.data ?? []).map((p) => [p.id, p.name]));
  const shown = found.data;
  if (found.error) return <ApiErrorNotice error={found.error} />;
  if (shown === undefined)
    return (
      <ul className={styles.grid} aria-busy="true" aria-label="Loading">
        <Placeholders count={3} />
      </ul>
    );
  if (shown.length === 0 && !q.trim() && !found.isPlaceholderData)
    return (
      <EmptyState
        icon="user"
        title="No bots yet"
        action={
          <span className={styles.row}>
            <Link to="?tab=browse" className={cs.inlineLink}>
              Browse bots
            </Link>
            <Button variant="secondary" icon="plus" onClick={onMake}>
              Make one
            </Button>
            <Button variant="secondary" icon="sparkle" onClick={onAi}>
              Create with AI
            </Button>
          </span>
        }
      >
        Add a ready-made bot, make one yourself, or describe it and let AI make it.
      </EmptyState>
    );
  if (shown.length === 0)
    return (
      <EmptyState icon="search" title="Nothing matches">
        None of your bots matches “{q}”.
      </EmptyState>
    );
  return (
    <ul className={styles.grid} aria-label="Your bots" aria-busy={found.isFetching || undefined}>
      {shown.map((bot) => (
        <BotCard key={bot.id} bot={bot} place={named.get(bot.runs_on ?? null)} />
      ))}
    </ul>
  );
}

/** The Marketplace's bots, searched here (the list is small); each opens its page in Marketplace › Bots. */
function Browse({ q, have }: { q: string; have: Set<string> }) {
  const templates = useBotTemplates();
  const needle = q.trim().toLowerCase();
  const shown = useMemo(
    () =>
      (templates.data ?? []).filter(
        (t) => !needle || [t.name, t.summary, ...t.required_apps.map((a) => a.name), ...t.tools].some((s) => s.toLowerCase().includes(needle)),
      ),
    [templates.data, needle],
  );
  return (
    <>
      <ApiErrorNotice error={templates.error} />
      {templates.data && shown.length === 0 ? (
        <EmptyState icon="search" title="Nothing matches">
          {needle ? `No bot matches “${q}”.` : 'No bots to add yet.'}
        </EmptyState>
      ) : (
        <ul className={styles.grid} aria-label="Bots to add">
          {templates.isPending ? <Placeholders count={6} /> : shown.map((t) => <TemplateCard key={t.slug} template={t} have={have.has(t.name)} />)}
        </ul>
      )}
      <p className={styles.muted}>
        These are the Marketplace’s bots. <Link to="/marketplace/bots">Open the Marketplace</Link>
      </p>
    </>
  );
}

/**
 * Bots, as Connections shows its apps: the org's own bots (searched by the server) and the Marketplace's bots to add
 * (Browse) as two tabs under one search. A bot to add opens its page in Marketplace › Bots.
 */
export function BotsPage() {
  const bots = useBots();
  const search = useUrlSearch();
  const [params] = useSearchParams();
  const [making, setMaking] = useState(false);
  const [asking, setAsking] = useState(false);
  const withAi = () => {
    setMaking(false);
    setAsking(true);
  };
  const view: View = params.get('tab') === 'browse' ? 'browse' : 'yours';
  const have = useMemo(() => new Set((bots.data ?? []).map((b) => b.name)), [bots.data]);

  return (
    <div className={cs.page}>
      <PageHeader
        title="Bots"
        description="Bots that do recurring work for you: Claude where judgment is needed, gates that learn from your answers, and only the tools you allow."
        actions={
          <>
            <Button variant="secondary" icon="sparkle" onClick={withAi}>
              Create with AI
            </Button>
            <Button variant="primary" icon="plus" onClick={() => setMaking(true)}>
              New bot
            </Button>
          </>
        }
      />
      <div className={cs.toolbar}>
        <TextField
          className={cs.search}
          label="Search"
          type="search"
          placeholder={view === 'browse' ? 'Search bots to add' : 'Search your bots'}
          value={search.typed}
          onChange={(e) => search.setTyped(e.target.value)}
        />
        <Tabs label="Bots" tabs={TABS} value={view} onChange={(tab) => search.setParam({ tab: tab === 'yours' ? null : tab })} />
      </div>
      <ApiErrorNotice error={bots.error} />
      <div className={cs.panel} role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
        {view === 'yours' ? <Yours q={search.q} onMake={() => setMaking(true)} onAi={withAi} /> : <Browse q={search.q} have={have} />}
      </div>
      <NewBotDialog open={making} onClose={() => setMaking(false)} onAi={withAi} />
      {asking && <BotMaker open onClose={() => setAsking(false)} />}
    </div>
  );
}
