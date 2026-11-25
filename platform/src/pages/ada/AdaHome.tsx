import { useNavigate } from 'react-router';
import { useAdaUsage } from '@/api/ada';
import { useBilling, useMe } from '@/api/queries';
import { useSession } from '@/api/session';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ActivityCard } from '@/pages/home/ActivityCard';
import { greetingFor } from '@/pages/home/greeting';
import { HomeStats } from '@/pages/home/HomeStats';
import { Resources } from '@/pages/home/Resources';
import { WhatsNew } from '@/pages/home/WhatsNew';
import styles from '@/pages/home/home.module.css';
import { Button, LoadingCard } from '@/ui';

/**
 * Home: a dashboard, not a list of models (Models is for that). A greeting; the balance, the month's tokens and Ada's
 * requests against the plan; the week's volume; what is new at Glyphh (Ada's releases); and where to go next.
 */
export function AdaHome() {
  const navigate = useNavigate();
  const session = useSession();
  const me = useMe();
  const billing = useBilling();
  const usage = useAdaUsage();
  const connector = session.data ? `${session.data.serverUrl}/mcp` : null;

  const actions = (
    <>
      <Button icon="key" onClick={() => navigate('/keys')}>
        API keys
      </Button>
      <Button variant="primary" icon="plus" onClick={() => navigate('/models/new')}>
        New model
      </Button>
    </>
  );

  return (
    <>
      <PageHeader title={greetingFor(me.data?.name)} description="Your month on Glyphh, and what’s new." actions={actions} />
      <div className={styles.stack}>
        {billing.isPending && <LoadingCard lines={3} />}
        <ApiErrorNotice error={billing.error} />
        {billing.data && <HomeStats billing={billing.data} usage={usage.data} isAdmin={me.data?.role === 'admin'} />}
        {billing.data && <ActivityCard tokens={Boolean(billing.data.tokens)} />}
        <WhatsNew />
        <Resources connector={connector} />
      </div>
    </>
  );
}
