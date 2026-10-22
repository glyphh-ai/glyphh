import { Link, useNavigate } from 'react-router';
import { useAdaModels } from '@/api/ada';
import { AdaErrorNotice } from './AdaErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard } from '@/ui';
import styles from './ada.module.css';

/** Models, with Ada Cloud on: every model of the org, its active version and the precedents it holds. */
export function AdaModelsPage() {
  const navigate = useNavigate();
  const models = useAdaModels();
  const newModel = (
    <Button variant="primary" icon="plus" onClick={() => navigate('/models/new')}>
      New model
    </Button>
  );

  return (
    <>
      <PageHeader title="Models" description="Each model decides from its own precedents. Open one to change it, load cases, try it or tune it." actions={newModel} />
      {models.isPending && <LoadingCard />}
      <AdaErrorNotice error={models.error} />
      {models.data?.length === 0 && (
        <EmptyState icon="model" title="No models yet" action={newModel}>
          Describe your cases once as a spec. Claude can write it with you through the connector.
        </EmptyState>
      )}
      {models.data && models.data.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col">Version</th>
                  <th scope="col">Precedents</th>
                  <th scope="col">Made</th>
                </tr>
              </thead>
              <tbody>
                {models.data.map((model) => (
                  <tr key={model.id}>
                    <td>
                      <Link to={`/models/${encodeURIComponent(model.name)}`} className={styles.link}>
                        {model.name}
                      </Link>
                    </td>
                    <td className={styles.num}>v{model.version}</td>
                    <td className={styles.num}>{model.precedents.toLocaleString('en-GB')}</td>
                    <td>{date(model.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
