import { composeCommands, connectorUrl, defaultOptions, dotEnv, helmCommand, hostOf, isHost, terraformModule } from './snippets';

const env = {
  RROTOR_MODE: 'self',
  RROTOR_SERVER: 'https://api.glyphh.ai',
  RROTOR_RUNTIME_ID: 'rt-1',
  RROTOR_RUNTIME_TOKEN: 'glyphh_rt_abc',
  RROTOR_PUBLIC_HOST: 'rrotor.acme.com',
};

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
    expect(isHost('rrotor acme.com')).toBe(false);
    expect(isHost('')).toBe(false);
  });

  it('gives the connector URL', () => expect(connectorUrl('rrotor.acme.com')).toBe('https://rrotor.acme.com/mcp'));
});

describe('the snippets', () => {
  it('writes the env file in the server’s order', () => {
    expect(dotEnv(env)).toBe(
      'RROTOR_MODE=self\nRROTOR_SERVER=https://api.glyphh.ai\nRROTOR_RUNTIME_ID=rt-1\nRROTOR_RUNTIME_TOKEN=glyphh_rt_abc\nRROTOR_PUBLIC_HOST=rrotor.acme.com',
    );
    expect(composeCommands).toContain('cd rrotor/deploy/compose');
    expect(composeCommands).toContain('docker compose up -d');
  });

  it('installs the Helm chart with each value set', () => {
    expect(helmCommand(env, { ...defaultOptions, size: 'medium', ingressClass: ' ' })).toBe(
      [
        'git clone https://github.com/glyphh-ai/rrotor.git',
        'helm install rrotor ./rrotor/deploy/helm/rrotor \\',
        '  --set runtime.id=rt-1 \\',
        '  --set runtime.token=glyphh_rt_abc \\',
        '  --set publicHost=rrotor.acme.com \\',
        '  --set size=medium \\',
        '  --set ingress.className=nginx',
      ].join('\n'),
    );
  });

  it('leaves a value blank when the env lacks it', () => {
    expect(helmCommand({}, defaultOptions)).toContain('--set runtime.id= \\');
    expect(terraformModule({}, defaultOptions)).toContain('runtime_id    = ""');
  });

  it('writes the AWS module with its four variables', () => {
    expect(terraformModule(env, defaultOptions)).toBe(
      [
        'module "rrotor" {',
        '  source = "github.com/glyphh-ai/rrotor//deploy/terraform/aws"',
        '',
        '  runtime_id    = "rt-1"',
        '  runtime_token = "glyphh_rt_abc"',
        '  public_host   = "rrotor.acme.com"',
        '  size          = "small"',
        '}',
      ].join('\n'),
    );
  });

  it('adds the project and the region for GCP, with placeholders until they are given', () => {
    const gcp = terraformModule(env, { ...defaultOptions, cloud: 'gcp', gcpRegion: '' });
    expect(gcp).toContain('source = "github.com/glyphh-ai/rrotor//deploy/terraform/gcp"');
    expect(gcp).toContain('project       = "your-project-id"');
    expect(gcp).toContain('region        = "europe-west2"');
    expect(terraformModule(env, { ...defaultOptions, cloud: 'gcp', gcpProject: 'acme-prod', gcpRegion: 'us-east1' })).toContain('project       = "acme-prod"');
  });
});
