import { Link } from 'react-router';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { money } from '@/lib/format';
import { Button, Card, Chip, LoadingCard } from '@/ui';
import { useGamesOverview, type GameRow, type Revenue } from './api';
import styles from './games.module.css';

const count = (value: number | null) => (value === null ? '–' : value.toLocaleString('en-GB'));
const cash = (cents: number | null) => (cents === null ? '–' : money(cents));

/** Every game at a glance: up or down, its players, its money, and what waits for someone. */
export function GamesPage() {
  const overview = useGamesOverview();
  return (
    <div className={styles.page}>
      <PageHeader
        title="Games"
        actions={
          <Button icon="undo" loading={overview.isFetching} onClick={() => void overview.refetch()}>
            Refresh
          </Button>
        }
      />
      {overview.isPending && <LoadingCard lines={6} />}
      <ApiErrorNotice error={overview.error} />
      {overview.data && (
        <div className={styles.games}>
          {overview.data.games.map((g) => (
            <GameCard key={g.id} game={g} />
          ))}
        </div>
      )}
    </div>
  );
}

function Health({ game }: { game: GameRow }) {
  if (!game.connected) return <Chip tone="amber">Not connected</Chip>;
  if (!game.health.ok) return <Chip tone="red" dot>Down</Chip>;
  return (
    <Chip tone="green" dot>
      Up
    </Chip>
  );
}

function Money({ revenue }: { revenue: Revenue | null }) {
  if (!revenue) return <p className={styles.meta}>Sells nothing.</p>;
  const cells: Array<[string, number | null]> = [
    ['Today', revenue.today],
    ['7 days', revenue.d7],
    ['30 days', revenue.d30],
    ['All time', revenue.all],
  ];
  return (
    <dl className={styles.money} aria-label="Revenue">
      {cells.map(([label, cents]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{cash(cents)}</dd>
        </div>
      ))}
    </dl>
  );
}

function GameCard({ game }: { game: GameRow }) {
  const s = game.summary;
  return (
    <Card as="article" aria-label={game.name} className={styles.gameCard}>
      <div className={styles.gameHead}>
        <img src={game.icon} alt="" width={40} height={40} className={styles.icon} />
        <div className={styles.gameName}>
          <h2 className={styles.cardTitle}>
            <Link to={`/admin/games/${game.id}`} className={styles.whole}>
              {game.name}
            </Link>
          </h2>
          <a href={game.site} target="_blank" rel="noreferrer" className={styles.site}>
            {game.site.replace(/^https:\/\//, '')}
          </a>
        </div>
        <Health game={game} />
      </div>
      {game.health.build && <p className={styles.meta}>{`Build ${game.health.build}`}</p>}
      {game.error && <p className={styles.problem}>{game.error}</p>}
      {s && (
        <>
          <dl className={styles.numbers}>
            <div>
              <dt>{s.playersAre === 'accounts' ? 'Accounts' : 'Players'}</dt>
              <dd>{count(s.players)}</dd>
            </div>
            <div>
              <dt>{s.labels[0]}</dt>
              <dd>{count(s.new24)}</dd>
            </div>
            <div>
              <dt>{s.labels[1]}</dt>
              <dd>{count(s.active24)}</dd>
            </div>
          </dl>
          <h3 className={styles.partTitle}>Revenue</h3>
          <Money revenue={s.revenue} />
          <ul className={styles.pending} aria-label="Waiting">
            {s.pending.map((p) => (
              <li key={p.label}>
                <Link to={`/admin/games/${game.id}?tab=${p.tab}`}>{p.label}</Link>
                <Chip tone={p.count > 0 ? 'amber' : 'neutral'}>{p.count.toLocaleString('en-GB')}</Chip>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className={styles.actions}>
        <Link to={`/admin/games/${game.id}`} className={styles.open}>
          Open admin
        </Link>
      </div>
    </Card>
  );
}
