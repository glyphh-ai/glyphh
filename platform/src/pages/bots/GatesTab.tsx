import { useBotGates, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { EmptyState, Skeleton } from '@/ui';
import styles from './bots.module.css';

const LABELS: Record<string, string> = { precedents: 'Learned from', asked: 'Asked you', right: 'Right on its own' };

/** What each of the bot's gates has learned in Ada: the answers it holds, how often it asked, how often it was right. */
export function GatesTab({ bot }: { bot: Bot }) {
  const gates = useBotGates(bot.slug);
  if (gates.isPending)
    return (
      <ul className={styles.gates} aria-busy="true" aria-label="Loading gates">
        {Array.from({ length: Math.max(1, bot.gate_models.length) }, (_, i) => (
          <li key={i} className={styles.gate} aria-hidden="true">
            <Skeleton height={16} width="50%" />
            <Skeleton height={28} width="30%" />
            <Skeleton height={12} width="70%" />
          </li>
        ))}
      </ul>
    );
  if (gates.error) return <ApiErrorNotice error={gates.error} />;
  const names = Object.keys(gates.data);
  if (names.length === 0)
    return (
      <EmptyState icon="flag" title="No gates">
        This bot’s loop has no gates, so it learns nothing from your answers.
      </EmptyState>
    );
  return (
    <ul className={styles.gates} aria-label="Gates">
      {names.map((name) => {
        const g = gates.data[name]!;
        return (
          <li key={name} className={styles.gate} aria-label={name}>
            <span className={styles.toolName}>{name}</span>
            <span className={styles.stat}>{g.precedents ?? 0}</span>
            <span className={styles.muted}>answers learned</span>
            {(['asked', 'right'] as const).map((k) =>
              g[k] === undefined ? null : (
                <span key={k} className={styles.muted}>
                  {LABELS[k]}: {String(g[k])}
                </span>
              ),
            )}
          </li>
        );
      })}
    </ul>
  );
}
