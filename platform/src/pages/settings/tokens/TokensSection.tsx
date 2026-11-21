import { useBilling, useMe } from '@/api/queries';
import type { TokenUsage } from '@/api/types';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date, dollars, micros } from '@/lib/format';
import { Card, Chip, Icon, ProgressBar } from '@/ui';
import usageStyles from '../UsagePage.module.css';
import { BotsSection } from '../usage/BotsSection';
import { BalanceCard } from './BalanceCard';
import styles from './tokens.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

/**
 * Tokens on Usage, the bots' and Glyphh's hosted models' (one meter): the month's against the plan's allowance, the
 * overage balance, each bot's month and each model's month (the days are Usage's charts, usage/UsageCharts). Nothing
 * from a server that leaves `tokens` out. */
export function TokensSection() {
  const billing = useBilling();
  const me = useMe();
  const tokens = billing.data?.tokens ?? null;
  const balance = billing.data?.balance ?? null;

  // Off, or not read: the page's other sections carry any refusal.
  if (!tokens) return null;

  return (
    <>
      <SettingsSection
        title="Tokens"
        description={`Your bots’ and Glyphh’s hosted models’, input and output together. Counted by calendar month in UTC: the allowance starts again on ${date(tokens.resets_at)}.`}
      >
        <div className={usageStyles.meters}>
          <Allowance tokens={tokens} />
          {balance && <BalanceCard balance={balance} isAdmin={me.data?.role === 'admin'} />}
        </div>
      </SettingsSection>

      {billing.data?.bots && <BotsSection bots={billing.data.bots} />}

      <SettingsSection title="Tokens by model" description="This month. Charged is what went on the balance, past the allowance.">
        <ModelTable tokens={tokens} />
      </SettingsSection>
    </>
  );
}

/** The month's tokens against the allowance; the bar stops full once the use goes past it. */
function Allowance({ tokens }: { tokens: TokenUsage }) {
  const { used, max, over_used: over } = tokens;
  return (
    <Card aria-label="Tokens this month">
      <div className={usageStyles.meterHead}>
        <Icon name="layers" />
        Tokens this month
      </div>
      <div className={usageStyles.value}>
        <span className={usageStyles.used}>{n(used)}</span>
        <span className={usageStyles.of}>{max === null ? 'tokens, by contract' : `of ${n(max)} tokens`}</span>
      </div>
      {max !== null && <ProgressBar value={Math.min(used, max)} max={max} label="Tokens this month" />}
      {over > 0 ? (
        <p className={styles.meta}>{`${n(over)} past the allowance, charged to the balance.`}</p>
      ) : (
        max !== null && <p className={styles.meta}>{`Past ${n(max)}, tokens are charged to the balance.`}</p>
      )}
    </Card>
  );
}

function ModelTable({ tokens }: { tokens: TokenUsage }) {
  if (tokens.models.length === 0) return <p className={styles.meta}>No model used this month.</p>;
  return (
    <Card>
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Tokens by model">
          <thead>
            <tr>
              <th>Model</th>
              <th className={styles.num}>Input</th>
              <th className={styles.num}>Output</th>
              <th className={styles.num}>Requests</th>
              <th className={styles.num}>Charged</th>
            </tr>
          </thead>
          <tbody>
            {tokens.models.map((model) => (
              <tr key={model.id}>
                <td>
                  {model.name} {model.kind === 'bot' && <Chip>Bots</Chip>}
                </td>
                <td className={styles.num}>{n(model.input_tokens)}</td>
                <td className={styles.num}>{n(model.output_tokens)}</td>
                <td className={styles.num}>{n(model.requests)}</td>
                <td className={styles.num}>{dollars(micros(model.charged_cents))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
