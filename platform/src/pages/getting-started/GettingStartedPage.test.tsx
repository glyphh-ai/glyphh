import { screen, within } from '@testing-library/react';
import type { Machine } from '@/api/types';
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
  await user.type(within(form).getByLabelText('Public host'), 'https://rrotor.acme.com/');
  await user.click(within(form).getByRole('button', { name: 'Register runtime' }));
  await screen.findByText('Runtime token for Acme production');
  return sent;
}

describe('Getting started', () => {
  it('is the first item in the sidebar, with its breadcrumb', async () => {
    renderApp('/getting-started');
    expect(await screen.findByRole('heading', { name: 'Getting started', level: 1 })).toBeInTheDocument();
    const sidebar = screen.getByRole('complementary', { name: 'Main' });
    expect(within(sidebar).getAllByRole('link')[0]).toHaveAccessibleName('Getting started');
    expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText('Getting started')).toHaveAttribute('aria-current', 'page');
    expect(screen.getAllByRole('link', { name: 'self-hosting docs' })[0]).toHaveAttribute('href', 'https://github.com/glyphh-ai/rrotor/tree/main/docs/self-hosting');
  });

  it('gives the SDKs and the Claude plugin to copy', async () => {
    const { user } = renderApp('/getting-started');
    expect(await screen.findByText('pip install glyphh')).toBeInTheDocument();
    expect(screen.getByText('npm i @glyphh-ai/glyphh')).toBeInTheDocument();
    expect(screen.getByText('/plugin marketplace add glyphh-ai/glyphh')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Copy plugin command' }));
    expect(await navigator.clipboard.readText()).toBe('/plugin install glyphh@glyphh');
  });

  it('is reached from Home when there is no runtime yet', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json(noRuntime)));
    const { user } = renderApp('/');
    await screen.findByText('No runtime yet');
    await user.click(within(screen.getByRole('main')).getByRole('link', { name: 'Getting started' }));
    expect(await screen.findByRole('heading', { name: 'Getting started', level: 1 })).toBeInTheDocument();
  });

  describe('Glyphh hosted', () => {
    it('makes a first machine with a name and a size, then gives its connector URL', async () => {
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
      const { user } = renderApp('/getting-started');
      expect(await screen.findByRole('radio', { name: /^Glyphh hosted/ })).toBeChecked();
      const form = await screen.findByRole('form', { name: 'Make your machine' });
      expect(within(form).getByLabelText('Name')).toHaveValue('Main');
      expect(within(form).getByRole('radio', { name: /^Small/ })).toBeChecked();
      await user.clear(within(form).getByLabelText('Name'));
      await user.type(within(form).getByLabelText('Name'), 'Work');
      await user.click(within(form).getByRole('radio', { name: /^Medium/ }));
      await user.click(within(form).getByRole('button', { name: 'Make your machine' }));
      expect(await screen.findByText('https://chris-7f3a.glyphh.app/mcp')).toBeInTheDocument();
      expect(sent).toEqual({ name: 'Work', size: 'medium' });
      expect(screen.getByRole('heading', { name: 'Connect Claude to Work' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^Start/ })).not.toBeInTheDocument();
      expect(within(screen.getByRole('main')).getByRole('link', { name: 'Machines' })).toHaveAttribute('href', '/machines');
    });

    it('says hosting is on Pro and Team, and running it yourself is free', async () => {
      renderApp('/getting-started');
      expect(await screen.findByRole('radio', { name: /^Glyphh hosted.*On Pro and Team\./ })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /^Docker Compose.*Free\./ })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /^Helm.*Free\./ })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /^Terraform.*Free\./ })).toBeInTheDocument();
      expect(screen.getByText(/Running it yourself is free on every plan/)).toBeInTheDocument();
    });

    it('shows the plan’s rate on each size of the first machine, and Enterprise’s as set in the contract', async () => {
      server.use(http.get(v1('/runtimes'), () => HttpResponse.json([])));
      const { client } = renderApp('/getting-started');
      const form = await screen.findByRole('form', { name: 'Make your machine' });
      expect(await within(form).findByText('$8.71 / month')).toBeInTheDocument();
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3] })));
      await client.invalidateQueries({ queryKey: ['me'] });
      expect(await within(form).findAllByText('Set in your contract.')).toHaveLength(3);
      expect(within(form).queryByText(/\/ month/)).not.toBeInTheDocument();
    });

    it('on Free, says hosting is on Pro and Team, with their rates and Upgrade', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[0] })), http.get(v1('/runtimes'), () => HttpResponse.json([])));
      const { user, router } = renderApp('/getting-started');
      expect(await screen.findByText(/Glyphh hosts machines on Pro and Team\./)).toBeInTheDocument();
      expect(screen.queryByRole('form', { name: 'Make your machine' })).not.toBeInTheDocument();
      const table = await screen.findByRole('table', { name: 'Hosted machine rates' });
      expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Size', 'Pro', 'Team']);
      await user.click(screen.getByRole('button', { name: 'Upgrade' }));
      expect(router.state.location.pathname).toBe('/settings/plans');
    });

    it('on Free, asks a member to ask their admin', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member', plan: plans[0] })), http.get(v1('/runtimes'), () => HttpResponse.json([])));
      renderApp('/getting-started');
      expect(await screen.findByText(/Ask your admin to upgrade\./)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Upgrade' })).not.toBeInTheDocument();
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
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('button', { name: 'Start' }));
      await vi.waitFor(() => expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument());
      expect(started).toBe('rt-2b8e41');
      expect(screen.getByText('https://chris-2b8e.glyphh.app/mcp')).toBeInTheDocument();
    });

    it('says plainly when the plan has no room for the machine to start, with the way to Billing', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([machines[1]])),
        http.post(v1('/runtimes/:id/start'), () => apiError(403, 'E_LIMIT', 'Free has no hosted machines.', { reason: 'machines' })),
      );
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('button', { name: 'Start' }));
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Your plan has no room for this machine, so it stays stopped.');
      expect(within(alert).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
    });

    it('shows the server’s refusal when starting fails', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([machines[1]])),
        http.post(v1('/runtimes/:id/start'), () => apiError(503, 'E_UNAVAILABLE', 'Hosting is off right now.')),
      );
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('button', { name: 'Start' }));
      expect(await screen.findByText('Hosting is off right now.')).toBeInTheDocument();
    });

    it('sends a person at the plan’s limit to Billing', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([])),
        http.post(v1('/runtimes'), () => apiError(403, 'E_LIMIT', 'Free allows 1 machine.', { reason: 'machines' })),
      );
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('button', { name: 'Make your machine' }));
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Your plan has no room for another machine.');
      expect(within(alert).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
    });

    it('says plainly when the server has stopped hosting machines, with the way to run rrotor yourself', async () => {
      server.use(
        http.get(v1('/runtimes'), () => HttpResponse.json([])),
        http.post(v1('/runtimes'), () => apiError(409, 'E_UNAVAILABLE', 'Hosting is off.', { reason: 'hosting_off' })),
      );
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('button', { name: 'Make your machine' }));
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Glyphh is not hosting machines now. Run rrotor yourself with Docker Compose, Helm or Terraform.');
      expect(within(alert).getByRole('link', { name: 'Getting started' })).toHaveAttribute('href', '/getting-started');
    });

    it('says so when the machines cannot be read', async () => {
      server.use(http.get(v1('/runtimes'), () => apiError(500, 'E_INTERNAL', 'The machines could not be read.')));
      renderApp('/getting-started');
      expect(await screen.findByText('The machines could not be read.')).toBeInTheDocument();
    });
  });

  describe('self-hosted', () => {
    it('registers with the host alone, shows the token once and the Compose env filled in', async () => {
      const { user } = renderApp('/getting-started');
      const sent = await register(user, 'Docker Compose');
      expect(sent).toEqual([{ name: 'Acme production', public_url: 'https://rrotor.acme.com' }]);
      expect(screen.getByText('glyphh_rt_secret')).toBeInTheDocument();
      expect(screen.getByText(/RROTOR_RUNTIME_TOKEN=glyphh_rt_secret/)).toBeInTheDocument();
      expect(screen.getByText(/docker compose up -d/)).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Copy .env' }));
      expect(await navigator.clipboard.readText()).toContain('RROTOR_PUBLIC_HOST=rrotor.acme.com');
      expect(screen.getByText('https://rrotor.acme.com/mcp')).toBeInTheDocument();
    });

    it('keeps the registration on changing option: Helm with its values, then Terraform for AWS and GCP', async () => {
      const { user } = renderApp('/getting-started');
      await register(user, 'Docker Compose');

      await user.click(screen.getByRole('radio', { name: /^Helm/ }));
      await user.selectOptions(screen.getByLabelText('Size'), 'Large');
      await user.clear(screen.getByLabelText('Ingress class'));
      await user.type(screen.getByLabelText('Ingress class'), 'traefik');
      const helm = screen.getByText(/helm install rrotor/);
      expect(helm).toHaveTextContent('--set runtime.token=glyphh_rt_secret');
      expect(helm).toHaveTextContent('--set size=large');
      expect(helm).toHaveTextContent('--set ingress.className=traefik');

      await user.click(screen.getByRole('radio', { name: /^Terraform/ }));
      expect(screen.getByText(/module "rrotor"/)).toHaveTextContent('//deploy/terraform/aws');
      await user.selectOptions(screen.getByLabelText('Cloud'), 'GCP');
      await user.type(screen.getByLabelText('Project'), 'acme-prod');
      const gcp = screen.getByText(/module "rrotor"/);
      expect(gcp).toHaveTextContent('//deploy/terraform/gcp');
      expect(gcp).toHaveTextContent('project = "acme-prod"');
      expect(gcp).toHaveTextContent('region = "europe-west2"');
      await user.clear(screen.getByLabelText('Region'));
      await user.type(screen.getByLabelText('Region'), 'us-east1');
      expect(screen.getByText(/module "rrotor"/)).toHaveTextContent('region = "us-east1"');

      await user.click(screen.getByRole('button', { name: 'Register another' }));
      expect(screen.getByRole('form', { name: 'Register a runtime' })).toBeInTheDocument();
      expect(screen.queryByText('glyphh_rt_secret')).not.toBeInTheDocument();
    });

    it('asks for a host it can use before registering', async () => {
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('radio', { name: /^Helm/ }));
      const button = screen.getByRole('button', { name: 'Register runtime' });
      await user.type(screen.getByLabelText('Name'), 'Lab');
      await user.type(screen.getByLabelText('Public host'), 'localhost');
      expect(screen.getByText('Use the host alone, such as rrotor.acme.com.')).toBeInTheDocument();
      expect(button).toBeDisabled();
    });

    it('shows why a runtime could not be registered', async () => {
      server.use(http.post(v1('/runtimes/self'), () => apiError(403, 'E_NOT_IN_PLAN', 'Self-hosting needs the Team plan.')));
      const { user } = renderApp('/getting-started');
      await user.click(await screen.findByRole('radio', { name: /^Terraform/ }));
      await user.type(screen.getByLabelText('Name'), 'Lab');
      await user.type(screen.getByLabelText('Public host'), 'rrotor.lab.acme.com');
      await user.click(screen.getByRole('button', { name: 'Register runtime' }));
      expect(await screen.findByText('Self-hosting needs the Team plan.')).toBeInTheDocument();
    });
  });

  describe('the self-hosted runtimes', () => {
    it('lists each with its state, version and last heartbeat', async () => {
      renderApp('/getting-started');
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      const [acme, lab] = within(list).getAllByRole('listitem');
      expect(within(acme!).getByText('Acme production')).toBeInTheDocument();
      expect(within(acme!).getByText('Running')).toBeInTheDocument();
      expect(within(acme!).getByText(/^rrotor\.acme\.com · 1\.4\.2 · last heartbeat /)).toBeInTheDocument();
      expect(within(lab!).getByText('Not seen yet')).toBeInTheDocument();
      expect(within(lab!).getByText('rrotor.lab.acme.com · no heartbeat yet')).toBeInTheDocument();
    });

    it('shows nothing when there are none', async () => {
      server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([])));
      renderApp('/getting-started');
      await screen.findByText('pip install glyphh');
      expect(screen.queryByText('Your self-hosted runtimes')).not.toBeInTheDocument();
    });

    it('says so when the list cannot be read', async () => {
      server.use(http.get(v1('/runtimes/self'), () => apiError(500, 'E_INTERNAL', 'The runtimes could not be read.')));
      renderApp('/getting-started');
      expect(await screen.findByText('The runtimes could not be read.')).toBeInTheDocument();
    });

    it('rotates a token after asking and shows the new one once', async () => {
      let rotated = '';
      server.use(
        http.post(v1('/runtimes/self/:id/token'), ({ params }) => {
          rotated = String(params.id);
          return HttpResponse.json({ token: 'glyphh_rt_new' });
        }),
      );
      const { user } = renderApp('/getting-started');
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      await user.click(within(list).getAllByRole('button', { name: 'Rotate token' })[0]!);
      const confirm = screen.getByRole('dialog', { name: 'Rotate this runtime’s token?' });
      await user.click(within(confirm).getByRole('button', { name: 'Rotate' }));
      const shown = await screen.findByRole('dialog', { name: 'The new runtime token' });
      expect(rotated).toBe('rt-self-1');
      expect(within(shown).getByText('glyphh_rt_new')).toBeInTheDocument();
      expect(within(shown).getByText(/set it as RROTOR_RUNTIME_TOKEN for Acme production/)).toBeInTheDocument();
      await user.click(within(shown).getByRole('button', { name: 'Done' }));
      expect(screen.queryByText('glyphh_rt_new')).not.toBeInTheDocument();
    });

    it('shows why a token could not be rotated, and forgets it on cancel', async () => {
      server.use(http.post(v1('/runtimes/self/:id/token'), () => apiError(404, 'E_NOT_FOUND', 'No such runtime.')));
      const { user } = renderApp('/getting-started');
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      await user.click(within(list).getAllByRole('button', { name: 'Rotate token' })[0]!);
      const confirm = screen.getByRole('dialog', { name: 'Rotate this runtime’s token?' });
      await user.click(within(confirm).getByRole('button', { name: 'Rotate' }));
      expect(await within(confirm).findByText('No such runtime.')).toBeInTheDocument();
      await user.click(within(confirm).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByText('No such runtime.')).not.toBeInTheDocument();
    });

    it('deletes a runtime after asking', async () => {
      let rows = selfRuntimes;
      server.use(
        http.get(v1('/runtimes/self'), () => HttpResponse.json(rows)),
        http.delete(v1('/runtimes/self/:id'), ({ params }) => {
          rows = rows.filter((r) => r.id !== params.id);
          return new HttpResponse(null, { status: 204 });
        }),
      );
      const { user } = renderApp('/getting-started');
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      await user.click(within(list).getAllByRole('button', { name: 'Delete' })[1]!);
      const confirm = screen.getByRole('dialog', { name: 'Delete this runtime?' });
      expect(within(confirm).getByText('Lab')).toBeInTheDocument();
      await user.click(within(confirm).getByRole('button', { name: 'Delete' }));
      await vi.waitFor(() => expect(within(list).queryByText('Lab')).not.toBeInTheDocument());
      await user.click(within(list).getByRole('button', { name: 'Delete' }));
      await user.click(within(screen.getByRole('dialog', { name: 'Delete this runtime?' })).getByRole('button', { name: 'Cancel' }));
      expect(within(list).getByText('Acme production')).toBeInTheDocument();
    });

    it('issues an offline licence on Enterprise, for a year by default, and says where it goes', async () => {
      let sent: unknown;
      server.use(
        http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3] })),
        http.post(v1('/runtimes/:id/offline-licence'), async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json({ token: 'eyJwYXlsb2FkIjp7fX0', expires_at: '2027-10-18T00:00:00Z' });
        }),
      );
      const { user, client } = renderApp('/getting-started');
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
      await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[0]!);
      const dialog = screen.getByRole('dialog', { name: 'Issue an offline licence' });
      expect(within(dialog).getByLabelText('Days')).toHaveValue(365);
      await user.click(within(dialog).getByRole('button', { name: 'Issue licence' }));
      const shown = await screen.findByRole('dialog', { name: 'The offline licence' });
      expect(sent).toEqual({ days: 365 });
      expect(within(shown).getByText('eyJwYXlsb2FkIjp7fX0')).toBeInTheDocument();
      expect(within(shown).getByText(/Set it as RROTOR_LICENCE for Acme production.*It expires 18 Oct 2027\./)).toBeInTheDocument();
      await user.click(within(shown).getByRole('button', { name: 'Copy licence' }));
      expect(await navigator.clipboard.readText()).toBe('eyJwYXlsb2FkIjp7fX0');
      await user.click(within(shown).getByRole('button', { name: 'Done' }));
      expect(screen.queryByRole('dialog', { name: 'The offline licence' })).not.toBeInTheDocument();
    });

    it('takes from 1 to 365 days, and shows a refusal', async () => {
      server.use(
        http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3] })),
        http.post(v1('/runtimes/:id/offline-licence'), () => apiError(403, 'E_NOT_IN_PLAN', 'Offline licences are on Enterprise.', { reason: 'offline' })),
      );
      const { user, client } = renderApp('/getting-started');
      await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[1]!);
      const dialog = screen.getByRole('dialog', { name: 'Issue an offline licence' });
      const days = within(dialog).getByLabelText('Days');
      await user.clear(days);
      await user.type(days, '400');
      expect(within(dialog).getByText('From 1 to 365 days.')).toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: 'Issue licence' })).toBeDisabled();
      await user.clear(days);
      await user.type(days, '30');
      await user.click(within(dialog).getByRole('button', { name: 'Issue licence' }));
      expect(await within(dialog).findByText('Offline licences are on Enterprise.')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('dialog', { name: 'Issue an offline licence' })).not.toBeInTheDocument();
    });

    it('says offline licences are on Enterprise on other plans, with Talk to us', async () => {
      const { user, client } = renderApp('/getting-started');
      const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
      await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
      await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[0]!);
      const dialog = screen.getByRole('dialog', { name: 'Offline licences are on Enterprise' });
      expect(within(dialog).queryByLabelText('Days')).not.toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
      await user.click(within(dialog).getByRole('button', { name: 'Close' }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});

describe('Getting started while Glyphh hosts nothing', () => {
  it.each(['off', 'empty'] as const)('offers only running rrotor yourself, Docker Compose first, when the rates answer %s', async (rates) => {
    server.use(...hostingOffHandlers(rates));
    renderApp('/getting-started');
    const compose = await screen.findByRole('radio', { name: /^Docker Compose/ });
    expect(compose).toBeChecked();
    expect(screen.getAllByRole('radio').map((radio) => (radio as HTMLInputElement).value)).toEqual(['compose', 'helm', 'terraform']);
    expect(screen.queryByRole('radio', { name: /^Glyphh hosted/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Glyphh runs it for you/)).not.toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Register a runtime' })).toBeInTheDocument();
    expect(screen.queryByRole('form', { name: 'Make your machine' })).not.toBeInTheDocument();
  });

  it('registers a self-hosted runtime as before', async () => {
    server.use(...hostingOffHandlers());
    const { user } = renderApp('/getting-started');
    const sent = await register(user, 'Helm');
    expect(sent).toEqual([{ name: 'Acme production', public_url: 'https://rrotor.acme.com' }]);
    expect(screen.getByText(/helm install/)).toBeInTheDocument();
  });

  it('lists the self-hosted runtimes, and offline licences stay on Enterprise', async () => {
    server.use(...hostingOffHandlers());
    const { user } = renderApp('/getting-started');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    expect(within(list).getByText('Acme production')).toBeInTheDocument();
    await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[0]!);
    expect(await screen.findByRole('dialog', { name: 'Offline licences are on Enterprise' })).toBeInTheDocument();
  });
});
