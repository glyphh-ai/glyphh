import { useState } from 'react';
import { Link } from 'react-router';
import { useMe } from '@/api/queries';
import { CodeBlock, Select, TextField } from '@/ui';
import {
  defaultOptions,
  deploymentDocsUrl,
  dockerInstall,
  dockerRun,
  helmCommand,
  image,
  sizes,
  terraformModule,
  type Cloud,
  type Deployment,
  type Size,
  type SnippetOptions,
} from './snippets';
import styles from './AddRuntime.module.css';

const clouds: ReadonlyArray<{ value: Cloud; label: string }> = [
  { value: 'aws', label: 'AWS' },
  { value: 'gcp', label: 'GCP' },
];

/**
 * The chosen option's command, filled in with the registration's env. On a paid plan, the licence key's line,
 * commented out: only an air-gapped node needs it.
 */
export function DeploySnippet({ deployment, env }: { deployment: Deployment; env: Record<string, string> }) {
  const [options, setOptions] = useState<SnippetOptions>(defaultOptions);
  const me = useMe();
  const paid = me.data !== undefined && me.data.plan.price_cents !== 0;
  const set = (change: Partial<SnippetOptions>) => setOptions((current) => ({ ...current, ...change }));
  const size = <Select label="Size" value={options.size} onChange={(e) => set({ size: e.target.value as Size })} options={sizes} />;

  if (deployment === 'compose') {
    const host = env.RROTOR_PUBLIC_HOST;
    return (
      <div className={styles.part}>
        <h3 className={styles.subTitle}>Run it with Docker</h3>
        <span className={styles.meta}>
          Point {host ? <code>{host}</code> : 'the host'}’s DNS at the machine first; the script serves it over HTTPS. Then, on the machine:
        </span>
        <div className={styles.formRow}>{size}</div>
        <CodeBlock code={dockerInstall(env, options.size, paid)} label="install command" />
        <details className={styles.details}>
          <summary className={styles.summary}>HTTPS already in front? Run the image alone:</summary>
          <CodeBlock code={dockerRun(env)} label="docker run command" />
        </details>
        <Note paid={paid} deployment={deployment} />
      </div>
    );
  }

  if (deployment === 'helm') {
    return (
      <div className={styles.part}>
        <h3 className={styles.subTitle}>Install the Helm chart</h3>
        <div className={styles.formRow}>
          {size}
          <TextField label="Ingress class" value={options.ingressClass} onChange={(e) => set({ ingressClass: e.target.value })} mono />
        </div>
        <CodeBlock code={helmCommand(env, options, paid)} label="helm install" />
        <Note paid={paid} deployment={deployment} />
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
      <CodeBlock code={terraformModule(env, options, paid)} label="Terraform module" />
      <span className={styles.meta}>Then run terraform init and terraform apply. It makes one VM.</span>
      <Note paid={paid} deployment={deployment} />
    </div>
  );
}

function Note({ paid, deployment }: { paid: boolean; deployment: Deployment }) {
  return (
    <>
      {paid && (
        <span className={styles.meta}>
          Your licence key reaches rrotor on its own when it links and at its daily heartbeat. Only an air-gapped node needs it set: see{' '}
          <Link to="/licence">Licence</Link>.
        </span>
      )}
      <span className={styles.meta}>
        It runs the image {image}. The <a href={deploymentDocsUrl[deployment]}>self-hosting docs</a> cover TLS, the sandbox’s needs and upgrades.
      </span>
    </>
  );
}
