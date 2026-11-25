import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { loginUrl, useProviders, useSession } from '@/api/session';
import { ProviderButtons } from '@/components/ProviderButtons';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { privacyUrl, termsUrl } from '@/lib/links';
import { ErrorNotice, Skeleton } from '@/ui';
import { rememberLogin } from './pendingLogin';

const failures: Record<string, string> = {
  denied: 'You chose not to sign in.',
  expired: 'The sign-in took too long. Try again.',
  state: 'That sign-in did not start here. Try again.',
};

export function LoginPage() {
  const session = useSession();
  const providers = useProviders();
  const [params] = useSearchParams();
  const returnTo = params.get('returnTo') ?? '/';
  const failed = params.get('failed');

  useEffect(() => {
    if (session.data?.signedIn) window.location.replace(returnTo.startsWith('/') && !returnTo.startsWith('//') ? returnTo : '/');
  }, [session.data?.signedIn, returnTo]);

  return (
    <AuthLayout
      title="Log in to Glyphh"
      footer={
        <>
          By logging in, you agree to our <a href={termsUrl}>Terms of Service</a> and <a href={privacyUrl}>Privacy Policy</a>.
        </>
      }
    >
      {failed && <ErrorNotice message={failures[failed] ?? 'The sign-in could not finish. Try again.'} />}
      {providers.isPending && (
        <>
          <Skeleton height={44} />
          <Skeleton height={44} />
        </>
      )}
      {providers.error && <ErrorNotice message="Glyphh could not be reached. Try again in a moment." />}
      {providers.data && (
        <ProviderButtons
          providers={providers.data.providers}
          sso={providers.data.sso}
          verb="Log in with"
          href={() => loginUrl(returnTo)}
          onChoose={rememberLogin}
        />
      )}
    </AuthLayout>
  );
}
