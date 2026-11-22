import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useApprovals, useBotPlaces, useBotSearch, useBots, type Bot } from '@/api/bots';
import { useBotTemplates, type BotTemplate } from '@/api/botTemplates';
import { botTemplatePath } from '@/pages/templates/BotTemplates';
import { Cat } from '@/bots/cat/Cat';
import { mascotSrc } from '@/bots/cat/mascots';
import type { Look } from '@/bots/cat/look';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { useUrlSearch } from '@/components/SearchPaged';
import { ago, plural } from '@/lib/format';
import { Button, EmptyState, Skeleton, Tabs, TextField } from '@/ui';
import { gateNames } from './ada';
import { BotMaker } from './BotMaker';
import { NewBotDialog } from './NewBotDialog';
import { botPath, RunChip } from './parts';
import cs from '../connections/connections.module.css';
import look from './look.module.css';

type View = 'yours' | 'browse';
const TABS = [
  { id: 'yours', label: 'Yours' },
  { id: 'browse', label: 'Browse' },
] as const;

/** A bot's face in its round, as the Glyphh Bot app's rail: its own mascot when it has one, else its cat. */
function Face({ look: l, mascot, size = 50, busy }: { look: Look | null | undefined; mascot?: string | null; size?: number; busy?: boolean }) {
  return (
    <span className={look.ava}>{mascot ? <img src={mascotSrc(mascot)} width={size} height={size} alt="" /> : <Cat look={l} size={size} busy={busy} />}</span>
  );
}

/** Rows standing in for what is loading, so nothing jumps when it lands. */
function Placeholders({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <li key={i} aria-hidden="true">
          <div className={look.row}>
            <Skeleton height={56} width={56} />
            <div className={look.who}>
              <Skeleton height={16} width="50%" />
              <Skeleton height={12} width="80%" />
            </div>
          </div>
        </li>
      ))}
    </>
  );
}

/** A bot in the list: its cat, name and what it is for; its Ada gates and what it watches; its last run and next. */
function BotRow({ bot, place, waiting }: { bot: Bot; place?: string; waiting: number }) {
  const title = `bot-${bot.slug}`;
  const gates = gateNames(bot);
  const apps = bot.connections.map((c) => c.app_name);
  return (
    <li>
      <Link to={botPath(bot.slug)} className={look.row} aria-labelledby={title}>
        <Face look={bot.look} mascot={bot.mascot} busy={bot.last_run?.status === 'running'} />
        <div className={look.who}>
          <h2 id={title} className={look.name}>
            {bot.name}
          </h2>
          {bot.summary && <p>{bot.summary}</p>}
        </div>
        <div className={look.meta}>
          <span>{gates.length ? `Ada: ${gates.join(' · ')}` : 'No Ada gates'}</span>
          <span>{apps.length ? `Watches ${apps.join(', ')}` : 'No connections yet'}</span>
          {bot.next_run ? <span>Next run {bot.next_run}</span> : <span>Runs when you run it</span>}
        </div>
        <div className={look.state}>
          {waiting > 0 ? (
            <span className={`${look.pill} ${look.pillOn}`}>
              <span className={look.dot} aria-hidden="true" />
              {waiting} waiting on you
            </span>
          ) : bot.last_run ? (
            <RunChip status={bot.last_run.status} small />
          ) : (
            <span className={look.muted}>Never run</span>
          )}
          {bot.last_run && <span className={look.muted}>{ago(bot.last_run.created_at)}</span>}
          {bot.runs_on && <span className={`${look.pill} ${look.pillSmall}`}>On {place ?? 'your machine'}</span>}
        </div>
      </Link>
    </li>
  );
}

function TemplateRow({ template, have }: { template: BotTemplate; have: boolean }) {
  const title = `template-${template.slug}`;
  return (
    <li>
      <Link to={botTemplatePath(template.slug)} className={look.row} aria-labelledby={title}>
        <Face look={template.look} />
        <div className={look.who}>
          <h2 id={title} className={look.name}>
            {template.name}
          </h2>
          <p>{template.summary}</p>
        </div>
        <div className={look.meta}>
          <span>{template.gates.length ? `Ada: ${template.gates.join(' · ')}` : 'No Ada gates'}</span>
          <span>{template.required_apps.length ? `Needs ${template.required_apps.map((a) => a.name).join(', ')}` : 'Needs no connections'}</span>
        </div>
        <div className={look.state}>{have ? <span className={`${look.pill} ${look.pillSmall}`}>Added</span> : <span className={look.muted}>Add</span>}</div>
      </Link>
    </li>
  );
}

