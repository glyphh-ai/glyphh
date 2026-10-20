import { screen, within } from '@testing-library/react';
import type { Machine, SelfRuntime } from '@/api/types';
import { machines, me, plans, runtime, selfRuntimes } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

const noRuntime = { ...runtime, state: 'none', address: null, runtime_id: null };

const registration = {
  id: 'rt-self-9',
  name: 'Acme production',
  public_url: 'https://rrotor.acme.com',
  token: 'glyphh_rt_secret',
  env: {
    RROTOR_MODE: 'self',
    RROTOR_SERVER: 'https://api.glyphh.ai',
    RROTOR_RUNTIME_ID: 'rt-self-9',
    RROTOR_RUNTIME_TOKEN: 'glyphh_rt_secret',
    RROTOR_PUBLIC_HOST: 'rrotor.acme.com',
  },
};

/** Opens Runtimes with the dialog up, as `/?add=1` does. */
async function openAdd(path = '/?add=1') {
  const view = renderApp(path);
  const dialog = await screen.findByRole('dialog', { name: 'Add a runtime' });
  return { ...view, dialog };
}

/** Registers through the form, as a person would; returns what was sent. */
async function register(user: ReturnType<typeof renderApp>['user'], choice: string) {
  const sent: unknown[] = [];
  server.use(
    http.post(v1('/runtimes/self'), async ({ request }) => {
      sent.push(await request.json());
      return HttpResponse.json(registration, { status: 201 });
    }),
  );
  await user.click(await screen.findByRole('radio', { name: new RegExp(`^${choice}`) }));
  const form = screen.getByRole('form', { name: 'Register a runtime' });
  await user.type(within(form).getByLabelText('Name'), 'Acme production');
  // "Public host", or "Host" on this computer, where it starts as 127.0.0.1.
  await user.clear(within(form).getByLabelText(/host$/i));
  await user.type(within(form).getByLabelText(/host$/i), 'https://rrotor.acme.com/');
  await user.click(within(form).getByRole('button', { name: 'Register runtime' }));
  await screen.findByText('Runtime token for Acme production');
  return sent;
}

