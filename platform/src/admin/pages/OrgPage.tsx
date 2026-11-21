import type { ReactNode } from 'react';
import { useParams } from 'react-router';
import { useAdminOrg, type OrgDetail } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Chart } from '@/components/Chart';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, date, dollars, micros, stamp } from '@/lib/format';
import { Card, Chip, LoadingCard } from '@/ui';
import { PrivacyNote } from '../AdminLayout';
import { BillingChip, n } from '../parts';
import { OrgActions } from './OrgActions';
import styles from '../admin.module.css';

/** One org: its account and billing, staff actions, members, use, and its models and jobs as metadata only. */
export function OrgPage() {
  const { id = '' } = useParams();
  const org = useAdminOrg(id);
  const data = org.data;
  return (
    <div className={styles.page}>
      <PageHeader title={data?.account.name ?? 'Organisation'} description={<PrivacyNote />} />
      {org.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={org.error} />
      {data && (
        <>
          <Account org={data} />
          <OrgActions org={data.account} />
          <Members org={data} />
          <Usage org={data} />
          <Models org={data} />
          <Taken org={data} />
        </>
      )}
    </div>
  );
}

const or = (value: string | null | undefined, none = 'None') => value || none;

function Account({ org }: { org: OrgDetail }) {
  const a = org.account;
  const tags = a.source ? Object.entries(a.source).map(([k, v]) => `${k}=${v}`).join(', ') : null;
  return (
    <Card>
      <div className={styles.chips}>
        <Chip>{`${a.plan} v${a.plan_version}`}</Chip>
        <BillingChip status={a.billing_status} />
        {a.suspended_at && <Chip tone="red">{`Suspended ${date(a.suspended_at)}`}</Chip>}
      </div>
      <dl className={styles.facts}>
        <Fact label="Org id" value={<span className={styles.mono}>{a.id}</span>} />
        <Fact label="Created" value={date(a.created_at)} />
        <Fact label="Stripe customer" value={<span className={styles.mono}>{or(a.stripe_customer_id)}</span>} />
        <Fact label="Stripe subscription" value={<span className={styles.mono}>{or(a.stripe_subscription_id)}</span>} />
        <Fact label="Renews" value={a.renews_at ? date(a.renews_at) : 'No'} />
        <Fact label="Enterprise until" value={a.plan_until ? date(a.plan_until) : 'Not on Enterprise'} />
        <Fact label="First paid" value={a.first_paid_at ? date(a.first_paid_at) : 'Never'} />
        <Fact label="Sign-up source" value={tags ?? 'Untagged'} />
        <Fact label="API keys and licence keys" value={`${n(org.api_keys)} API keys, ${n(org.licences)} licence keys`} />
        {org.balance && <Fact label="Overage balance" value={dollars(micros(org.balance.cents, org.balance.micros))} />}
        {a.suspended_reason && <Fact label="Suspended because" value={a.suspended_reason} />}
      </dl>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Members({ org }: { org: OrgDetail }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>{`Members (${n(org.members.length)})`}</h2>
      <div className={styles.tableBox}>
        <table className={styles.table} aria-label="Members">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Role</th>
              <th>Signs in with</th>
              <th>Joined</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {org.members.map((m) => (
              <tr key={m.id}>
                <td>{m.email}</td>
                <td>{or(m.name, '–')}</td>
                <td>{m.role}</td>
                <td>{m.providers.length ? m.providers.join(', ') : '–'}</td>
                <td className={styles.num}>{date(m.created_at)}</td>
                <td className={styles.num}>{m.last_seen_at ? ago(m.last_seen_at) : 'Never'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Usage({ org }: { org: OrgDetail }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>{`Ada reads: ${n(org.reads_month)} this month`}</h2>
      <Chart kind="bar" label="Ada reads by day, last 30 days" labels={org.days.map((d) => d.day.slice(5))} series={[{ label: 'Reads', data: org.days.map((d) => d.reads) }]} />
      <p className={styles.meta}>{org.months.map((m) => `${m.period}: ${n(m.reads)}`).join(' · ') || 'No reads recorded.'}</p>
    </Card>
  );
}

function Models({ org }: { org: OrgDetail }) {
  const failed = org.jobs.filter((j) => j.state === 'failed').length;
  return (
    <Card>
      <h2 className={styles.cardTitle}>{`Models (${n(org.models.filter((m) => !m.deleted).length)} live)`}</h2>
      <p className={styles.meta}>{`${n(org.jobs.length)} jobs in the last 7 days, ${n(failed)} failed.`}</p>
      {org.models.length > 0 && (
        <div className={styles.tableBox}>
          <table className={styles.table} aria-label="Models">
            <thead>
              <tr>
                <th>Model</th>
                <th>Version</th>
                <th>Ada</th>
                <th className={styles.num}>Precedents</th>
                <th>Made</th>
              </tr>
            </thead>
            <tbody>
              {org.models.map((m) => (
                <tr key={`${m.name}-${m.created_at}`}>
                  <td>
                    {m.name} {m.deleted && <Chip>Deleted</Chip>}
                  </td>
                  <td>{`v${m.active_version}`}</td>
                  <td>{m.ada ? `${m.ada}${m.kernel ? ` (kernel ${m.kernel})` : ''}` : '–'}</td>
                  <td className={styles.num}>{n(m.precedents)}</td>
                  <td className={styles.num}>{date(m.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Taken({ org }: { org: OrgDetail }) {
  return (
    <Card>
      <h2 className={styles.cardTitle}>Staff activity on this org</h2>
      <ul className={styles.alerts} aria-label="Staff activity">
        {org.audit.map((e) => (
          <li key={e.id} className={styles.meta}>{`${stamp(e.at)} ${e.staff_email}: ${e.action} (${e.outcome})`}</li>
        ))}
      </ul>
    </Card>
  );
}
