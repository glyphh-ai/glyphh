import { useMemo, useState, type ReactNode } from 'react';
import { useBilling, useTokenDays, useUsageSeries } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Chart, type Series } from '@/components/Chart';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { money } from '@/lib/format';
import { Card, LoadingCard, Select } from '@/ui';
import { axisDays, dayText, field, rangeDays, ranges, sum, tokensOn, type Range } from './days';
import styles from './charts.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

/** A chart in a card: its name, the range's total beside it, and the chart. */
function ChartCard({ title, total, children }: { title: string; total: string; children: ReactNode }) {
  return (
    <Card aria-label={title}>
      <div className={styles.head}>
        <h3 className={styles.title}>{title}</h3>
        <span className={styles.total}>{total}</span>
      </div>
      {children}
    </Card>
  );
}

/**
 * Usage over time, a range at a time (the last 7 or 30 days, or this month): Ada's requests, and with hosted models on
 * their tokens in and out (one model's or every model's) and what went on the balance. Days are UTC. Precedents have
 * no history on the server, so they are only this month's meter above.
 */
export function UsageCharts() {
  const [range, setRange] = useState<Range>('30');
  const [model, setModel] = useState('all');
  const days = rangeDays(range);
  const billing = useBilling();
  const tokens = billing.data?.tokens ?? null;
  const series = useUsageSeries(days);
  const tokenDays = useTokenDays(days, tokens !== null);

  const axis = useMemo(() => axisDays(series.data, days), [series.data, days]);
  const labels = useMemo(() => axis.map(dayText), [axis]);
  const models = useMemo(() => {
    const named = new Map((tokens?.models ?? []).map((m) => [m.id, m.name]));
    for (const row of tokenDays.data ?? []) if (!named.has(row.model)) named.set(row.model, row.model);
    return [{ value: 'all', label: 'All models' }, ...[...named].map(([value, label]) => ({ value, label }))];
  }, [tokens, tokenDays.data]);
  const used = useMemo(() => tokensOn(axis, tokenDays.data ?? [], model), [axis, tokenDays.data, model]);
  const charts = useMemo(() => {
    const reads = field(axis, series.data, 'reads');
    const decides = field(axis, series.data, 'decides');
    return {
      tokens: [
        { label: 'Input', data: used.input },
        { label: 'Output', data: used.output },
      ] as Series[],
      charged: [{ label: 'Charged', data: used.charged }] as Series[],
      requests: [
        { label: 'Requests', data: reads },
        { label: 'Decides', data: decides },
      ] as Series[],
      totals: { reads: sum(reads) },
    };
  }, [axis, series.data, used]);

  const rangeName = ranges.find((r) => r.value === range)!.label.toLowerCase();

  return (
    <SettingsSection title="Over time" description="Day by day, UTC. Pick a range, and a model for its tokens and charges.">
      <div className={styles.controls}>
        <Select label="Range" value={range} options={ranges} onChange={(event) => setRange(event.target.value as Range)} />
        {tokens && <Select label="Model" value={model} options={models} onChange={(event) => setModel(event.target.value)} />}
      </div>
      <ApiErrorNotice error={series.error ?? tokenDays.error} />
      {series.isPending ? (
        <LoadingCard lines={4} />
      ) : (
        <div className={styles.grid}>
          {tokens && (
            <ChartCard title="Tokens in and out" total={`${n(sum(used.input) + sum(used.output))} tokens`}>
              <Chart kind="bar" stacked label={`Input and output tokens by day, ${rangeName}`} labels={labels} series={charts.tokens} />
            </ChartCard>
          )}
          {tokens && (
            <ChartCard title="Charged to the balance" total={money(Math.round(sum(used.charged)))}>
              <Chart kind="bar" cents label={`Charged to the balance by day, ${rangeName}`} labels={labels} series={charts.charged} />
            </ChartCard>
          )}
          <ChartCard title="Ada requests" total={`${n(charts.totals.reads)} requests`}>
            <Chart kind="line" label={`Ada requests and decides by day, ${rangeName}`} labels={labels} series={charts.requests} />
          </ChartCard>
        </div>
      )}
    </SettingsSection>
  );
}
