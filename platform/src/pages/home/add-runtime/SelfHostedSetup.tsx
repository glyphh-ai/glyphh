import { useState, type FormEvent } from 'react';
import { useRegisterSelfRuntime } from '@/api/queries';
import type { NewSelfRuntime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, CopyField, TextField } from '@/ui';
import { Connect } from './Connect';
import { DeploySnippet } from './DeploySnippet';
import { connectorUrl, docsUrl, hostOf, isHost, type Deployment } from './snippets';
import styles from './AddRuntime.module.css';

type SelfHostedSetupProps = {
  deployment: Deployment;
  /** Kept by the dialog, so changing the option keeps the runtime just registered. */
  registered: NewSelfRuntime | null;
  onRegistered: (runtime: NewSelfRuntime | null) => void;
};

/** Register a runtime you run yourself, then paste what it needs where it runs. */
export function SelfHostedSetup({ deployment, registered, onRegistered }: SelfHostedSetupProps) {
  if (!registered) return <RegisterForm onRegistered={onRegistered} />;

  const host = registered.env.RROTOR_PUBLIC_HOST ?? hostOf(registered.public_url);
  return (
    <div className={styles.stack}>
      <div className={styles.part}>
        <h3 className={styles.subTitle}>Runtime token for {registered.name}</h3>
        <CopyField value={registered.token} label="runtime token" />
        <span className={styles.meta}>Shown once. It is in the snippet below too; keep both out of version control.</span>
      </div>
      <DeploySnippet deployment={deployment} env={registered.env} />
      <Connect title="Connect" connector={connectorUrl(host)} note={`Once it answers at ${host}, add this in Claude as a custom connector.`} />
      <div className={styles.actions}>
        <Button variant="ghost" icon="plus" onClick={() => onRegistered(null)}>
          Register another
        </Button>
      </div>
    </div>
  );
}

function RegisterForm({ onRegistered }: { onRegistered: (runtime: NewSelfRuntime) => void }) {
  const register = useRegisterSelfRuntime();
  const [name, setName] = useState('');
  const [hostInput, setHostInput] = useState('');
  const host = hostOf(hostInput);
  const hostError = hostInput.trim() && !isHost(host) ? 'Use the host alone, such as rrotor.acme.com.' : undefined;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    register.mutate({ name: name.trim(), public_url: `https://${host}` }, { onSuccess: onRegistered });
  };

  return (
    <form className={styles.form} onSubmit={submit} aria-label="Register a runtime">
      <span className={styles.meta}>
        Register it first: you get its token and the settings to paste. See the <a href={docsUrl}>self-hosting docs</a> for what the host needs.
      </span>
      <div className={styles.formRow}>
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Acme production" />
        <TextField
          label="Public host"
          value={hostInput}
          onChange={(e) => setHostInput(e.target.value)}
          placeholder="rrotor.acme.com"
          mono
          hint="Where it will answer. TLS ends in front of it."
          error={hostError}
        />
      </div>
      <ApiErrorNotice error={register.error} />
      <div className={styles.actions}>
        <Button variant="primary" type="submit" loading={register.isPending} disabled={!name.trim() || !isHost(host)}>
          Register runtime
        </Button>
      </div>
    </form>
  );
}
