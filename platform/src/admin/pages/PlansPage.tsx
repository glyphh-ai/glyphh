import { useAdminPlans, type PlanVersionRow } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date, money } from '@/lib/format';
import { Card, Chip, LoadingCard } from '@/ui';
import { n } from '../parts';
import styles from '../admin.module.css';

const limit = (value: number | null) => (value === null ? 'No limit' : n(value));

function price(v: PlanVersionRow): string {
  if (v.price_cents === null) return 'By contract';
  if (v.price_cents === 0) return 'Free';
  return `${money(v.price_cents)} a ${v.billing_interval ?? 'month'}`;
}

/** Every plan and each of its versions: price, Stripe price, caps and the orgs on it. */
export function PlansPage() {
  const plans = useAdminPlans();
  return (
    <div className={styles.page}>
      <PageHeader title="Plans" description="A version never changes: a new price or cap is a new version. Orgs stay on the version they are on." />
      {plans.isPending && <LoadingCard />}
      <ApiErrorNotice error={plans.error} />
      {plans.data?.map((plan) => (
        <Card key={plan.name}>
          <div className={styles.chips}>
            <h2 className={styles.cardTitle}>{plan.name}</h2>
            {!plan.active && <Chip>Retired</Chip>}
            <span className={styles.meta}>{`${n(plan.orgs)} orgs`}</span>
          </div>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label={`${plan.name} versions`}>
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Price</th>
                  <th>Stripe price</th>
                  <th className={styles.num}>Ada precedents</th>
                  <th className={styles.num}>Reads a month</th>
                  <th className={styles.num}>Calls a second</th>
                  <th>Past the month</th>
                  <th className={styles.num}>Runtime nodes</th>
                  <th className={styles.num}>Orgs</th>
                  <th>Made</th>
                </tr>
              </thead>
              <tbody>
                {plan.versions.map((v) => (
                  <tr key={v.id}>
                    <td>
                      {`v${v.version}`} {v.newest && <Chip tone="green">Newest</Chip>}
                    </td>
                    <td>{price(v)}</td>
                    <td className={styles.mono}>{v.stripe_price_id ?? '–'}</td>
                    <td className={styles.num}>{limit(v.cloud_precedents)}</td>
                    <td className={styles.num}>{limit(v.cloud_requests)}</td>
                    <td className={styles.num}>{limit(v.cloud_rps)}</td>
                    <td>{v.cloud_overage ? 'Metered' : 'Refused'}</td>
                    <td className={styles.num}>{limit(v.max_machines)}</td>
                    <td className={styles.num}>{n(v.orgs)}</td>
                    <td className={styles.num}>{date(v.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </div>
  );
}
