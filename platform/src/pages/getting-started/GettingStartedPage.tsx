import { useState, type ReactNode } from 'react';
import type { NewSelfRuntime } from '@/api/types';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Card, CopyField } from '@/ui';
import { HostedChoice } from './HostedChoice';
import { SelfHostedSetup } from './SelfHostedSetup';
import { SelfRuntimes } from './SelfRuntimes';
import { docsUrl, type Deployment } from './snippets';
import styles from './GettingStarted.module.css';

type Where = 'hosted' | Deployment;

const choices: ReadonlyArray<{ value: Where; title: string; text: string }> = [
  { value: 'hosted', title: 'Glyphh hosted', text: 'Glyphh runs it for you. Make a machine and connect.' },
  { value: 'compose', title: 'Docker Compose', text: 'One VM or your own machine.' },
  { value: 'helm', title: 'Helm', text: 'Your Kubernetes cluster: EKS, GKE or AKS.' },
  { value: 'terraform', title: 'Terraform', text: 'One VM on AWS or GCP.' },
];

export function GettingStartedPage() {
  const [where, setWhere] = useState<Where>('hosted');
  const [registered, setRegistered] = useState<NewSelfRuntime | null>(null);

  return (
    <>
      <PageHeader
        title="Getting started"
        description={
          <>
            Install the SDK and the Claude plugin, choose where rrotor runs, then connect Claude. Running it yourself? Read the{' '}
            <a href={docsUrl}>self-hosting docs</a>.
          </>
        }
      />

      <div className={styles.stack}>
        <Card>
          <Step number={1}>Install</Step>
          <div className={styles.grid}>
            <Install title="Python">
              <CopyField value="pip install glyphh-ada" label="pip command" />
            </Install>
            <Install title="Node">
              <CopyField value="npm i @glyphh-ai/ada" label="npm command" />
            </Install>
          </div>
          <Install title="Claude plugin">
            <span className={styles.meta}>In Claude Code, add the Glyphh marketplace, then the Ada plugin:</span>
            <CopyField value="/plugin marketplace add glyphh-ai/glyphh" label="marketplace command" />
            <CopyField value="/plugin install ada@glyphh" label="plugin command" />
          </Install>
        </Card>

        <Card>
          <Step number={2}>Where rrotor runs</Step>
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
          {where === 'hosted' ? (
            <HostedChoice />
          ) : (
            <SelfHostedSetup deployment={where} registered={registered} onRegistered={setRegistered} />
          )}
        </Card>

        <SelfRuntimes />
      </div>
    </>
  );
}

function Step({ number, children }: { number: number; children: ReactNode }) {
  return (
    <h2 className={styles.step}>
      <span className={styles.stepNumber} aria-hidden="true">
        {number}
      </span>
      {children}
    </h2>
  );
}

function Install({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.part}>
      <h3 className={styles.subTitle}>{title}</h3>
      {children}
    </div>
  );
}