/** The org's bots the server finds for what is typed (`GET /v1/bots?q=`). */
function Yours({ q, onMake, waiting }: { q: string; onMake: () => void; waiting: Map<string, number> }) {
  const found = useBotSearch(q.trim());
  const places = useBotPlaces();
  const named = new Map((places.data ?? []).map((p) => [p.id, p.name]));
  const shown = found.data;
  if (found.error) return <ApiErrorNotice error={found.error} />;
  if (shown === undefined)
    return (
      <ul className={look.rows} aria-busy="true" aria-label="Loading">
        <Placeholders count={3} />
      </ul>
    );
  if (shown.length === 0 && !q.trim() && !found.isPlaceholderData)
    return (
      <EmptyState
        icon="user"
        title="No bots yet"
        action={
          <span className={look.facts}>
            <Link to="?tab=browse" className={cs.inlineLink}>
              Browse bots
            </Link>
            <Button variant="secondary" icon="plus" onClick={onMake}>
              Make one
            </Button>
          </span>
        }
      >
        A bot decides with gates in Ada that learn from your answers. Add a ready-made one, or make your own.
      </EmptyState>
    );
  if (shown.length === 0)
    return (
      <EmptyState icon="search" title="Nothing matches">
        None of your bots matches “{q}”.
      </EmptyState>
    );
  return (
    <ul className={look.rows} aria-label="Your bots" aria-busy={found.isFetching || undefined}>
      {shown.map((bot) => (
        <BotRow key={bot.id} bot={bot} place={named.get(bot.runs_on ?? null)} waiting={waiting.get(bot.slug) ?? 0} />
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
        <ul className={look.rows} aria-label="Bots to add">
          {templates.isPending ? <Placeholders count={4} /> : shown.map((t) => <TemplateRow key={t.slug} template={t} have={have.has(t.name)} />)}
        </ul>
      )}
      <p className={look.muted}>
        These are the Marketplace’s bots. <Link to="/marketplace/bots">Open the Marketplace</Link>
      </p>
    </>
  );
}

/**
 * Bots, in the Glyphh Bot app's look: the crew of the org's bots as a strip of cats, what waits on you, then the
 * bots as rows (each with its Ada gates, what it watches and its last run) and the Marketplace's bots to add (Browse)
 * as two tabs under one search. New bot makes one; Create with AI is in its dialog.
 */
export function BotsPage() {
  const bots = useBots();
  const approvals = useApprovals();
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
  const waiting = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of approvals.data ?? []) if (r.kind !== 'swarm') m.set(r.bot_slug, (m.get(r.bot_slug) ?? 0) + 1);
    return m;
  }, [approvals.data]);
  const asks = [...waiting.values()].reduce((a, b) => a + b, 0);
  const crew = bots.data ?? [];

  return (
    <div className={look.page}>
      <header className={look.listHead}>
        <div className={look.headText}>
          <span className={look.label}>Glyphh bots</span>
          <h1 className={look.listTitle}>Bots</h1>
          <p className={look.sub}>Each bot decides with gates in Ada that learn from your answers, and does the rest with Claude and only the tools you allow.</p>
        </div>
        <div className={look.actions}>
          {asks > 0 && (
            <Link to="/approvals" className={look.chip}>
              {plural(asks, 'answer')} waiting
            </Link>
          )}
          <Button variant="primary" icon="plus" onClick={() => setMaking(true)}>
            New bot
          </Button>
        </div>
      </header>
      {crew.length > 1 && (
        <nav className={look.crew} aria-label="The crew">
          {crew.map((b) => (
            <Link key={b.id} to={botPath(b.slug)}>
              {b.mascot ? <img src={mascotSrc(b.mascot)} width={26} height={26} alt="" /> : <Cat look={b.look} size={26} />}
              {b.name}
            </Link>
          ))}
        </nav>
      )}
      <div className={look.toolbar}>
        <TextField
          className={cs.search}
          label="Search"
          type="search"
          placeholder={view === 'browse' ? 'Search bots to add' : 'Search your bots'}
          value={search.typed}
          onChange={(e) => search.setTyped(e.target.value)}
        />
        <div className={look.tabs}>
          <Tabs label="Bots" tabs={TABS} value={view} onChange={(tab) => search.setParam({ tab: tab === 'yours' ? null : tab })} />
        </div>
      </div>
      <ApiErrorNotice error={bots.error} />
      <div role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
        {view === 'yours' ? <Yours q={search.q} onMake={() => setMaking(true)} waiting={waiting} /> : <Browse q={search.q} have={have} />}
      </div>
      <NewBotDialog open={making} onClose={() => setMaking(false)} onAi={withAi} />
      {asking && <BotMaker open onClose={() => setAsking(false)} />}
    </div>
  );
}
