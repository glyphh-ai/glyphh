import { screen, waitFor, within } from '@testing-library/react';
import { HttpResponse } from 'msw';
import type { Template } from '@/api/templates';
import { adaFake } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

const memory = (installed = false): Template => ({
  slug: 'agentic-memory',
  name: 'Agentic memory',
  category: 'Memory',
  summary: 'Your glyphh: what any AI you use knows about you.',
  version: 1,
  models: [{ key: 'memory', title: 'What it knows about you', about: 'facts about the person', model: 'me-abc-agentic-memory-memory' }],
  tools: [{ name: 'glyphh_recall', title: 'Recall', description: 'What the glyphh holds that bears on it.' }],
  instructions: 'Use it.',
  installed,
  installed_version: installed ? 1 : null,
});

const another = (n: number): Template => ({
  ...memory(),
  slug: `support-${n}`,
  name: `Support desk ${n}`,
  category: 'Support',
  summary: 'Routes each ticket.',
  tools: [{ name: `route_${n}`, title: 'Route', description: 'Routes it.' }],
});

/** Ada Cloud on, and the library as the server answers it; each install and removal flips it, as the server does. */
function on(start = false, more: Template[] = []) {
  let installed = start;
  const seen: string[] = [];
  server.use(
    ...adaFake({}).handlers,
    http.get('*/api/v1/templates', () => HttpResponse.json({ templates: [memory(installed), ...more] })),
    http.get('*/api/v1/templates/:slug', ({ params }) =>
      params.slug === 'agentic-memory' ? HttpResponse.json(memory(installed)) : apiError(404, 'E_TEMPLATE_MISSING', 'There is no such template.'),
    ),
    http.post('*/api/v1/templates/:slug/install', ({ params }) => {
      seen.push(`install ${params.slug}`);
      installed = true;
      return HttpResponse.json(memory(true));
    }),
    http.delete('*/api/v1/templates/:slug/install', ({ params }) => {
      seen.push(`remove ${params.slug}`);
      installed = false;
      return HttpResponse.json(memory(false));
    }),
    http.get('*/api/v1/bot-templates', () => HttpResponse.json({ templates: [] })),
  );
  return seen;
}

describe('the Marketplace’s models', () => {
  it('is Marketplace in the sidebar under Ada, on its Models tab, each template a card that opens its details', async () => {
    on();
    const { user, router } = renderApp('/models');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    expect(within(sidebar).queryByRole('link', { name: 'Templates' })).not.toBeInTheDocument();
    await user.click(await within(sidebar).findByRole('link', { name: 'Marketplace' }));
    expect(router.state.location.pathname).toBe('/marketplace/models');
    expect(await screen.findByRole('heading', { name: 'Marketplace', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Models' })).toHaveAttribute('aria-selected', 'true');
    const card = await screen.findByRole('link', { name: 'Agentic memory' });
    expect(card).toHaveTextContent('Your glyphh: what any AI you use knows about you.');
    expect(card).toHaveTextContent('1 model · 1 tool · v1');
    expect(card).toHaveTextContent('Memory');
    await user.click(card);
    expect(router.state.location.pathname).toBe('/marketplace/models/agentic-memory');
    expect(await screen.findByRole('heading', { name: 'Agentic memory', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: "Agentic memory's models" })).toHaveTextContent('What it knows about you');
    expect(screen.getByRole('list', { name: "Agentic memory's tools" })).toHaveTextContent('glyphh_recall');
    expect(screen.getByLabelText('About this template')).toHaveTextContent('Not installed');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Marketplaceagentic-memory');
    await user.click(within(screen.getByRole('main')).getAllByRole('link', { name: 'Marketplace' })[0]!);
    expect(router.state.location.pathname).toBe('/marketplace/models');
  });

  it('switches to the Bots tab, and the old Templates paths come here', async () => {
    on();
    const { user, router } = renderApp('/marketplace');
    expect(await screen.findByRole('tab', { name: 'Models' })).toHaveAttribute('aria-selected', 'true');
    expect(router.state.location.pathname).toBe('/marketplace/models');
    await user.click(screen.getByRole('tab', { name: 'Bots' }));
    expect(router.state.location.pathname).toBe('/marketplace/bots');
    expect(await screen.findByText('No bots yet')).toBeInTheDocument();

    const old = renderApp('/templates?q=memory');
    await waitFor(() => expect(old.router.state.location.pathname).toBe('/marketplace/models'));
    expect(old.router.state.location.search).toBe('?q=memory');
    const one = renderApp('/templates/agentic-memory');
    await waitFor(() => expect(one.router.state.location.pathname).toBe('/marketplace/models/agentic-memory'));
  });

  it('searches the library and pages it', async () => {
    on(false, Array.from({ length: 30 }, (_, i) => another(i + 1)));
    const { user } = renderApp('/marketplace/models');
    const grid = await screen.findByRole('list', { name: 'Model templates' });
    expect(within(grid).getAllByRole('link')).toHaveLength(24);
    expect(screen.getByRole('navigation', { name: 'Pages' })).toHaveTextContent('1–24 of 31');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(within(await screen.findByRole('list', { name: 'Model templates' })).getAllByRole('link')).toHaveLength(7);
    await user.type(screen.getByLabelText('Search'), 'route_7');
    expect(await screen.findByRole('link', { name: 'Support desk 7' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Agentic memory' })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing like it');
    expect(await screen.findByText('No template matches “nothing like it”.')).toBeInTheDocument();
  });

  it('installs a template from its details, then removes it once its slug is typed', async () => {
    const seen = on();
    const { user } = renderApp('/marketplace/models/agentic-memory');
    await user.click(await screen.findByRole('button', { name: 'Install' }));
    expect(await screen.findByText('Installed')).toBeInTheDocument();
    expect(screen.getByLabelText('About this template')).toHaveTextContent('Installed, v1');
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    const dialog = await screen.findByRole('dialog');
    const remove = within(dialog).getByRole('button', { name: 'Remove' });
    expect(remove).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Type agentic-memory'), 'agentic-memory');
    await user.click(remove);
    expect(await screen.findByRole('button', { name: 'Install' })).toBeInTheDocument();
    expect(seen).toEqual(['install agentic-memory', 'remove agentic-memory']);
  });

  it('says what the server refused, and a template that is not there', async () => {
    on();
    server.use(http.post('*/api/v1/templates/:slug/install', () => apiError(503, 'E_UNAVAILABLE', 'Ada Cloud is busy.')));
    const { user } = renderApp('/marketplace/models/agentic-memory');
    await user.click(await screen.findByRole('button', { name: 'Install' }));
    expect(await screen.findByText(/Ada Cloud is busy/)).toBeInTheDocument();
    renderApp('/marketplace/models/nope');
    expect(await screen.findByText(/There is no such template/)).toBeInTheDocument();
  });

  it('cancels a removal, and says when the library is empty', async () => {
    on(true);
    const { user } = renderApp('/marketplace/models/agentic-memory');
    await user.click(await screen.findByRole('button', { name: 'Remove' }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    server.use(http.get('*/api/v1/templates', () => HttpResponse.json({ templates: [] })));
    renderApp('/marketplace/models');
    expect(await screen.findByText('No models yet')).toBeInTheDocument();
  });
});
