/**
 * What each self-hosted option needs pasted, filled in from a registration's env. Nothing to clone, and every shell
 * block pastes as is into zsh or bash: no `#` lines (zsh without interactive_comments refuses them); notes go beside
 * the block. Each ends with the health check.
 */

/** The self-hosting docs' hub; each deployment also has its own page. */
export const docsUrl = 'https://docs.glyphh.ai/run-rrotor';
export const image = 'ghcr.io/glyphh-ai/rrotor';
/** The install script for one Linux machine: Docker, rrotor and HTTPS in front of it. */
export const installScriptUrl = 'https://glyphh.ai/install.sh';
/** The Helm chart as released from the public repo. */
export const helmChartUrl = 'https://github.com/glyphh-ai/glyphh/releases/download/rrotor-chart-0.2.0/rrotor-0.2.0.tgz';

/** `local` is this computer: the image alone on port 7777, no HTTPS. */
export type Deployment = 'local' | 'compose' | 'helm' | 'terraform';

export const deploymentDocsUrl: Record<Deployment, string> = {
  local: docsUrl,
  compose: 'https://docs.glyphh.ai/docker-compose',
  helm: 'https://docs.glyphh.ai/helm',
  terraform: 'https://docs.glyphh.ai/terraform',
};

/** What each way needs before registering. */
export const requirements: Record<Deployment, string> = {
  local: 'Docker running on this computer (Docker Desktop, or any Docker).',
  compose: 'A Linux server with Docker and the Compose plugin (docker compose version works), a DNS name pointing at it, ports 80 and 443 open.',
  helm: 'A Kubernetes cluster with an Ingress controller, and kubectl and helm set up for it.',
  terraform: 'An AWS account or a GCP project, and terraform.',
};

export type Cloud = 'aws' | 'gcp';
export type Size = 'small' | 'medium' | 'large';

/** The Terraform module for a cloud, straight from the public repo. */
export const terraformSource = (cloud: Cloud) => `git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/${cloud}?ref=main`;

export const sizes: ReadonlyArray<{ value: Size; label: string }> = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
];

/** The settings a person can change under the snippet; the rest come from the registration. */
export type SnippetOptions = {
  size: Size;
  ingressClass: string;
  cloud: Cloud;
  gcpProject: string;
  gcpRegion: string;
};

export const defaultOptions: SnippetOptions = { size: 'small', ingressClass: 'nginx', cloud: 'aws', gcpProject: '', gcpRegion: 'europe-west2' };

/** This computer's host until the person changes it. */
export const localHost = '127.0.0.1';

