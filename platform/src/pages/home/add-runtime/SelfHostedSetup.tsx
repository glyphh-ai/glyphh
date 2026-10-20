import { useState, type FormEvent } from 'react';
import { useRegisterSelfRuntime } from '@/api/queries';
import type { NewSelfRuntime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, CopyField, TextField } from '@/ui';
import { Connect } from './Connect';
import { useFooterPrimary, type OnPrimary } from './footer';
import { DeploySnippet } from './DeploySnippet';
import { connectorUrl, docsUrl, hostOf, isHostFor, localHost, localRuntimeUrl, requirements, type Deployment } from './snippets';
import styles from './AddRuntime.module.css';

type SelfHostedSetupProps = {
  deployment: Deployment;
  /** Kept by the dialog, so changing the option keeps the runtime just registered. */
  registered: NewSelfRuntime | null;
  onRegistered: (runtime: NewSelfRuntime | null) => void;
  /** Register runtime goes in the dialog's footer. */
  onPrimary: OnPrimary;
};

/** What the way needs, then register a runtime you run yourself, then paste what it needs where it runs. */
export function SelfHostedSetup({ deployment, registered, onRegistered, onPrimary }: SelfHostedSetupProps) {
  const needs = (
    <p className={styles.needs}>
      <strong>What you need:</strong> {requirements[deployment]}
    </p>
  );
  if (!registered) {
    return (
      <div className={styles.stack}>
        {needs}
        <RegisterForm deployment={deployment} onRegistered={onRegistered} onPrimary={onPrimary} />
      </div>
    );
  }

  const host = registered.env.RROTOR_PUBLIC_HOST ?? hostOf(registered.public_url);
  return (
    <div className={styles.stack}>
      {needs}
      <div className={styles.part}>
        <h3 className={styles.subTitle}>Runtime token for {registered.name}</h3>
        <CopyField value={registered.token} label="runtime token" />
        <span className={styles.meta}>Shown once. It is in the command below too; keep both out of version control.</span>
      </div>
      <DeploySnippet deployment={deployment} env={registered.env} />
      {deployment === 'local' ? (
        <Connect
          title="Connect"
          runtimeUrl={localRuntimeUrl(host)}
          note="Claude’s connector needs a public HTTPS host: run it with Docker or Helm on a server for that."
        />
      ) : (
        <Connect title="Connect" connector={connectorUrl(host)} note={`Once it answers at ${host}, add this in Claude as a custom connector.`} />
      )}
      <div className={styles.actions}>
        <Button variant="ghost" icon="plus" onClick={() => onRegistered(null)}>
          Register another
        </Button>
      </div>
    </div>
  );
}

type RegisterFormProps = { deployment: Deployment; onRegistered: (runtime: NewSelfRuntime) => void; onPrimary: OnPrimary };

function RegisterForm({ deployment, onRegistered, onPrimary }: RegisterFormProps) {
  const register = useRegisterSelfRuntime();
  const local = deployment === 'local';
  const [name, setName] = useState('');
  // Untouched, this computer's host is 127.0.0.1; any other way starts empty.
  const [typed, setTyped] = useState<string | null>(null);
  const hostInput = typed ?? (local ? localHost : '');
  const host = hostOf(hostInput);
  const valid = isHostFor(deployment, host);
  useFooterPrimary(onPrimary, { form: 'register-runtime', label: 'Register runtime', ready: !!name.trim() && valid, pending: register.isPending });
  const hostError = hostInput.trim() && !valid ? (local ? 'Use a host or an IP address, such as 127.0.0.1.' : 'Use the host alone, such as rrotor.acme.com.') : undefined;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    register.mutate({ name: name.trim(), public_url: `https://${host}` }, { onSuccess: onRegistered });
  };

  return (
    <form id="register-runtime" className={styles.form} onSubmit={submit} aria-label="Register a runtime">
      <span className={styles.meta}>
        Register it first: you get its token and the command to paste. See the <a href={docsUrl}>self-hosting docs</a> for what the host needs.
      </span>
      <div className={styles.formRow}>
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder={local ? 'My laptop' : 'Acme production'} />
        <TextField
          label={local ? 'Host' : 'Public host'}
          value={hostInput}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={local ? localHost : 'rrotor.acme.com'}
          mono
          hint={local ? '127.0.0.1 (this computer only)' : 'The DNS name that will point at the server, e.g. rrotor.acme.com'}
          error={hostError}
        />
      </div>
      <ApiErrorNotice error={register.error} />
    </form>
  );
}
