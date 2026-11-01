import {
  connectorUrl,
  defaultOptions,
  dockerInstall,
  dockerRun,
  healthCheck,
  helmChartUrl,
  helmCommand,
  hostOf,
  isHost,
  isHostFor,
  localInstall,
  localRun,
  localRuntimeUrl,
  terraformCommands,
  terraformModule,
} from './snippets';

const env = {
  RROTOR_MODE: 'self',
  RROTOR_SERVER: 'https://api.glyphh.ai',
  RROTOR_RUNTIME_ID: 'rt-1',
  RROTOR_RUNTIME_TOKEN: 'glyphh_rt_abc',
  RROTOR_PUBLIC_HOST: 'rrotor.acme.com',
};
const localEnv = { ...env, RROTOR_PUBLIC_HOST: '127.0.0.1' };

const runImage = (host: string) =>
  [
    'docker run -d --name rrotor --restart unless-stopped \\',
    '  --security-opt seccomp=unconfined --security-opt apparmor=unconfined --security-opt systempaths=unconfined \\',
    '  --read-only --tmpfs /tmp:exec,mode=1777 -v rrotor-data:/data -p 7777:7777 \\',
    '  -e RROTOR_MODE=self \\',
    '  -e RROTOR_RUNTIME_ID=rt-1 \\',
    '  -e RROTOR_RUNTIME_TOKEN=glyphh_rt_abc \\',
    `  -e RROTOR_PUBLIC_HOST=${host} \\`,
    '  ghcr.io/glyphh-ai/rrotor:latest',
  ].join('\n');

describe('the host', () => {
  it('is what a person typed, without a scheme, a path or a trailing slash', () => {
    expect(hostOf('  https://RRotor.Acme.com/mcp ')).toBe('rrotor.acme.com');
    expect(hostOf('rrotor.acme.com/')).toBe('rrotor.acme.com');
    expect(hostOf('rrotor.acme.com:8443?x')).toBe('rrotor.acme.com:8443');
  });

  it('needs a dot and nothing odd', () => {
    expect(isHost('rrotor.acme.com')).toBe(true);
    expect(isHost('rrotor.acme.com:8443')).toBe(true);
    expect(isHost('localhost')).toBe(false);
    expect(isHost('127.0.0.1')).toBe(false);
    expect(isHost('rrotor acme.com')).toBe(false);
    expect(isHost('')).toBe(false);
  });

  it('may be localhost or an IP address on this computer only', () => {
    for (const host of ['127.0.0.1', 'localhost', '192.168.1.20', 'rrotor.acme.com']) expect(isHostFor('local', host)).toBe(true);
    // The server keeps https://<host> with no port, and no IPv6 literal.
    for (const host of ['', 'rrotor acme.com', 'not_a_host', 'localhost:7777', '127.0.0.1:7777', '[::1]']) expect(isHostFor('local', host)).toBe(false);
    for (const way of ['compose', 'helm', 'terraform'] as const) {
      expect(isHostFor(way, '127.0.0.1')).toBe(false);
      expect(isHostFor(way, 'localhost')).toBe(false);
      expect(isHostFor(way, 'rrotor.acme.com')).toBe(true);
    }
  });

  it('gives the connector URL, and the SDKs’ URL on this computer', () => {
    expect(connectorUrl('rrotor.acme.com')).toBe('https://rrotor.acme.com/mcp');
    expect(localRuntimeUrl('127.0.0.1')).toBe('http://127.0.0.1:7777');
  });
});

