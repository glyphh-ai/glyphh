/** What each self-hosted option needs pasted, filled in from a registration's env. */

export const docsUrl = 'https://github.com/glyphh-ai/rrotor/tree/main/docs/self-hosting';
export const image = 'ghcr.io/glyphh-ai/rrotor';
const repo = 'https://github.com/glyphh-ai/rrotor.git';
const modules = 'github.com/glyphh-ai/rrotor//deploy/terraform';

export type Deployment = 'compose' | 'helm' | 'terraform';
export type Cloud = 'aws' | 'gcp';
export type Size = 'small' | 'medium' | 'large';

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

/** The env file for Docker Compose: one `NAME=value` a line, in the server's order. */
export function dotEnv(env: Record<string, string>): string {
  return Object.entries(env)
    .map(([name, value]) => `${name}=${value}`)
    .join('\n');
}

/**
 * On a paid plan, the licence key's optional line, commented out: rrotor gets its key over the link and the daily
 * heartbeat, so only an air-gapped node needs it set. Free has no key (rrotor runs as Community).
 */
export const licenceKeyNote = '# Air-gapped only, normally not needed: rrotor gets its licence key when it links.';
export const licenceKeyPlaceholder = '<your licence key from Settings → Licence>';
export const licenceDotEnv = [licenceKeyNote, `# GLYPHH_LICENSE_KEY=${licenceKeyPlaceholder}`].join('\n');

/** The env file with, on a paid plan, the licence key's commented line after a blank one. */
export const composeEnv = (env: Record<string, string>, paid: boolean) => (paid ? `${dotEnv(env)}\n\n${licenceDotEnv}` : dotEnv(env));

export const composeCommands = [`git clone ${repo}`, 'cd rrotor/deploy/compose', '# save the .env above here, then:', 'docker compose up -d'].join('\n');

export function helmCommand(env: Record<string, string>, options: SnippetOptions, paid = false): string {
  const values = [
    ['runtime.id', env.RROTOR_RUNTIME_ID],
    ['runtime.token', env.RROTOR_RUNTIME_TOKEN],
    ['publicHost', env.RROTOR_PUBLIC_HOST],
    ['size', options.size],
    ['ingress.className', options.ingressClass.trim() || 'nginx'],
  ];
  const sets = values.map(([name, value]) => `  --set ${name}=${value ?? ''}`);
  const lines = [`git clone ${repo}`, ['helm install rrotor ./rrotor/deploy/helm/rrotor', ...sets].join(' \\\n')];
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
  return ['module "rrotor" {', `  source = "${modules}/${options.cloud}"`, '', ...lines, '}'].join('\n');
}
