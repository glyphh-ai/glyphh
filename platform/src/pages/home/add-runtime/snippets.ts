/** What each self-hosted option needs pasted, filled in from a registration's env. Nothing to clone. */

/** The self-hosting docs' hub; each deployment also has its own page. */
export const docsUrl = 'https://docs.glyphh.ai/run-rrotor';
export const image = 'ghcr.io/glyphh-ai/rrotor';
/** The install script for one Linux machine: Docker, rrotor and HTTPS in front of it. */
export const installScriptUrl = 'https://glyphh.ai/install.sh';
/** The Helm chart as released from the public repo. */
export const helmChartUrl = 'https://github.com/glyphh-ai/glyphh/releases/download/rrotor-chart-0.2.0/rrotor-0.2.0.tgz';

export type Deployment = 'compose' | 'helm' | 'terraform';

export const deploymentDocsUrl: Record<Deployment, string> = {
  compose: 'https://docs.glyphh.ai/docker-compose',
  helm: 'https://docs.glyphh.ai/helm',
  terraform: 'https://docs.glyphh.ai/terraform',
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

/** `rrotor.acme.com` from what a person types: a scheme, a path or a trailing slash are dropped. */
export function hostOf(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/^[a-z]+:\/\//, '')
    .replace(/[/?#].*$/, '');
}

/** A host with at least one dot and nothing but letters, digits, dots, hyphens and a port. */
export function isHost(host: string): boolean {
  return /^[a-z0-9-]+(\.[a-z0-9-]+)+(:\d{1,5})?$/.test(host);
}

export const connectorUrl = (host: string) => `https://${host}/mcp`;

/**
 * On a paid plan, the licence key's optional line, commented out: rrotor gets its key over the link and the daily
 * heartbeat, so only an air-gapped node needs it set. Free has no key (rrotor runs as Community).
 */
export const licenceKeyNote = '# Air-gapped only, normally not needed: rrotor gets its licence key when it links.';
export const licenceKeyPlaceholder = '<your licence key from the Licence page>';

/** The registration's values the install script and the image take, in this order. */
const runtimeVars = ['RROTOR_RUNTIME_ID', 'RROTOR_RUNTIME_TOKEN', 'RROTOR_PUBLIC_HOST'] as const;

/**
 * One command on a Linux machine: the install script with the registration's values, and the size unless small. On a
 * paid plan, the licence key's line follows, commented out.
 */
export function dockerInstall(env: Record<string, string>, size: Size = 'small', paid = false): string {
  const vars = runtimeVars.map((name) => `${name}=${env[name] ?? ''}`);
  if (size !== 'small') vars.push(`RROTOR_SIZE=${size}`);
  const lines = [`curl -fsSL ${installScriptUrl} | \\`, `  ${vars.join(' ')} sh`];
  if (paid) lines.push('', licenceKeyNote, `# Add GLYPHH_LICENSE_KEY=${licenceKeyPlaceholder} before sh.`);
  return lines.join('\n');
}

/** The image alone, for a machine with HTTPS already in front of port 7777. */
export function dockerRun(env: Record<string, string>): string {
  return [
    'docker run -d --name rrotor --restart unless-stopped',
    '  --security-opt seccomp=unconfined --security-opt apparmor=unconfined --security-opt systempaths=unconfined',
    '  --read-only --tmpfs /tmp:exec,mode=1777 -v rrotor-data:/data -p 7777:7777',
    '  -e RROTOR_MODE=self',
    ...runtimeVars.map((name) => `  -e ${name}=${env[name] ?? ''}`),
    `  ${image}:latest`,
  ].join(' \\\n');
}

export function helmCommand(env: Record<string, string>, options: SnippetOptions, paid = false): string {
  const values = [
    ['runtime.id', env.RROTOR_RUNTIME_ID],
    ['runtime.token', env.RROTOR_RUNTIME_TOKEN],
    ['publicHost', env.RROTOR_PUBLIC_HOST],
    ['size', options.size],
    ['ingress.className', options.ingressClass.trim() || 'nginx'],
  ];
  const sets = values.map(([name, value]) => `  --set ${name}=${value ?? ''}`);
  const lines = [[`helm install rrotor ${helmChartUrl}`, ...sets].join(' \\\n')];
  if (paid) {
    lines.push('', `${licenceKeyNote} Add:`, '#   --set extraEnv[0].name=GLYPHH_LICENSE_KEY \\', `#   --set-string extraEnv[0].value='${licenceKeyPlaceholder}'`);
  }
  return lines.join('\n');
}

export function terraformModule(env: Record<string, string>, options: SnippetOptions, paid = false): string {
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
  // The module sets offline_licence as RROTOR_LICENCE, which rrotor reads as GLYPHH_LICENSE_KEY.
  if (paid) lines.push('', `  ${licenceKeyNote}`, `  # offline_licence = "${licenceKeyPlaceholder}"`);
  return ['module "rrotor" {', `  source = "${terraformSource(options.cloud)}"`, '', ...lines, '}'].join('\n');
}