describe('Add a runtime', () => {
  it('opens over Runtimes from Add a runtime, and closes back to it', async () => {
    const { user, router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Runtimes', level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Add a runtime' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Add a runtime' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add a runtime' });
    expect(router.state.location.pathname + router.state.location.search).toBe('/?add=1');
    expect(within(dialog).getByRole('link', { name: 'self-hosting docs' })).toHaveAttribute('href', 'https://docs.glyphh.ai/run-rrotor');
    await user.click(within(dialog).getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog', { name: 'Add a runtime' })).not.toBeInTheDocument();
    expect(router.state.location.search).toBe('');
  });

  it('opens on load at /?add=1, under the Runtimes breadcrumb', async () => {
    await openAdd();
    expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText('Runtimes')).toHaveAttribute('aria-current', 'page');
  });

  it('is where /getting-started goes now, and there is no Getting started in the sidebar', async () => {
    const { router } = await openAdd('/getting-started');
    expect(router.state.location.pathname + router.state.location.search).toBe('/?add=1');
    const sidebar = screen.getByRole('complementary', { name: 'Main' });
    expect(within(sidebar).queryByRole('link', { name: 'Getting started' })).not.toBeInTheDocument();
  });

  it('opens from the empty Runtimes page, with no address change but ?add=1', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json(noRuntime)), http.get(v1('/runtimes/self'), () => HttpResponse.json([])));
    const { user, router } = renderApp('/');
    await screen.findByText('No runtime yet');
    await user.click(screen.getByRole('button', { name: 'Run rrotor yourself' }));
    expect(await screen.findByRole('dialog', { name: 'Add a runtime' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/');
  });

  it('shows the runtime just registered in the list once it closes', async () => {
    let rows: SelfRuntime[] = [];
    server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json(rows)));
    const { user, dialog } = await openAdd();
    await register(user, 'Docker');
    rows = [{ ...selfRuntimes[0]!, id: 'rt-self-9', state: 'stopped', version: null, last_heartbeat_at: null, last_seen_at: null }];
    await user.click(within(dialog).getByRole('button', { name: 'Done' }));
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    expect(within(list).getByText('Acme production')).toBeInTheDocument();
    expect(within(list).getByText('Not seen yet')).toBeInTheDocument();
  });

  it('starts afresh each time it opens', async () => {
    const { user, dialog } = await openAdd();
    await register(user, 'Docker');
    await user.click(within(dialog).getByRole('button', { name: 'Done' }));
    await user.click(screen.getByRole('button', { name: 'Add a runtime' }));
    const again = await screen.findByRole('dialog', { name: 'Add a runtime' });
    expect(within(again).getByRole('radio', { name: /^Glyphh hosted/ })).toBeChecked();
    await user.click(within(again).getByRole('radio', { name: /^Docker/ }));
    expect(within(again).getByRole('form', { name: 'Register a runtime' })).toBeInTheDocument();
    expect(screen.queryByText('glyphh_rt_secret')).not.toBeInTheDocument();
  });

  describe('Glyphh hosted', () => {
    it('makes a first machine with a name and a size, then gives its connector URL and the SDKs', async () => {
      let rows: Machine[] = [];
      let sent: unknown;
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json(rows)),
        http.post(v1('/runtimes'), async ({ request }) => {
          sent = await request.json();
          rows = [{ ...machines[0]!, name: 'Work', size: 'medium' }];
          return HttpResponse.json(rows[0], { status: 201 });
        }),
      );
      const { user, dialog } = await openAdd();
      expect(await within(dialog).findByRole('radio', { name: /^Glyphh hosted/ })).toBeChecked();
      const form = await within(dialog).findByRole('form', { name: 'Make your machine' });
      expect(within(form).getByLabelText('Name')).toHaveValue('Main');
      expect(within(form).getByRole('radio', { name: /^Small/ })).toBeChecked();
      await user.clear(within(form).getByLabelText('Name'));
      await user.type(within(form).getByLabelText('Name'), 'Work');
      await user.click(within(form).getByRole('radio', { name: /^Medium/ }));
      await user.click(within(form).getByRole('button', { name: 'Make your machine' }));
      expect(await within(dialog).findByText('https://chris-7f3a.glyphh.app/mcp')).toBeInTheDocument();
      expect(sent).toEqual({ name: 'Work', size: 'medium' });
      expect(within(dialog).getByRole('heading', { name: 'Connect Claude to Work' })).toBeInTheDocument();
      expect(within(dialog).getByText('pip install glyphh')).toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: /^Start/ })).not.toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: 'Machines' })).toHaveAttribute('href', '/machines');
    });

    it('says hosting is on Pro and Team, and running it yourself is free', async () => {
      const { dialog } = await openAdd();
      expect(await within(dialog).findByRole('radio', { name: /^Glyphh hosted.*On Pro and Team\./ })).toBeInTheDocument();
      expect(within(dialog).getAllByRole('radio').map((radio) => (radio as HTMLInputElement).value)).toEqual(['hosted', 'local', 'compose', 'helm', 'terraform']);
      expect(
        within(dialog).getByRole('radio', { name: /^This computer.*Free\. Try it on your laptop; no HTTPS, so Claude cannot connect yet\./ }),
      ).toBeInTheDocument();
      expect(within(dialog).getByRole('radio', { name: /^Docker.*Free\. One command on a Linux machine\./ })).toBeInTheDocument();
      expect(within(dialog).getByRole('radio', { name: /^Helm.*Free\./ })).toBeInTheDocument();
      expect(within(dialog).getByRole('radio', { name: /^Terraform.*Free\./ })).toBeInTheDocument();
      expect(within(dialog).getByText(/Running it yourself is free on every plan/)).toBeInTheDocument();
    });

    it('shows the plan’s rate on each size of the first machine, and Enterprise’s as set in the contract', async () => {
      server.use(http.get(v1('/runtimes'), () => HttpResponse.json([])));
      const { client } = await openAdd();
      const form = await screen.findByRole('form', { name: 'Make your machine' });
      expect(await within(form).findByText('$8.71 / month')).toBeInTheDocument();
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3] })));
      await client.invalidateQueries({ queryKey: ['me'] });
      expect(await within(form).findAllByText('Set in your contract.')).toHaveLength(3);
      expect(within(form).queryByText(/\/ month/)).not.toBeInTheDocument();
    });

    it('on Free, says hosting is on Pro and Team, with their rates and Upgrade', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[0] })), http.get(v1('/runtimes'), () => HttpResponse.json([])));
      const { user, router, dialog } = await openAdd();
      expect(await within(dialog).findByText(/Glyphh hosts machines on Pro and Team\./)).toBeInTheDocument();
      expect(within(dialog).queryByRole('form', { name: 'Make your machine' })).not.toBeInTheDocument();
      const table = await within(dialog).findByRole('table', { name: 'Hosted machine rates' });
      expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Size', 'Pro', 'Team']);
      await user.click(within(dialog).getByRole('button', { name: 'Upgrade' }));
      expect(router.state.location.pathname).toBe('/settings/plans');
    });

    it('on Free, asks a member to ask their admin', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member', plan: plans[0] })), http.get(v1('/runtimes'), () => HttpResponse.json([])));
      const { dialog } = await openAdd();
      expect(await within(dialog).findByText(/Ask your admin to upgrade\./)).toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: 'Upgrade' })).not.toBeInTheDocument();
    });

    it('starts the first machine when it is stopped', async () => {
      let rows: Machine[] = [{ ...machines[1]! }];
      let started = '';
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json(rows)),
        http.post(v1('/runtimes/:id/start'), ({ params }) => {
          started = String(params.id);
          rows = [{ ...rows[0]!, state: 'online' }];
          return HttpResponse.json(rows[0]);
        }),
      );
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('button', { name: 'Start' }));
      await vi.waitFor(() => expect(within(dialog).queryByRole('button', { name: 'Start' })).not.toBeInTheDocument());
      expect(started).toBe('rt-2b8e41');
      expect(within(dialog).getByText('https://chris-2b8e.glyphh.app/mcp')).toBeInTheDocument();
    });

    it('says plainly when the plan has no room for the machine to start, with the way to Billing', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([machines[1]])),
        http.post(v1('/runtimes/:id/start'), () => apiError(403, 'E_LIMIT', 'Free has no hosted machines.', { reason: 'machines' })),
      );
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('button', { name: 'Start' }));
      const alert = await within(dialog).findByRole('alert');
      expect(alert).toHaveTextContent('Your plan has no room for this machine, so it stays stopped.');
      expect(within(alert).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
    });

    it('shows the server’s refusal when starting fails', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([machines[1]])),
        http.post(v1('/runtimes/:id/start'), () => apiError(503, 'E_UNAVAILABLE', 'Hosting is off right now.')),
      );
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('button', { name: 'Start' }));
      expect(await within(dialog).findByText('Hosting is off right now.')).toBeInTheDocument();
    });

    it('sends a person at the plan’s limit to Billing', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([])),
        http.post(v1('/runtimes'), () => apiError(403, 'E_LIMIT', 'Free allows 1 machine.', { reason: 'machines' })),
      );
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('button', { name: 'Make your machine' }));
      const alert = await within(dialog).findByRole('alert');
      expect(alert).toHaveTextContent('Your plan has no room for another machine.');
      expect(within(alert).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
    });

    it('says plainly when the server has stopped hosting machines, with the way to run rrotor yourself', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([])),
        http.post(v1('/runtimes'), () => apiError(409, 'E_UNAVAILABLE', 'Hosting is off.', { reason: 'hosting_off' })),
      );
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('button', { name: 'Make your machine' }));
      const alert = await within(dialog).findByRole('alert');
      expect(alert).toHaveTextContent('Glyphh is not hosting machines now. Run rrotor yourself with Docker, Helm or Terraform.');
      expect(within(alert).getByRole('link', { name: 'Add a runtime' })).toHaveAttribute('href', '/?add=1');
    });

    it('says so when the machines cannot be read', async () => {
      server.use(http.get(v1('/runtimes'), () => apiError(500, 'E_INTERNAL', 'The machines could not be read.')));
      const { dialog } = await openAdd();
      expect(await within(dialog).findByText('The machines could not be read.')).toBeInTheDocument();
    });
  });

  describe('self-hosted', () => {
    it('registers with the host alone, shows the token once, the Docker command filled in, then how to connect', async () => {
      const { user, dialog } = await openAdd();
      const sent = await register(user, 'Docker');
      expect(sent).toEqual([{ name: 'Acme production', public_url: 'https://rrotor.acme.com' }]);
      expect(within(dialog).getByText('glyphh_rt_secret')).toBeInTheDocument();
      expect(within(dialog).getByText(/Shown once\./)).toBeInTheDocument();
      const install = within(dialog).getByText(/curl -fsSL https:\/\/glyphh\.ai\/install\.sh/);
      expect(install).toHaveTextContent('RROTOR_RUNTIME_ID=rt-self-9 RROTOR_RUNTIME_TOKEN=glyphh_rt_secret RROTOR_PUBLIC_HOST=rrotor.acme.com sh');
      expect(install).not.toHaveTextContent('RROTOR_SIZE');
      await user.selectOptions(within(dialog).getByLabelText('Size'), 'Medium');
      expect(within(dialog).getByText(/curl -fsSL/)).toHaveTextContent('RROTOR_PUBLIC_HOST=rrotor.acme.com RROTOR_SIZE=medium sh');
      await user.click(within(dialog).getByRole('button', { name: 'Copy install command' }));
      expect(await navigator.clipboard.readText()).toContain('RROTOR_RUNTIME_TOKEN=glyphh_rt_secret');
      expect(within(dialog).getByText('HTTPS already in front? Run the image alone:')).toBeInTheDocument();
      const run = within(dialog).getByText(/docker run -d --name rrotor/);
      expect(run).toHaveTextContent('-e RROTOR_RUNTIME_TOKEN=glyphh_rt_secret');
      expect(run).toHaveTextContent('ghcr.io/glyphh-ai/rrotor:latest');
      expect(within(dialog).getByText(/rrotor\.acme\.com’s DNS at the server first/)).toBeInTheDocument();
      expect(install).toHaveTextContent('curl -fsS --retry 15 --retry-connrefused --retry-delay 2 https://rrotor.acme.com/healthz');
      expect(run).toHaveTextContent('http://127.0.0.1:7777/healthz');
      expect(within(dialog).queryByText(/git\s+clone/)).not.toBeInTheDocument();
      expect(within(dialog).getByText('https://rrotor.acme.com/mcp')).toBeInTheDocument();
      expect(within(dialog).getByText('pip install glyphh')).toBeInTheDocument();
      expect(within(dialog).getByText('npm i @glyphh-ai/glyphh')).toBeInTheDocument();
      expect(within(dialog).getByText('/plugin marketplace add glyphh-ai/glyphh')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'Copy plugin command' }));
      expect(await navigator.clipboard.readText()).toBe('/plugin install glyphh@glyphh');
    });

    it('keeps the registration on changing option: Helm with its values, then Terraform for AWS and GCP', async () => {
      const { user, dialog } = await openAdd();
      await register(user, 'Docker');
      const docs = () => within(dialog).getAllByRole('link', { name: 'self-hosting docs' }).map((link) => link.getAttribute('href'));
      expect(docs()).toContain('https://docs.glyphh.ai/docker-compose');

      await user.click(within(dialog).getByRole('radio', { name: /^Helm/ }));
      expect(docs()).toContain('https://docs.glyphh.ai/helm');
      await user.selectOptions(within(dialog).getByLabelText('Size'), 'Large');
      await user.clear(within(dialog).getByLabelText('Ingress class'));
      await user.type(within(dialog).getByLabelText('Ingress class'), 'traefik');
      const helm = within(dialog).getByText(/helm install rrotor/);
      expect(helm).toHaveTextContent('helm install rrotor https://github.com/glyphh-ai/glyphh/releases/download/rrotor-chart-0.2.0/rrotor-0.2.0.tgz');
      expect(helm).toHaveTextContent('--set runtime.token=glyphh_rt_secret');
      expect(helm).toHaveTextContent('--set size=large');
      expect(helm).toHaveTextContent('--set ingress.className=traefik');

      await user.click(within(dialog).getByRole('radio', { name: /^Terraform/ }));
      expect(docs()).toContain('https://docs.glyphh.ai/terraform');
      expect(within(dialog).getByText(/module "rrotor"/)).toHaveTextContent('git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/aws?ref=main');
      await user.selectOptions(within(dialog).getByLabelText('Cloud'), 'GCP');
      await user.type(within(dialog).getByLabelText('Project'), 'acme-prod');
      const gcp = within(dialog).getByText(/module "rrotor"/);
      expect(gcp).toHaveTextContent('//deploy/terraform/gcp?ref=main');
      expect(gcp).toHaveTextContent('project = "acme-prod"');
      expect(gcp).toHaveTextContent('region = "europe-west2"');
      await user.clear(within(dialog).getByLabelText('Region'));
      await user.type(within(dialog).getByLabelText('Region'), 'us-east1');
      expect(within(dialog).getByText(/module "rrotor"/)).toHaveTextContent('region = "us-east1"');

      await user.click(within(dialog).getByRole('button', { name: 'Register another' }));
      expect(within(dialog).getByRole('form', { name: 'Register a runtime' })).toBeInTheDocument();
      expect(within(dialog).queryByText('glyphh_rt_secret')).not.toBeInTheDocument();
    });

    it('on a paid plan, says beside the command how to set the licence key, for an air-gapped node only', async () => {
      const { user, dialog } = await openAdd();
      await register(user, 'Docker');
      expect(within(dialog).getByText(/curl -fsSL/)).not.toHaveTextContent('GLYPHH_LICENSE_KEY');
      expect(within(dialog).getByText(/reaches rrotor on its own when it links and at its daily heartbeat\. Only for an air-gapped node, add/)).toBeInTheDocument();
      expect(within(dialog).getByText('GLYPHH_LICENSE_KEY=<your licence key from the Licence page> before sh')).toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: 'Licence' })).toHaveAttribute('href', '/licence');

      await user.click(within(dialog).getByRole('radio', { name: /^This computer/ }));
      expect(within(dialog).getByText('-e GLYPHH_LICENSE_KEY=<your licence key from the Licence page> before the image')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('radio', { name: /^Helm/ }));
      expect(within(dialog).getByText(/helm install rrotor/)).not.toHaveTextContent('GLYPHH_LICENSE_KEY');
      expect(within(dialog).getByText(/^--set extraEnv\[0\]\.name=GLYPHH_LICENSE_KEY/)).toBeInTheDocument();
      await user.click(within(dialog).getByRole('radio', { name: /^Terraform/ }));
      expect(within(dialog).getByText(/module "rrotor"/)).not.toHaveTextContent('offline_licence');
      expect(within(dialog).getByText('offline_licence = "<your licence key from the Licence page>" to the module')).toBeInTheDocument();
    });

    it('shows no comment lines in any command, so each pastes into zsh or bash, and each ends with the health check', async () => {
      const { user, dialog } = await openAdd();
      await register(user, 'This computer');
      const blocks = () => within(dialog).getAllByRole('button', { name: /^Copy (docker run command|install command|helm install|terraform commands)$/ });
      const codeOf = (button: HTMLElement) => button.parentElement!.querySelector('code')!.textContent!;
      for (const way of ['This computer', 'Docker', 'Helm', 'Terraform']) {
        await user.click(within(dialog).getByRole('radio', { name: new RegExp(`^${way}`) }));
        expect(blocks().length).toBeGreaterThan(0);
        for (const button of blocks()) {
          const lines = codeOf(button).split('\n');
          expect(lines.filter((line) => line.trim().startsWith('#'))).toEqual([]);
          expect(lines.at(-1)).toMatch(/^curl -fsS .*\/healthz$/);
        }
      }
    });

    it('on Free, has no licence key line: rrotor runs as Community', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[0] })));
      const { user, dialog } = await openAdd();
      await register(user, 'Docker');
      expect(within(dialog).getByText(/curl -fsSL/)).not.toHaveTextContent('GLYPHH_LICENSE_KEY');
      expect(within(dialog).queryByText(/reaches rrotor on its own/)).not.toBeInTheDocument();
      await user.click(within(dialog).getByRole('radio', { name: /^Helm/ }));
      expect(within(dialog).getByText(/helm install rrotor/)).not.toHaveTextContent('GLYPHH_LICENSE_KEY');
    });

    it('asks for a DNS name it can use before registering, except on this computer', async () => {
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('radio', { name: /^Helm/ }));
      const button = within(dialog).getByRole('button', { name: 'Register runtime' });
      await user.type(within(dialog).getByLabelText('Name'), 'Lab');
      await user.type(within(dialog).getByLabelText('Public host'), 'localhost');
      expect(within(dialog).getByText('Use the host alone, such as rrotor.acme.com.')).toBeInTheDocument();
      expect(button).toBeDisabled();
      await user.click(within(dialog).getByRole('radio', { name: /^This computer/ }));
      expect(within(dialog).getByLabelText('Host')).toHaveValue('localhost');
      expect(within(dialog).queryByText('Use the host alone, such as rrotor.acme.com.')).not.toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: 'Register runtime' })).toBeEnabled();
    });

    it('says what each way needs before registering', async () => {
      const { user, dialog } = await openAdd();
      const needs: Array<[string, RegExp]> = [
        ['This computer', /What you need: Docker running on this computer/],
        ['Docker', /What you need: A Linux server with Docker and the Compose plugin \(docker compose version works\), a DNS name pointing at it, ports 80 and 443 open\./],
        ['Helm', /What you need: A Kubernetes cluster with an Ingress controller, and kubectl and helm/],
        ['Terraform', /What you need: An AWS account or a GCP project, and terraform\./],
      ];
      for (const [way, text] of needs) {
        await user.click(await within(dialog).findByRole('radio', { name: new RegExp(`^${way}`) }));
        expect(within(dialog).getByText('What you need:').parentElement).toHaveTextContent(text);
        expect(within(dialog).getByRole('form', { name: 'Register a runtime' })).toBeInTheDocument();
      }
    });

    it('runs on this computer: 127.0.0.1 to start with, the image alone, its check, and the SDKs’ URL instead of a connector', async () => {
      const local = { ...registration, name: 'My laptop', public_url: 'https://127.0.0.1', env: { ...registration.env, RROTOR_PUBLIC_HOST: '127.0.0.1' } };
      let sent: unknown;
      server.use(
        http.post(v1('/runtimes/self'), async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json(local, { status: 201 });
        }),
      );
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('radio', { name: /^This computer/ }));
      const form = within(dialog).getByRole('form', { name: 'Register a runtime' });
      expect(within(form).getByLabelText('Host')).toHaveValue('127.0.0.1');
      await user.type(within(form).getByLabelText('Name'), 'My laptop');
      await user.click(within(form).getByRole('button', { name: 'Register runtime' }));
      await within(dialog).findByText('Runtime token for My laptop');
      expect(sent).toEqual({ name: 'My laptop', public_url: 'https://127.0.0.1' });

      const run = within(dialog).getByText(/docker run -d --name rrotor/);
      expect(run).toHaveTextContent('-p 7777:7777');
      expect(run).toHaveTextContent('-e RROTOR_PUBLIC_HOST=127.0.0.1');
      expect(run).toHaveTextContent('ghcr.io/glyphh-ai/rrotor:latest');
      expect(run).toHaveTextContent(/curl -fsS .* http:\/\/127\.0\.0\.1:7777\/healthz$/);
      expect(run).not.toHaveTextContent('install.sh');
      expect(run).not.toHaveTextContent('compose');
      expect(within(dialog).getByText(/Claude’s connector cannot reach it: that needs a public HTTPS host, so use Docker or Helm on a server/)).toBeInTheDocument();
      expect(within(dialog).getByText('export GLYPHH_RUNTIME_URL=http://127.0.0.1:7777')).toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: 'API Keys' })).toHaveAttribute('href', '/keys');
      expect(within(dialog).queryByRole('button', { name: 'Copy connector URL' })).not.toBeInTheDocument();
      expect(within(dialog).getByText('pip install glyphh')).toBeInTheDocument();
    });

    it('shows why a runtime could not be registered', async () => {
      server.use(http.post(v1('/runtimes/self'), () => apiError(403, 'E_NOT_IN_PLAN', 'Self-hosting needs the Team plan.')));
      const { user, dialog } = await openAdd();
      await user.click(await within(dialog).findByRole('radio', { name: /^Terraform/ }));
      await user.type(within(dialog).getByLabelText('Name'), 'Lab');
      await user.type(within(dialog).getByLabelText('Public host'), 'rrotor.lab.acme.com');
      await user.click(within(dialog).getByRole('button', { name: 'Register runtime' }));
      expect(await within(dialog).findByText('Self-hosting needs the Team plan.')).toBeInTheDocument();
    });
  });
});