describe('the snippets', () => {
  it('runs the install script on this computer (it runs the image alone there), then checks it over HTTP at its host', () => {
    expect(localInstall(localEnv)).toBe(
      [
        'curl -fsSL https://glyphh.ai/install.sh | \\',
        '  RROTOR_RUNTIME_ID=rt-1 RROTOR_RUNTIME_TOKEN=glyphh_rt_abc RROTOR_PUBLIC_HOST=127.0.0.1 sh',
        'curl -fsS --retry 15 --retry-connrefused --retry-delay 2 http://127.0.0.1:7777/healthz',
      ].join('\n'),
    );
  });

  it('runs the image alone on this computer, then checks it at its host', () => {
    expect(localRun(localEnv)).toBe(`${runImage('127.0.0.1')}\ncurl -fsS --retry 15 --retry-connrefused --retry-delay 2 http://127.0.0.1:7777/healthz`);
    expect(localRun({ ...localEnv, RROTOR_PUBLIC_HOST: 'localhost' })).toMatch(/http:\/\/localhost:7777\/healthz$/);
  });

  it('runs the install script with the registration’s values, the size only when not small, then checks it over HTTPS', () => {
    expect(dockerInstall(env)).toBe(
      [
        'curl -fsSL https://glyphh.ai/install.sh | \\',
        '  RROTOR_RUNTIME_ID=rt-1 RROTOR_RUNTIME_TOKEN=glyphh_rt_abc RROTOR_PUBLIC_HOST=rrotor.acme.com sh',
        healthCheck('https://rrotor.acme.com'),
      ].join('\n'),
    );
    expect(dockerInstall(env, 'large')).toContain('RROTOR_PUBLIC_HOST=rrotor.acme.com RROTOR_SIZE=large sh');
  });

  it('runs the image alone behind HTTPS, checked on the machine', () => {
    expect(dockerRun(env)).toBe(`${runImage('rrotor.acme.com')}\n${healthCheck('http://127.0.0.1:7777')}`);
  });

  it('installs the released Helm chart with each value set, then checks it', () => {
    expect(helmCommand(env, { ...defaultOptions, size: 'medium', ingressClass: ' ' })).toBe(
      [
        `helm install rrotor ${helmChartUrl} \\`,
        '  --set runtime.id=rt-1 \\',
        '  --set runtime.token=glyphh_rt_abc \\',
        '  --set publicHost=rrotor.acme.com \\',
        '  --set size=medium \\',
        '  --set ingress.className=nginx',
        healthCheck('https://rrotor.acme.com'),
      ].join('\n'),
    );
    expect(helmChartUrl).toBe('https://github.com/glyphh-ai/glyphh/releases/download/rrotor-chart-0.2.0/rrotor-0.2.0.tgz');
  });

  it('leaves a value blank when the env lacks it', () => {
    expect(helmCommand({}, defaultOptions)).toContain('--set runtime.id= \\');
    expect(terraformModule({}, defaultOptions)).toContain('runtime_id    = ""');
    expect(dockerInstall({})).toContain('RROTOR_RUNTIME_ID= ');
  });

  it('writes the AWS module with its four variables, and the commands beside it end with the check', () => {
    expect(terraformModule(env, defaultOptions)).toBe(
      [
        'module "rrotor" {',
        '  source = "git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/aws?ref=main"',
        '',
        '  runtime_id    = "rt-1"',
        '  runtime_token = "glyphh_rt_abc"',
        '  public_host   = "rrotor.acme.com"',
        '  size          = "small"',
        '}',
      ].join('\n'),
    );
    expect(terraformCommands(env)).toBe(['terraform init', 'terraform apply', healthCheck('https://rrotor.acme.com')].join('\n'));
  });

  it('adds the project and the region for GCP, with placeholders until they are given', () => {
    const gcp = terraformModule(env, { ...defaultOptions, cloud: 'gcp', gcpRegion: '' });
    expect(gcp).toContain('source = "git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/gcp?ref=main"');
    expect(gcp).toContain('project       = "your-project-id"');
    expect(gcp).toContain('region        = "europe-west2"');
    expect(terraformModule(env, { ...defaultOptions, cloud: 'gcp', gcpProject: 'acme-prod', gcpRegion: 'us-east1' })).toContain('project       = "acme-prod"');
  });

  const shell = () => [localInstall(localEnv), localRun(localEnv),dockerInstall(env, 'medium'), dockerRun(env), helmCommand(env, defaultOptions), terraformCommands(env)];

  it('pastes into zsh or bash: no comment lines, and each ends with the health check', () => {
    for (const block of shell()) {
      expect(block.split('\n').filter((line) => line.trim().startsWith('#'))).toEqual([]);
      expect(block.split('\n').at(-1)).toMatch(/^curl -fsS .*\/healthz$/);
    }
    expect(terraformModule(env, defaultOptions)).not.toContain('#');
  });

  it('never clones a repo', () => {
    for (const snippet of [...shell(), terraformModule(env, defaultOptions)]) expect(snippet).not.toMatch(/git\s+clone/);
  });
});
