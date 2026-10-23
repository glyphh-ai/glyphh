import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { useAdminOrgs, useAdminPlans, type OrgFilter } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, Card, Chip, EmptyState, LoadingCard, Select, TextField } from '@/ui';
import { BillingChip, n, Pager } from '../parts';
import styles from '../admin.module.css';

/** Every org: searched by its name, its id or a member’s email; filtered by plan. */
export function OrgsPage() {
  const [typed, setTyped] = useState('');
  const [filter, setFilter] = useState<OrgFilter>({});
  const orgs = useAdminOrgs(filter);
  const plans = useAdminPlans();
  const planOptions = [{ value: '', label: 'Any plan' }, ...(plans.data ?? []).map((p) => ({ value: p.name, label: p.name }))];
  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilter((f) => ({ ...f, q: typed.trim() || undefined, offset: 0 }));
  };
  const page = orgs.data;

  return (
    <div className={styles.page}>
      <PageHeader title="Organisations" description="Each org’s plan, people, Ada use and where its sign-up came from." />
      <form className={styles.filters} onSubmit={search} role="search">
        <TextField label="Search" placeholder="A name, an org id or a member’s email" value={typed} onChange={(e) => setTyped(e.target.value)} />
        <Select label="Plan" value={filter.plan ?? ''} options={planOptions} onChange={(e) => setFilter((f) => ({ ...f, plan: e.target.value || undefined, offset: 0 }))} />
        <Button type="submit" icon="search">
          Search
        </Button>
      </form>
      {orgs.isPending && <LoadingCard />}
      <ApiErrorNotice error={orgs.error} />
      {page?.orgs.length === 0 && <EmptyState icon="team" title="No organisations match" />}
      {page && page.orgs.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Organisations">
              <thead>
                <tr>
                  <th>Organisation</th>
                  <th>Plan</th>
                  <th className={styles.num}>Members</th>
                  <th className={styles.num}>Models</th>
                  <th className={styles.num}>Precedents</th>
                  <th className={styles.num}>Reads this month</th>
                  <th>Sign-up source</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {page.orgs.map((org) => (
                  <tr key={org.id}>
                    <td>
                      <Link to={`/admin/orgs/${org.id}`}>{org.name}</Link>
                      {org.suspended && (
                        <>
                          {' '}
                          <Chip tone="red">Suspended</Chip>
                        </>
                      )}
                    </td>
                    <td>
                      <div className={styles.chips}>
                        {`${org.plan} v${org.plan_version}`}
                        <BillingChip status={org.billing_status} />
                      </div>
                    </td>
                    <td className={styles.num}>{n(org.members)}</td>
                    <td className={styles.num}>{n(org.models)}</td>
                    <td className={styles.num}>{n(org.precedents)}</td>
                    <td className={styles.num}>{n(org.reads_month)}</td>
                    <td>{org.source ?? <span className={styles.meta}>Untagged</span>}</td>
                    <td className={styles.num}>{date(org.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager offset={page.offset} limit={page.limit} total={page.total} onMove={(offset) => setFilter((f) => ({ ...f, offset }))} />
        </Card>
      )}
    </div>
  );
}
