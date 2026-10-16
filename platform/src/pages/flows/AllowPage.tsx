import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { useConsent, useSession } from '@/api/session';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { ButtonLink, Skeleton } from '@/ui';
import { ConsentError } from './ConsentError';
import { forgetLogin, pendingLogin } from './pendingLogin';
import styles from './flows.module.css';

/** After signing in: the person allows or denies the client. Each answer is a full page load to the server. */
export function AllowPage() {
  const [params] = useSearchParams();
  const consent = params.get('consent');
  if (!consent) return <ConsentError error={null} />;
  return <Allow consent={consent} />;
}

function Allow({ consent }: { consent: string }) {
  const session = useSession();
  const serverUrl = session.data?.serverUrl;
  const query = useConsent(serverUrl, consent);
  const data = query.data;

  const answerUrl = (decision: 'allow' | 'deny') =>
    `${serverUrl}/auth/oauth/allow?consent=${encodeURIComponent(consent)}&decision=${decision}`;

  // The platform's own log-in allows itself: the person chose to log in here a moment ago.
  const own = data?.kind === 'oauth' && data.client === session.data?.clientName && pendingLogin() !== null;
  useEffect(() => {
    if (!own) return;
    forgetLogin();
    window.location.replace(answerUrl('allow'));
  });

  if (query.error) return <ConsentError error={query.error} />;
  if (!data || own) {
    return (
      <AuthLayout title={own ? 'Logging you in' : 'One moment'}>
        <Skeleton height={80} />
      </AuthLayout>
    );
  }
  if (data.kind !== 'oauth') return <ConsentError error={null} />;

  return (
    <AuthLayout title={`${data.client} wants to use your Glyphh account`}>
      <dl className={styles.details}>
        <dt>Signed in as</dt>
        <dd>{data.email}</dd>
        <dt>Reaches</dt>
        <dd className={styles.mono}>{data.resource}</dd>
        {data.returns_to && (
          <>
            <dt>Then back to</dt>
            <dd>{data.returns_to}</dd>
          </>
        )}
      </dl>
      <div className={styles.actions}>
        <ButtonLink href={answerUrl('deny')}>Deny</ButtonLink>
        <ButtonLink variant="primary" href={answerUrl('allow')}>
          Allow
        </ButtonLink>
      </div>
    </AuthLayout>
  );
}