/** `rrotor.acme.com` from what a person types: a scheme, a path or a trailing slash are dropped. */
export function hostOf(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/^[a-z]+:\/\//, '')
    .replace(/[/?#].*$/, '');
}

/** A DNS name: at least one dot, nothing but letters, digits, dots, hyphens and a port, and not an IP address. */
export function isHost(host: string): boolean {
  return /^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z][a-z0-9-]*(:\d{1,5})?$/.test(host);
}

/** On this computer, also localhost or an IP address; elsewhere, a DNS name as `isHost`. */
export function isHostFor(deployment: Deployment, host: string): boolean {
  if (deployment !== 'local') return isHost(host);
  return isHost(host) || /^(localhost|\d{1,3}(\.\d{1,3}){3}|\[[0-9a-f:]+\])(:\d{1,5})?$/.test(host);
}

export const connectorUrl = (host: string) => `https://${host}/mcp`;
/** Where the SDKs reach a runtime on this computer. */
export const localRuntimeUrl = (host: string) => `http://${host}:7777`;

/** The last line of every block: waits for rrotor to answer, and fails loudly when it does not. */
export const healthCheck = (base: string) => `curl -fsS --retry 15 --retry-connrefused --retry-delay 2 ${base}/healthz`;

/**
 * On a paid plan, how to set the licence key, as text beside the block: rrotor gets its key over the link and the
 * daily heartbeat, so only an air-gapped node needs it. Free has no key (rrotor runs as Community).
 */
export const licenceKeyPlaceholder = '<your licence key from the Licence page>';
export const licenceKeyAddition: Record<Deployment, string> = {
  local: `-e GLYPHH_LICENSE_KEY=${licenceKeyPlaceholder} before the image`,
  compose: `GLYPHH_LICENSE_KEY=${licenceKeyPlaceholder} before sh`,
  helm: `--set extraEnv[0].name=GLYPHH_LICENSE_KEY --set-string extraEnv[0].value='${licenceKeyPlaceholder}'`,
  terraform: `offline_licence = "${licenceKeyPlaceholder}" to the module`,
};

/** The registration's values the install script and the image take, in this order. */
const runtimeVars = ['RROTOR_RUNTIME_ID', 'RROTOR_RUNTIME_TOKEN', 'RROTOR_PUBLIC_HOST'] as const;
const hostIn = (env: Record<string, string>) => env.RROTOR_PUBLIC_HOST ?? '';

/** One command on a Linux server: the install script with the registration's values, and the size unless small. */
export function dockerInstall(env: Record<string, string>, size: Size = 'small'): string {
  const vars = runtimeVars.map((name) => `${name}=${env[name] ?? ''}`);
  if (size !== 'small') vars.push(`RROTOR_SIZE=${size}`);
  return [`curl -fsSL ${installScriptUrl} | \\`, `  ${vars.join(' ')} sh`, healthCheck(`https://${hostIn(env)}`)].join('\n');
}

/** The image alone on port 7777. */
function runImage(env: Record<string, string>): string {
  return [
    'docker run -d --name rrotor --restart unless-stopped',
    '  --security-opt seccomp=unconfined --security-opt apparmor=unconfined --security-opt systempaths=unconfined',
    '  --read-only --tmpfs /tmp:exec,mode=1777 -v rrotor-data:/data -p 7777:7777',
    '  -e RROTOR_MODE=self',
    ...runtimeVars.map((name) => `  -e ${name}=${env[name] ?? ''}`),
    `  ${image}:latest`,
  ].join(' \\\n');
}

/** A server with HTTPS already in front: the image alone, checked on the machine itself. */
export const dockerRun = (env: Record<string, string>) => `${runImage(env)}\n${healthCheck(localRuntimeUrl(localHost))}`;

/** This computer: the image alone, checked at the host it was registered with. */
export const localRun = (env: Record<string, string>) => `${runImage(env)}\n${healthCheck(localRuntimeUrl(hostIn(env) || localHost))}`;

export function helmCommand(env: Record<string, string>, options: SnippetOptions): string {
  const values = [
    ['runtime.id', env.RROTOR_RUNTIME_ID],
    ['runtime.token', env.RROTOR_RUNTIME_TOKEN],
    ['publicHost', env.RROTOR_PUBLIC_HOST],
    ['size', options.size],
    ['ingress.className', options.ingressClass.trim() || 'nginx'],
  ];
  const sets = values.map(([name, value]) => `  --set ${name}=${value ?? ''}`);
  return [[`helm install rrotor ${helmChartUrl}`, ...sets].join(' \\\n'), healthCheck(`https://${hostIn(env)}`)].join('\n');
}

/** The module, for a .tf file (not the shell). */
export function terraformModule(env: Record<string, string>, options: SnippetOptions): string {
  const variables: Array<[string, string]> = [
    ['runtime_id', env.RROTOR_RUNTIME_ID ?? ''],
    ['runtime_token', env.RROTOR_RUNTIME_TOKEN ?? ''],
    ['public_host', env.RROTOR_PUBLIC_HOST ?? ''],
    ['size', options.size],
  ];
  if (options.cloud === 'gcp') {
    variables.push(['project', options.gcpProject.trim() || 'your-project-id'], ['region', options.gcpRegion.trim() || 'europe-west2']);
  }
  const width = Math.max(...variables.map(([name]) => name.length));
  const lines = variables.map(([name, value]) => `  ${name.padEnd(width)} = "${value}"`);
  return ['module "rrotor" {', `  source = "${terraformSource(options.cloud)}"`, '', ...lines, '}'].join('\n');
}

/** Run beside the module: it makes one VM, then rrotor answers at its host. */
export const terraformCommands = (env: Record<string, string>) =>
  ['terraform init', 'terraform apply', healthCheck(`https://${hostIn(env)}`)].join('\n');
