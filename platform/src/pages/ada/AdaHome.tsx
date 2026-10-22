import { Link, useNavigate } from 'react-router';
import { useAdaModels, useAdaUsage } from '@/api/ada';
import { useSession } from '@/api/session';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date, plural } from '@/lib/format';
import { Button, Card, Chip, CopyField, EmptyState, LoadingCard } from '@/ui';
import { PrecedentsMeter } from './AdaUsagePage';
import styles from './ada.module.css';

/** Home, with Ada Cloud on: the org's models, what they use of the plan, and the connector to add in Claude. */
export function AdaHome() {
  const navigate = useNavigate();
  const session = useSession();
  const models = useAdaModels();
  const usage = useAdaUsage();
  const connector = session.data ? `${session.data.serverUrl}/mcp` : null;

  const newModel = (
    <Button variant="primary" icon="plus" onClick={() => navigate('/models/new')}>
      New model
    </Button>
  );

  return (
    <>
      <PageHeader title="Home" description="Your Ada models, what they use of your plan, and how Claude reaches them." actions={newModel} />
      <div className={styles.stack}>
        <div className={styles.grid}>
          <Card>
            <h2 className={styles.cardTitle}>Connect Claude</h2>
            {connector && <CopyField value={connector} label="connector URL" />}
            <span className={styles.meta}>Add it in Claude as a custom connector. You’ll be asked to allow it once.</span>
          </Card>
          <Card>
            <div className={styles.leverHead}>
              <h2 className={styles.cardTitle}>Usage</h2>
              {usage.data?.plan && <Chip tone="violet">{usage.data.plan}</Chip>}
            </div>
            {usage.isPending && <LoadingCard lines={2} />}
            <ApiErrorNotice error={usage.error} />
            {usage.data && <PrecedentsMeter usage={usage.data} />}
            <Link to="/usage" className={styles.meta}>
              See usage
            </Link>
          </Card>
        </div>

        {models.isPending && <LoadingCard />}
        <ApiErrorNotice error={models.error} />
        {models.data?.length === 0 && (
          <EmptyState icon="model" title="No models yet" action={newModel}>
            Describe your cases once as a spec, load your history, and ask. Or ask Claude to make one with the connector.
          </EmptyState>
        )}
        {models.data && models.data.length > 0 && (
          <List label="Models">
            {models.data.map((model) => (
              <Row
                key={model.id}
                title={
                  <Link to={`/models/${encodeURIComponent(model.name)}`} className={styles.link}>
                    {model.name}
                  </Link>
                }
                meta={`Version ${model.version} · made ${date(model.created_at)}`}
                actions={<span className={styles.num}>{plural(model.precedents, 'precedent')}</span>}
              />
            ))}
          </List>
        )}
      </div>
    </>
  );
}
