import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { startUrl, useProviders, useSession } from '@/api/session';
import { ProviderButtons } from '@/components/ProviderButtons';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { ErrorNotice, Skeleton } from '@/ui';
import { pendingLogin } from './pendingLogin';
import styles from './flows.module.css';

/** A client (Claude, an app, or this platform) asks to use the person's account: they pick how to sign in. */
export function AuthorizePage() {
  const [params] = useSearchParams();
  const oauth = params.get('oauth');
  if (!oauth) {
    return (
      <AuthLayout title="Sign-in link incomplete">
        <ErrorNotice message="This link is missing part of the sign-in. Start again from the app that sent you here." />
      </AuthLayout>
    );
  }
  return <Authorize oauth={oauth} client={params.get('client') ?? 'An app'} />;
}

function Authorize({ oauth, client }: { oauth: string; client: string }) {
  const session = useSession();
  const providers = useProviders();
  const serverUrl = session.data?.serverUrl;

  const start = (provider: string, email?: string) => startUrl(serverUrl ?? '', provider, `oauth=${encodeURIComponent(oauth)}`, email);

  // The platform's own log-in: the provider (and, for single sign-on, the work email) was chosen on /login a moment ago.
  const own = session.data && client === session.data.clientName ? pendingLogin() : null;
  useEffect(() => {
    if (own) window.location.replace(start(own.provider, own.email));
  });

  if (own) {
    return (
      <AuthLayout title="Logging you in">
        <Skeleton height={44} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={`${client} wants to use your Glyphh account`}>
      <p className={styles.text}>Sign in to choose whether to allow it.</p>
      {(providers.isPending || session.isPending) && <Skeleton height={44} />}
      {providers.data && serverUrl && <ProviderButtons providers={providers.data.providers} sso={providers.data.sso} href={start} />}
    </AuthLayout>
  );
}
