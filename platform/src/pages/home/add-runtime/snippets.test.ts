import { connectorUrl, defaultOptions, dockerInstall, dockerRun, helmChartUrl, helmCommand, hostOf, isHost, terraformModule } from './snippets';

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
  it('runs the install script with the registration’s values, the size only when not small', () => {
    expect(dockerInstall(env)).toBe(
      [
        'curl -fsSL https://glyphh.ai/install.sh | \\',
        '  RROTOR_RUNTIME_ID=rt-1 RROTOR_RUNTIME_TOKEN=glyphh_rt_abc RROTOR_PUBLIC_HOST=rrotor.acme.com sh',
      ].join('\n'),
    );
    expect(dockerInstall(env, 'large')).toContain('RROTOR_PUBLIC_HOST=rrotor.acme.com RROTOR_SIZE=large sh');
  });

  it('runs the image alone, over lines', () => {
    expect(dockerRun(env)).toBe(
      [
        'docker run -d --name rrotor --restart unless-stopped \\',
        '  --security-opt seccomp=unconfined --security-opt apparmor=unconfined --security-opt systempaths=unconfined \\',
        '  --read-only --tmpfs /tmp:exec,mode=1777 -v rrotor-data:/data -p 7777:7777 \\',
        '  -e RROTOR_MODE=self \\',
        '  -e RROTOR_RUNTIME_ID=rt-1 \\',
        '  -e RROTOR_RUNTIME_TOKEN=glyphh_rt_abc \\',
        '  -e RROTOR_PUBLIC_HOST=rrotor.acme.com \\',
        '  ghcr.io/glyphh-ai/rrotor:latest',
      ].join('\n'),
    );
  });

  it('installs the released Helm chart with each value set', () => {
    expect(helmCommand(env, { ...defaultOptions, size: 'medium', ingressClass: ' ' })).toBe(
      [
        `helm install rrotor ${helmChartUrl} \\`,
        '  --set runtime.id=rt-1 \\',
        '  --set runtime.token=glyphh_rt_abc \\',
        '  --set publicHost=rrotor.acme.com \\',
        '  --set size=medium \\',
        '  --set ingress.className=nginx',
      ].join('\n'),
    );
    expect(helmChartUrl).toBe('https://github.com/glyphh-ai/glyphh/releases/download/rrotor-chart-0.2.0/rrotor-0.2.0.tgz');
  });

  it('leaves a value blank when the env lacks it', () => {
    expect(helmCommand({}, defaultOptions)).toContain('--set runtime.id= \\');
    expect(terraformModule({}, defaultOptions)).toContain('runtime_id    = ""');
    expect(dockerInstall({})).toContain('RROTOR_RUNTIME_ID= ');
  });

  it('writes the AWS module with its four variables', () => {
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
  });

  it('adds the project and the region for GCP, with placeholders until they are given', () => {
    const gcp = terraformModule(env, { ...defaultOptions, cloud: 'gcp', gcpRegion: '' });
    expect(gcp).toContain('source = "git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/gcp?ref=main"');
    expect(gcp).toContain('project       = "your-project-id"');
    expect(gcp).toContain('region        = "europe-west2"');
    expect(terraformModule(env, { ...defaultOptions, cloud: 'gcp', gcpProject: 'acme-prod', gcpRegion: 'us-east1' })).toContain('project       = "acme-prod"');
  });

  it('never clones a repo', () => {
    const all = [dockerInstall(env, 'medium', true), dockerRun(env), helmCommand(env, defaultOptions, true), terraformModule(env, defaultOptions, true)];
    for (const snippet of all) expect(snippet).not.toMatch(/git\s+clone/);
  });
});

describe('the licence key’s line, on a paid plan', () => {
  it('follows the install command, commented out, for an air-gapped node only; none on Free', () => {
    expect(dockerInstall(env, 'small', false)).not.toContain('GLYPHH_LICENSE_KEY');
    expect(dockerInstall(env, 'small', true)).toBe(
      `${dockerInstall(env)}\n\n# Air-gapped only, normally not needed: rrotor gets its licence key when it links.\n# Add GLYPHH_LICENSE_KEY=<your licence key from the Licence page> before sh.`,
    );
  });

  it('follows the Helm command as values to add, leaving the command whole', () => {
    const helm = helmCommand(env, defaultOptions, true);
    expect(helm.startsWith(helmCommand(env, defaultOptions))).toBe(true);
    expect(helm.split('\n').slice(-3)).toEqual([
      '# Air-gapped only, normally not needed: rrotor gets its licence key when it links. Add:',
      '#   --set extraEnv[0].name=GLYPHH_LICENSE_KEY \\',
      "#   --set-string extraEnv[0].value='<your licence key from the Licence page>'",
    ]);
  });

  it('sits in the Terraform module as offline_licence, commented out', () => {
    const module = terraformModule(env, defaultOptions, true).split('\n');
    expect(module.slice(-3)).toEqual([
      '  # Air-gapped only, normally not needed: rrotor gets its licence key when it links.',
      '  # offline_licence = "<your licence key from the Licence page>"',
      '}',
    ]);
    expect(terraformModule(env, defaultOptions)).not.toContain('offline_licence');
  });
});
