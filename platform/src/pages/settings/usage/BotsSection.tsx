import { Link } from 'react-router';
import type { BotUsage } from '@/api/types';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { dollars, micros } from '@/lib/format';
import { Card } from '@/ui';
import styles from '../tokens/tokens.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

/** Each bot's month on Usage: its runs, its tokens and what they were charged past the plan's tokens. */
export function BotsSection({ bots }: { bots: BotUsage[] }) {
  return (
    <SettingsSection title="Bots" description="This month. A bot’s tokens draw on the plan’s first; charged is what went on the balance past them.">
      {bots.length === 0 ? (
        <p className={styles.meta}>No bot has run this month.</p>
      ) : (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Tokens by bot">
              <thead>
                <tr>
                  <th>Bot</th>
                  <th className={styles.num}>Runs</th>
                  <th className={styles.num}>Input</th>
                  <th className={styles.num}>Output</th>
                  <th className={styles.num}>Charged</th>
                </tr>
              </thead>
              <tbody>
                {bots.map((bot) => (
                  <tr key={bot.slug}>
                    <td>
                      <Link to={`/bots/${encodeURIComponent(bot.slug)}`}>{bot.name}</Link>
                    </td>
                    <td className={styles.num}>{n(bot.runs)}</td>
                    <td className={styles.num}>{n(bot.input_tokens)}</td>
                    <td className={styles.num}>{n(bot.output_tokens)}</td>
                    <td className={styles.num}>{dollars(micros(bot.charged_cents))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </SettingsSection>
  );
}
