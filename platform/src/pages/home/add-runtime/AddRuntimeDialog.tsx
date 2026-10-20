import { useState } from 'react';
import { useHosting, usePlans } from '@/api/queries';
import type { NewSelfRuntime } from '@/api/types';
import { hostingPlansText } from '@/pages/settings/billing/plans';
import { Button, Dialog, LoadingCard } from '@/ui';
import type { OnPrimary, Primary } from './footer';
import { HostedChoice } from './HostedChoice';
import { SelfHostedSetup } from './SelfHostedSetup';
import { docsUrl, type Deployment } from './snippets';
import styles from './AddRuntime.module.css';

type Where = 'hosted' | Deployment;

type Choice = { value: Where; title: string; text: string };

/** Running rrotor yourself: free on every plan, and the way to run it while Glyphh hosts nothing. */
const selfHosted: ReadonlyArray<Choice> = [
  { value: 'local', title: 'This computer', text: 'Free. Try it on your laptop; no HTTPS, so Claude cannot connect yet.' },
  { value: 'compose', title: 'Docker', text: 'Free. One command on a Linux machine.' },
  { value: 'helm', title: 'Helm', text: 'Free. Your Kubernetes cluster: EKS, GKE or AKS.' },
  { value: 'terraform', title: 'Terraform', text: 'Free. One VM on AWS or GCP.' },
];

/** Where rrotor can run: Glyphh hosted first when Glyphh hosts machines (on the plans with them), else only yourself. */
const choices = (hosting: boolean, plans: string): ReadonlyArray<Choice> =>
  hosting
    ? [{ value: 'hosted', title: 'Glyphh hosted', text: `On ${plans}. Glyphh runs it for you. Make a machine and connect.` }, ...selfHosted]
    : selfHosted;

/**
 * Adding a runtime, over the Runtimes page: where it runs, registering it, its token once, the option's command,
 * then the connector URL and the SDKs. Its state goes when it closes.
 */
export function AddRuntimeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  // The form that makes the runtime, while there is one: its button goes in the footer, after Cancel.
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
  const plans = usePlans();
  const known = useHosting();
  const hosting = known === true;
  // Until the person picks, the first option: Glyphh hosted when it is offered, else this computer.
  const [picked, setWhere] = useState<Where | null>(null);
  const where: Where = picked === 'hosted' && !hosting ? 'local' : (picked ?? (hosting ? 'hosted' : 'local'));
  const [registered, setRegistered] = useState<NewSelfRuntime | null>(null);

  if (known === undefined) return <LoadingCard lines={3} />;

  return (
    <div className={styles.stack}>
      <fieldset className={styles.choices}>
        <legend className="visually-hidden">Where rrotor runs</legend>
        {choices(hosting, hostingPlansText(plans.data)).map((choice) => (
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
      {where === 'hosted' ? (
        <HostedChoice onPrimary={onPrimary} />
      ) : (
        <SelfHostedSetup deployment={where} registered={registered} onRegistered={setRegistered} onPrimary={onPrimary} />
      )}
    </div>
  );
}
