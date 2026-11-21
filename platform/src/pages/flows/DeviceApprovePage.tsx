import { useSearchParams } from 'react-router';
import { useConsent, useSession } from '@/api/session';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { ButtonLink, Skeleton } from '@/ui';
import { ConsentError } from './ConsentError';
import styles from './flows.module.css';

/** Signed in: the person approves or denies the install that showed the code. */
export function DeviceApprovePage() {
  const [params] = useSearchParams();
  const consent = params.get('consent');
  if (!consent) return <ConsentError error={null} />;
  return <DeviceApprove consent={consent} />;
}

function DeviceApprove({ consent }: { consent: string }) {
  const session = useSession();
  const serverUrl = session.data?.serverUrl;
  const query = useConsent(serverUrl, consent);
  const data = query.data;

  const answerUrl = (decision: 'approve' | 'deny') => `${serverUrl}/auth/approve?consent=${encodeURIComponent(consent)}&decision=${decision}`;

  if (query.error) return <ConsentError error={query.error} />;
  if (!data) {
    return (
      <AuthLayout title="One moment">
        <Skeleton height={80} />
      </AuthLayout>
    );
  }
  if (data.kind !== 'device') return <ConsentError error={null} />;

  return (
    <AuthLayout title="Approve this sign-in?">
      <p className={styles.text}>
        <span className={styles.strong}>
          {data.name} ({data.surface})
        </span>{' '}
        wants to sign in as <span className={styles.strong}>{data.email}</span>.
      </p>
      <div className={styles.code} aria-label="Code">
        {data.code}
      </div>
      <div className={styles.actions}>
        <ButtonLink href={answerUrl('deny')}>Deny</ButtonLink>
        <ButtonLink variant="primary" href={answerUrl('approve')}>
          Approve
        </ButtonLink>
      </div>
    </AuthLayout>
  );
}
