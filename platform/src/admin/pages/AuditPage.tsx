import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { useAdminAudit, type AuditFilter } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { stamp } from '@/lib/format';
import { Button, Card, Chip, EmptyState, LoadingCard, TextField } from '@/ui';
import styles from '../admin.module.css';

/** Every request staff made of the staff view: who, what, when, which org, and how it ended. */
export function AuditPage() {
  const [typed, setTyped] = useState({ by: '', action: '' });
  const [filter, setFilter] = useState<AuditFilter>({});
  const audit = useAdminAudit(filter);
  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilter({ by: typed.by.trim() || undefined, action: typed.action.trim() || undefined });
  };
  return (
    <div className={styles.page}>
      <PageHeader title="Audit log" description="Kept for every page staff open here and every action they take. Staff can’t change it." />
      <form className={styles.filters} onSubmit={search} role="search">
        <TextField label="Staff member" placeholder="support@glyphh.ai" value={typed.by} onChange={(e) => setTyped((t) => ({ ...t, by: e.target.value }))} />
        <TextField label="Action" placeholder="adminSuspendOrg" value={typed.action} onChange={(e) => setTyped((t) => ({ ...t, action: e.target.value }))} />
        <Button type="submit" icon="search">
          Filter
        </Button>
      </form>
      {audit.isPending && <LoadingCard />}
      <ApiErrorNotice error={audit.error} />
      {audit.data?.entries.length === 0 && <EmptyState icon="logs" title="Nothing recorded" />}
      {audit.data && audit.data.entries.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Audit log">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Staff</th>
                  <th>Action</th>
                  <th>Organisation</th>
                  <th>Detail</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.entries.map((e) => (
                  <tr key={e.id}>
                    <td className={styles.num}>{stamp(e.at)}</td>
                    <td>{e.staff_email}</td>
                    <td className={styles.mono}>{e.action}</td>
                    <td className={styles.mono}>{e.org_id ? <Link to={`/admin/orgs/${e.org_id}`}>{e.org_id}</Link> : '–'}</td>
                    <td className={styles.mono}>{JSON.stringify(e.detail)}</td>
                    <td>
                      <Chip tone={e.outcome === 'ok' ? 'green' : 'amber'}>{e.outcome}</Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {audit.data.next_before && (
            <div className={styles.pager}>
              <span />
              <Button size="sm" onClick={() => setFilter((f) => ({ ...f, before: audit.data!.next_before! }))}>
                Older
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
