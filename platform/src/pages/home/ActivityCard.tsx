import { useMemo } from 'react';
import { Link } from 'react-router';
import { useTokenDays, useUsageSeries } from '@/api/queries';
import { Chart, type Series } from '@/components/Chart';
import { axisDays, dayText, field, sum, tokensOn } from '@/pages/settings/usage/days';
import { Card, LoadingCard } from '@/ui';
import styles from './home.module.css';

const DAYS = 7;
const n = (value: number) => value.toLocaleString('en-GB');

/**
 * The last 7 days at a glance, UTC: the tokens in and out (the bots' and the hosted models') when the plan has them,
 * else Ada's requests, as small bars by day, with the week's total.
 */
export function ActivityCard({ tokens }: { tokens: boolean }) {
  const series = useUsageSeries(DAYS);
  const tokenDays = useTokenDays(DAYS, tokens);
  const chart = useMemo(() => {
    const axis = axisDays(series.data, DAYS);
    const labels = axis.map(dayText);
    if (tokens) {
      const used = tokensOn(axis, tokenDays.data ?? [], 'all');
      const data: Series[] = [
        { label: 'Input', data: used.input },
        { label: 'Output', data: used.output },
      ];
      return { labels, data, total: `${n(sum(used.input) + sum(used.output))} tokens`, title: 'Token volume' };
    }
    const reads = field(axis, series.data, 'reads');
    return { labels, data: [{ label: 'Requests', data: reads }] as Series[], total: `${n(sum(reads))} requests`, title: 'Requests' };
  }, [series.data, tokenDays.data, tokens]);

  return (
    <Card aria-label={chart.title}>
      <div className={styles.wideHead}>
        <div>
          <h2 className={styles.label}>{`${chart.title}, last 7 days`}</h2>
          <span className={styles.big}>{chart.total}</span>
        </div>
        <Link to="/usage" className={styles.link}>
          See usage
        </Link>
      </div>
      {series.isPending || (tokens && tokenDays.isPending) ? (
        <LoadingCard lines={3} />
      ) : (
        <Chart kind="bar" stacked label={`${chart.title} by day, last 7 days`} labels={chart.labels} series={chart.data} height={160} />
      )}
    </Card>
  );
}
