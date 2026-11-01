import { useState } from 'react';
import type { NewSelfRuntime } from '@/api/types';
import { Button, Dialog } from '@/ui';
import type { OnPrimary, Primary } from './footer';
import { SelfHostedSetup } from './SelfHostedSetup';
import { docsUrl, type Deployment } from './snippets';
import styles from './AddRuntime.module.css';

type Choice = { value: Deployment; title: string; text: string };

/** Where a person runs rrotor themselves: free on every plan. Glyphh hosts none. */
const choices: ReadonlyArray<Choice> = [
  { value: 'local', title: 'This computer', text: 'Free. Try it on your laptop; no HTTPS, so Claude cannot connect yet.' },
  { value: 'compose', title: 'Docker', text: 'Free. One command on a Linux machine.' },
  { value: 'helm', title: 'Helm', text: 'Free. Your Kubernetes cluster: EKS, GKE or AKS.' },
  { value: 'terraform', title: 'Terraform', text: 'Free. One VM on AWS or GCP.' },
];

/**
 * Adding a runtime, over the Runtimes page: where it runs, registering it, its token once, the option's command,
 * then the connector URL and the SDKs. Its state goes when it closes.
 */
export function AddRuntimeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  // The form that registers the runtime, while there is one: its button goes in the footer, after Cancel.
  const [primary, setPrimary] = useState<Primary | null>(null);
  return (
    <Dialog
      open={open}
      size="wide"
      onClose={onClose}
      title="Add a runtime"
      description={
        <>
          Choose where rrotor runs, then connect Claude. Running it yourself is free on every plan: read the{' '}
          <a href={docsUrl}>self-hosting docs</a>.
        </>
      }
      actions={
        primary ? (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" form={primary.form} loading={primary.pending} disabled={!primary.ready}>
              {primary.label}
            </Button>
          </>
        ) : (
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        )
      }
    >
      <AddRuntime onPrimary={setPrimary} />
    </Dialog>
  );
}

function AddRuntime({ onPrimary }: { onPrimary: OnPrimary }) {
  // Until the person picks, this computer.
  const [where, setWhere] = useState<Deployment>('local');
  const [registered, setRegistered] = useState<NewSelfRuntime | null>(null);

  return (
    <div className={styles.stack}>
      <fieldset className={styles.choices}>
        <legend className="visually-hidden">Where rrotor runs</legend>
        {choices.map((choice) => (
          <label key={choice.value} className={styles.choice}>
            <input type="radio" name="where" value={choice.value} checked={where === choice.value} onChange={() => setWhere(choice.value)} />
            <span className={styles.choiceBody}>
              <span className={styles.choiceTitle}>{choice.title}</span>
              <span className={styles.choiceText}>{choice.text}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <div className={styles.divider} />
      <SelfHostedSetup deployment={where} registered={registered} onRegistered={setRegistered} onPrimary={onPrimary} />
    </div>
  );
}
