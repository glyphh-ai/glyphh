import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';
import { startUrl, useProviders, useSession } from '@/api/session';
import { ProviderButtons } from '@/components/ProviderButtons';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { Button, Skeleton, TextField } from '@/ui';
import styles from './flows.module.css';

/** Claude Code shows a code and this link: the person checks the code matches, then signs in. */
export function DevicePage() {
  const [params, setParams] = useSearchParams();
  const code = params.get('code');
  const session = useSession();
  const providers = useProviders();
  const [typed, setTyped] = useState('');
  const serverUrl = session.data?.serverUrl;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (typed.trim()) setParams({ code: typed.trim().toUpperCase() });
  };

  if (!code) {
    return (
      <AuthLayout title="Enter the code from Claude">
        <form className={styles.form} onSubmit={submit}>
          <TextField label="Code" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="ABCD-EFGH" mono autoComplete="one-time-code" autoFocus />
          <Button type="submit" variant="primary" disabled={!typed.trim()}>
            Continue
          </Button>
        </form>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Sign in to Claude with Glyphh">
      <p className={styles.text}>Check this matches the code Claude is showing.</p>
      <div className={styles.code} aria-label="Code">
        {code}
      </div>
      {(providers.isPending || session.isPending) && <Skeleton height={44} />}
      {providers.data && serverUrl && (
        <ProviderButtons
          providers={providers.data.providers}
          sso={providers.data.sso}
          href={(p, email) => startUrl(serverUrl, p, `code=${encodeURIComponent(code)}`, email)}
        />
      )}
    </AuthLayout>
  );
}
