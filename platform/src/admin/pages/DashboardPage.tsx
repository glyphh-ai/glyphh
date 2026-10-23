import { useState } from 'react';
import { useAdminDashboard, useAdminInfra } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Chart } from '@/components/Chart';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { money } from '@/lib/format';
import { Button, Card, LoadingCard, Select } from '@/ui';
import { PrivacyNote } from '../AdminLayout';
import { Alerts, n, ms, Stat } from '../parts';
import styles from '../admin.module.css';

const periods = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
];

/** "2026-10-23" as "23 Oct". */
const dayLabel = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

/** The staff view's landing: alerts first, then sign-ups, use, revenue and the plan mix, day by day. */
export function DashboardPage() {
  const [days, setDays] = useState(30);
  const dashboard = useAdminDashboard(days);
  const infra = useAdminInfra();
  const data = dashboard.data;
  const labels = data?.series.map((d) => dayLabel(d.day)) ?? [];
  const refresh = (
    <Button
      icon="undo"
      onClick={() => {
        void dashboard.refetch();
        void infra.refetch();
      }}
    >
      Refresh
    </Button>
  );

  return (
    <div className={styles.page}>
      <PageHeader title="Dashboard" description={<PrivacyNote />} actions={refresh} />
      <Card>
        <h2 className={styles.cardTitle}>Alerts</h2>
        {infra.isPending && <LoadingCard lines={1} />}
        <ApiErrorNotice error={infra.error} />
        {infra.data && <Alerts alerts={infra.data.alerts} />}
      </Card>
      <div className={styles.filters}>
        <Select label="Period" value={String(days)} options={periods} onChange={(e) => setDays(Number(e.target.value))} />
      </div>
      {dashboard.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={dashboard.error} />
      {data && (
        <>
          <div className={styles.stats}>
            <Stat label="MRR" value={money(data.money.mrr_cents)} note={`${n(data.money.paying_orgs)} paying, ${n(data.money.contract_orgs)} on contract`} />
            <Stat label="Organisations" value={n(data.totals.orgs)} note={`${n(data.totals.suspended_orgs)} suspended`} />
            <Stat label="People" value={n(data.totals.users)} />
            <Stat label="Active orgs" value={n(data.totals.active_orgs)} note="Read Ada in the period" />
            <Stat label="Reads this month" value={n(data.totals.reads_month)} note={`Overage ${money(data.money.overage_cents_month)}`} />
            <Stat label="Models" value={n(data.totals.models)} note={`${n(data.totals.precedents)} precedents held`} />
            {infra.data && <Stat label="Read latency p95" value={ms(infra.data.read.last_hour.p95)} note="The last hour" />}
          </div>
          <div className={styles.charts}>
            <Card>
              <h2 className={styles.cardTitle}>Sign-ups</h2>
              <Chart
                kind="bar"
                label="Sign-ups by day"
                labels={labels}
                series={[
                  { label: 'People', data: data.series.map((d) => d.new_users) },
                  { label: 'Orgs', data: data.series.map((d) => d.new_orgs) },
                ]}
              />
            </Card>
            <Card>
              <h2 className={styles.cardTitle}>Ada reads</h2>
              <Chart kind="line" label="Ada reads by day" labels={labels} series={[{ label: 'Reads', data: data.series.map((d) => d.reads) }]} />
            </Card>
            <Card>
              <h2 className={styles.cardTitle}>Active orgs and models made</h2>
              <Chart
                kind="line"
                label="Active orgs and models made by day"
                labels={labels}
                series={[
                  { label: 'Active orgs', data: data.series.map((d) => d.active_orgs) },
                  { label: 'Models made', data: data.series.map((d) => d.models_created) },
                ]}
              />
            </Card>
            <Card>
              <h2 className={styles.cardTitle}>Paid conversions</h2>
              <Chart kind="bar" label="Paid conversions by day" labels={labels} series={[{ label: 'Conversions', data: data.series.map((d) => d.conversions) }]} />
            </Card>
          </div>
          <PlanMixCard plans={data.money.plans} />
        </>
      )}
    </div>
  );
}

function PlanMixCard({ plans }: { plans: Array<{ plan: string; orgs: number; paying: number; mrr_cents: number }> }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>Plan mix</h2>
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Plan mix">
          <thead>
            <tr>
              <th>Plan</th>
              <th className={styles.num}>Orgs</th>
              <th className={styles.num}>Paying</th>
              <th className={styles.num}>MRR</th>
            </tr>
          </thead>
          <tbody>
            {plans.map((p) => (
              <tr key={p.plan}>
                <td>{p.plan}</td>
                <td className={styles.num}>{n(p.orgs)}</td>
                <td className={styles.num}>{n(p.paying)}</td>
                <td className={styles.num}>{money(p.mrr_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
