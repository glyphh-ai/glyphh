import { screen, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { me, plans } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server, v1 } from '@/test/server';

// rrotor switched off (lib/shelved; it ships on): with Ada Cloud on the platform is Ada's alone.
vi.mock('@/lib/shelved', () => ({ RROTOR_SHOWN: false }));

describe('rrotor shelved, with Ada Cloud on', () => {
  beforeEach(() => server.use(...adaFake({ models: [tickets()] }).handlers));

  it('lists Ada’s pages only in the sidebar', async () => {
    renderApp('/');
    const main = await screen.findByRole('complementary', { name: 'Main' });
    await within(main).findByRole('link', { name: 'Home' });
    expect(within(main).getAllByRole('link').map((link) => link.textContent)).toEqual(['Home', 'Models', 'Marketplace', 'API Keys', 'Usage', 'Bots']);
    expect(within(main).queryByRole('group', { name: 'Runtimes & licences' })).not.toBeInTheDocument();
  });

  it.each(['/runtimes', '/licence', '/apps', '/artifacts', '/runtime-keys', '/machines', '/getting-started', '/settings/licence'])(
    'sends %s to Home',
    async (path) => {
      const { router } = renderApp(path);
      expect(await screen.findByRole('heading', { name: /^Good (morning|afternoon|evening)/, level: 1 })).toBeInTheDocument();
      expect(router.state.location.pathname).toBe('/');
    },
  );

  it('asks for no reviewer groups on the Auth page', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[4] })));
    renderApp('/settings/auth');
    expect(await screen.findByLabelText('Issuer')).toBeInTheDocument();
    expect(screen.getByLabelText('Email domains')).toBeInTheDocument();
    expect(screen.queryByLabelText('Reviewer groups')).not.toBeInTheDocument();
  });
});
