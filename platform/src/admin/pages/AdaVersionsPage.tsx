import { useAdminAdaVersions } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Card, LoadingCard } from '@/ui';
import { n } from '../parts';
import styles from '../admin.module.css';

/** Live models by the Ada version their active version runs; models made before Ada versions count apart. */
export function AdaVersionsPage() {
  const versions = useAdminAdaVersions();
  const data = versions.data;
  return (
    <div className={styles.page}>
      <PageHeader title="Ada versions" description="Each live model runs the Ada version its active version was made with." />
      {versions.isPending && <LoadingCard />}
      <ApiErrorNotice error={versions.error} />
      {data && !data.versioned && <p className={styles.meta}>No model names its Ada version yet: Ada versions have not reached the cloud’s models.</p>}
      {data && data.versions.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Models by Ada version">
              <thead>
                <tr>
                  <th>Ada version</th>
                  <th>Kernel</th>
                  <th className={styles.num}>Models</th>
                  <th className={styles.num}>Orgs</th>
                  <th className={styles.num}>Precedents</th>
                </tr>
              </thead>
              <tbody>
                {data.versions.map((v) => (
                  <tr key={v.ada ?? 'none'}>
                    <td className={styles.mono}>{v.ada ?? 'Before Ada versions'}</td>
                    <td className={styles.mono}>{v.kernels.join(', ') || '–'}</td>
                    <td className={styles.num}>{n(v.models)}</td>
                    <td className={styles.num}>{n(v.orgs)}</td>
                    <td className={styles.num}>{n(v.precedents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
