import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { useAdminUsers, type PeopleFilter } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, date } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard, Select, TextField } from '@/ui';
import { Pager } from '../parts';
import styles from '../admin.module.css';

const providers = [
  { value: '', label: 'Any sign-in' },
  { value: 'google', label: 'Google' },
  { value: 'github', label: 'GitHub' },
];

/** Every person: their org, how they sign in, when they joined and when they were last seen. */
export function UsersPage() {
  const [typed, setTyped] = useState('');
  const [filter, setFilter] = useState<PeopleFilter>({});
  const people = useAdminUsers(filter);
  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilter((f) => ({ ...f, q: typed.trim() || undefined, offset: 0 }));
  };
  const page = people.data;
  return (
    <div className={styles.page}>
      <PageHeader title="People" description="Last seen is their newest use of an install, the platform or a connector." />
      <form className={styles.filters} onSubmit={search} role="search">
        <TextField label="Search" placeholder="An email or a name" value={typed} onChange={(e) => setTyped(e.target.value)} />
        <Select label="Signs in with" value={filter.provider ?? ''} options={providers} onChange={(e) => setFilter((f) => ({ ...f, provider: e.target.value || undefined, offset: 0 }))} />
        <Button type="submit" icon="search">
          Search
        </Button>
      </form>
      {people.isPending && <LoadingCard />}
      <ApiErrorNotice error={people.error} />
      {page?.people.length === 0 && <EmptyState icon="user" title="No one matches" />}
      {page && page.people.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="People">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Organisation</th>
                  <th>Role</th>
                  <th>Signs in with</th>
                  <th>Joined</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {page.people.map((p) => (
                  <tr key={p.id}>
                    <td>{p.email}</td>
                    <td>{p.name ?? '–'}</td>
                    <td>
                      <Link to={`/admin/orgs/${p.org_id}`}>{p.org_name}</Link>
                    </td>
                    <td>{p.role}</td>
                    <td>{p.providers.length ? p.providers.join(', ') : '–'}</td>
                    <td className={styles.num}>{date(p.created_at)}</td>
                    <td className={styles.num}>{p.last_seen_at ? ago(p.last_seen_at) : 'Never'}</td>
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
