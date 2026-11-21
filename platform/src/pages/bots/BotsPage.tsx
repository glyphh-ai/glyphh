import { useState } from 'react';
import { Link } from 'react-router';
import { useBots, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, plural } from '@/lib/format';
import { Button, EmptyState, LoadingCard } from '@/ui';
import { NewBotDialog } from './NewBotDialog';
import { botPath, CatTile, RunChip } from './parts';
import styles from './bots.module.css';

function BotCard({ bot }: { bot: Bot }) {
  const title = `bot-${bot.slug}`;
  const tools = bot.connections.reduce((n, c) => n + c.tools.length, 0);
  return (
    <li>
      <Link to={botPath(bot.slug)} className={styles.card} aria-labelledby={title}>
        <CatTile look={bot.look} busy={bot.last_run?.status === 'running'} />
        <div className={styles.cardBody}>
          <h2 id={title} className={styles.name}>
            {bot.name}
          </h2>
          {bot.summary && <p className={styles.summary}>{bot.summary}</p>}
          <span className={styles.muted}>
            {plural(tools, 'tool')} · {plural(bot.models.length, 'Ada model')}
          </span>
          {bot.last_run ? (
            <span className={styles.row}>
              <RunChip status={bot.last_run.status} />
              <span className={styles.muted}>{ago(bot.last_run.created_at)}</span>
            </span>
          ) : (
            <span className={styles.muted}>Never run</span>
          )}
        </div>
      </Link>
    </li>
  );
}

/** The org's bots, each a card with its cat; New bot makes one. */
export function BotsPage() {
  const bots = useBots();
  const [making, setMaking] = useState(false);
  const make = (
    <Button variant="primary" icon="plus" onClick={() => setMaking(true)}>
      New bot
    </Button>
  );
  return (
    <>
      <PageHeader
        title="Bots"
        description="Claude agents that do work for you on Glyphh, with the tools you allow from your connections and your Ada models. You pay for the tokens they use."
        actions={make}
      />
      {bots.isPending && <LoadingCard />}
      <ApiErrorNotice error={bots.error} />
      {bots.data?.length === 0 && (
        <EmptyState icon="model" title="No bots yet" action={make}>
          Make one and tell it what to do.
        </EmptyState>
      )}
      {bots.data && bots.data.length > 0 && (
        <ul className={styles.grid} aria-label="Bots">
          {bots.data.map((bot) => (
            <BotCard key={bot.id} bot={bot} />
          ))}
        </ul>
      )}
      <NewBotDialog open={making} onClose={() => setMaking(false)} />
    </>
  );
}
