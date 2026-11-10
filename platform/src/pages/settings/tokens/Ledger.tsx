import type { LedgerEntry, LedgerKind, LlmModel } from '@/api/types';
import { cx } from '@/lib/cx';
import { date, dollars, micros, rate } from '@/lib/format';
import { Card, Chip, type ChipTone } from '@/ui';
import styles from './tokens.module.css';

const kinds: Record<LedgerKind, { label: string; tone: ChipTone }> = {
  topup: { label: 'Top-up', tone: 'green' },
  grant: { label: 'Grant', tone: 'blue' },
  refund: { label: 'Refund', tone: 'violet' },
  charge: { label: 'Charge', tone: 'neutral' },
};

/** The balance's movements, newest first: what was added, granted, refunded or charged, in dollars. */
export function LedgerTable({ entries, models = [] }: { entries: LedgerEntry[]; models?: LlmModel[] }) {
  const modelName = (id: string) => models.find((m) => m.id === id)?.name ?? id;
  return (
    <Card>
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Balance history">
          <thead>
            <tr>
              <th>Date</th>
              <th>Kind</th>
              <th className={styles.num}>Amount</th>
              <th>Model or note</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => {
              const kind = kinds[entry.kind] ?? { label: entry.kind, tone: 'neutral' as const };
              const amount = micros(entry.amount_cents, entry.amount_micros);
              const about = [entry.model && modelName(entry.model), entry.note].filter(Boolean).join(' · ');
              return (
                <tr key={`${entry.at}-${i}`}>
                  <td className={styles.date}>{date(entry.at)}</td>
                  <td>
                    <Chip tone={kind.tone}>{kind.label}</Chip>
                  </td>
                  <td className={cx(styles.num, amount < 0 && styles.negative)}>{amount > 0 ? `+${dollars(amount)}` : dollars(amount)}</td>
                  <td>{about || '–'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Each hosted model's price past the allowance, in dollars per million input and output tokens. */
export function ModelRates({ models }: { models: LlmModel[] }) {
  return (
    <div className={styles.tableBox}>
      <table className={styles.table} aria-label="Model rates">
        <thead>
          <tr>
            <th>Model</th>
            <th className={styles.num}>Context</th>
            <th className={styles.num}>Input, per million tokens</th>
            <th className={styles.num}>Output, per million tokens</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.id}>
              <td>
                <span className={styles.model}>
                  {model.name}
                  <span className={styles.mono}>{model.id}</span>
                  {model.status === 'beta' && <Chip tone="violet">Beta</Chip>}
                  {model.status === 'deprecated' && <Chip tone="amber">Deprecated</Chip>}
                </span>
              </td>
              <td className={styles.num}>{`${model.context_tokens.toLocaleString('en-GB')} tokens`}</td>
              <td className={styles.num}>{rate(model.input_cents_per_mtok)}</td>
              <td className={styles.num}>{rate(model.output_cents_per_mtok)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
