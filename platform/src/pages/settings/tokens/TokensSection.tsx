import { useMemo } from 'react';
import { useBilling, useMe, useTokenDays } from '@/api/queries';
import type { TokenDay, TokenUsage } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Chart, type Series } from '@/components/Chart';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date, dollars, micros } from '@/lib/format';
import { Card, Icon, LoadingCard, ProgressBar } from '@/ui';
import usageStyles from '../UsagePage.module.css';
import { BalanceCard } from './BalanceCard';
import styles from './tokens.module.css';

const n = (value: number) => value.toLocaleString('en-GB');
const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = 30;

/** "2026-11-03" as "3 Nov". */
const dayText = (day: string) => {
  const d = new Date(`${day}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? day : `${d.getUTCDate()} ${months[d.getUTCMonth()]}`;
};

/**
 * Each day's input and output tokens across the models, from the first day with use to the last, a day with none
 * as nothing; in day order, UTC.
 */
export function tokensByDay(days: TokenDay[]): { labels: string[]; input: number[]; output: number[] } {
  const totals = new Map<string, { input: number; output: number }>();
  for (const row of days) {
    const total = totals.get(row.day) ?? { input: 0, output: 0 };
    total.input += row.input_tokens;
    total.output += row.output_tokens;
    totals.set(row.day, total);
  }
  const sorted = [...totals.keys()].sort();
  const labels: string[] = [];
  const input: number[] = [];
  const output: number[] = [];
  if (sorted.length === 0) return { labels, input, output };
  const last = new Date(`${sorted.at(-1)}T00:00:00Z`).getTime();
  for (let t = new Date(`${sorted[0]}T00:00:00Z`).getTime(); t <= last; t += 86_400_000) {
    const day = new Date(t).toISOString().slice(0, 10);
    const total = totals.get(day) ?? { input: 0, output: 0 };
    labels.push(dayText(day));
    input.push(total.input);
    output.push(total.output);
  }
  return { labels, input, output };
}

/**
 * Glyphh's hosted models on Usage: the month's tokens against the plan's allowance, the overage balance, the last 30
 * days' input and output tokens by day, and each model's month. Nothing while hosted models are off (no `tokens`). */
export function TokensSection() {
  const billing = useBilling();
  const me = useMe();
  const tokens = billing.data?.tokens ?? null;
  const balance = billing.data?.balance ?? null;
  const days = useTokenDays(DAYS, tokens !== null);
  const chart = useMemo(() => tokensByDay(days.data ?? []), [days.data]);
  const series = useMemo<Series[]>(
    () => [
      { label: 'Input', data: chart.input },
      { label: 'Output', data: chart.output },
    ],
    [chart],
  );

  // Off, or not read: the page's other sections carry any refusal.
  if (!tokens) return null;

  return (
    <>
      <SettingsSection
        title="Tokens"
        description={`Glyphh’s hosted models, input and output together. Counted by calendar month in UTC: the allowance starts again on ${date(tokens.resets_at)}.`}
      >
        <div className={usageStyles.meters}>
          <Allowance tokens={tokens} />
          {balance && <BalanceCard balance={balance} isAdmin={me.data?.role === 'admin'} />}
        </div>
      </SettingsSection>

      <SettingsSection title="Tokens by day" description="The last 30 days, input and output, across every hosted model.">
        {days.isPending && <LoadingCard lines={4} />}
        <ApiErrorNotice error={days.error} />
        {days.data && chart.labels.length === 0 && <p className={styles.meta}>No tokens in the last 30 days.</p>}
        {days.data && chart.labels.length > 0 && (
          <Card>
            <Chart kind="bar" stacked label="Input and output tokens by day, last 30 days" labels={chart.labels} series={series} />
          </Card>
        )}
      </SettingsSection>

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
  if (tokens.models.length === 0) return <p className={styles.meta}>No hosted model used this month.</p>;
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
                <td>{model.name}</td>
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
