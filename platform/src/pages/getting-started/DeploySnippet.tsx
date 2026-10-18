import { useState } from 'react';
import { CodeBlock, Select, TextField } from '@/ui';
import {
  composeCommands,
  defaultOptions,
  docsUrl,
  dotEnv,
  helmCommand,
  image,
  sizes,
  terraformModule,
  type Cloud,
  type Deployment,
  type Size,
  type SnippetOptions,
} from './snippets';
import styles from './GettingStarted.module.css';

const clouds: ReadonlyArray<{ value: Cloud; label: string }> = [
  { value: 'aws', label: 'AWS' },
  { value: 'gcp', label: 'GCP' },
];

/** The chosen option's files and commands, filled in with the registration's env. */
export function DeploySnippet({ deployment, env }: { deployment: Deployment; env: Record<string, string> }) {
  const [options, setOptions] = useState<SnippetOptions>(defaultOptions);
  const set = (change: Partial<SnippetOptions>) => setOptions((current) => ({ ...current, ...change }));

  if (deployment === 'compose') {
    return (
      <div className={styles.part}>
        <h3 className={styles.subTitle}>Run it with Docker Compose</h3>
        <span className={styles.meta}>Save this as .env beside the compose file:</span>
        <CodeBlock code={dotEnv(env)} label=".env" />
        <CodeBlock code={composeCommands} label="commands" />
        <Note />
      </div>
    );
  }

  const size = <Select label="Size" value={options.size} onChange={(e) => set({ size: e.target.value as Size })} options={sizes} />;

  if (deployment === 'helm') {
    return (
      <div className={styles.part}>
        <h3 className={styles.subTitle}>Install the Helm chart</h3>
        <div className={styles.formRow}>
          {size}
          <TextField label="Ingress class" value={options.ingressClass} onChange={(e) => set({ ingressClass: e.target.value })} mono />
        </div>
        <CodeBlock code={helmCommand(env, options)} label="helm install" />
        <Note />
      </div>
    );
  }

  return (
    <div className={styles.part}>
      <h3 className={styles.subTitle}>Add the Terraform module</h3>
      <div className={styles.formRow}>
        <Select label="Cloud" value={options.cloud} onChange={(e) => set({ cloud: e.target.value as Cloud })} options={clouds} />
        {size}
      </div>
      {options.cloud === 'gcp' && (
        <div className={styles.formRow}>
          <TextField label="Project" value={options.gcpProject} onChange={(e) => set({ gcpProject: e.target.value })} placeholder="your-project-id" mono />
          <TextField label="Region" value={options.gcpRegion} onChange={(e) => set({ gcpRegion: e.target.value })} mono />
        </div>
      )}
      <CodeBlock code={terraformModule(env, options)} label="Terraform module" />
      <span className={styles.meta}>Then run terraform init and terraform apply. It makes one VM.</span>
      <Note />
    </div>
  );
}

function Note() {
  return (
    <span className={styles.meta}>
      It runs the image {image}. The <a href={docsUrl}>self-hosting docs</a> cover TLS, the sandbox’s needs and upgrades.
    </span>
  );
}