describe('Add a runtime while Glyphh hosts nothing', () => {
  it.each(['refused', 'off', 'empty'] as const)('offers only running rrotor yourself, this computer first, when the rates answer %s', async (rates) => {
    server.use(...hostingOffHandlers(rates));
    const { dialog } = await openAdd();
    const local = await within(dialog).findByRole('radio', { name: /^This computer/ });
    expect(local).toBeChecked();
    expect(within(dialog).getAllByRole('radio').map((radio) => (radio as HTMLInputElement).value)).toEqual(['local', 'compose', 'helm', 'terraform']);
    expect(within(dialog).queryByRole('radio', { name: /^Glyphh hosted/ })).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/Glyphh runs it for you/)).not.toBeInTheDocument();
    expect(within(dialog).getByRole('form', { name: 'Register a runtime' })).toBeInTheDocument();
    expect(within(dialog).queryByRole('form', { name: 'Make your machine' })).not.toBeInTheDocument();
  });

  it('registers a self-hosted runtime as before', async () => {
    server.use(...hostingOffHandlers());
    const { user } = await openAdd();
    const sent = await register(user, 'Helm');
    expect(sent).toEqual([{ name: 'Acme production', public_url: 'https://rrotor.acme.com' }]);
    expect(screen.getByText(/helm install/)).toBeInTheDocument();
  });
});
