import { screen, within } from '@testing-library/react';
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

/** Ada Cloud on, and the library as the server answers it; each install and removal flips it, as the server does. */
function on(start = false) {
  let installed = start;
  const seen: string[] = [];
  server.use(
    ...adaFake({}).handlers,
    http.get('*/api/v1/templates', () => HttpResponse.json({ templates: [memory(installed)] })),
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
  );
  return seen;
}

describe('the Templates page', () => {
  it('is in the sidebar under Ada and shows each template with what it keeps and the tools it adds', async () => {
    on();
    const { user, router } = renderApp('/models');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    await user.click(await within(sidebar).findByRole('link', { name: 'Templates' }));
    expect(router.state.location.pathname).toBe('/templates');
    const card = await screen.findByRole('region', { name: 'Agentic memory' });
    expect(card).toHaveTextContent('Your glyphh: what any AI you use knows about you.');
    expect(within(card).getByRole('list', { name: "Agentic memory's models" })).toHaveTextContent('What it knows about you');
    expect(within(card).getByRole('list', { name: "Agentic memory's tools" })).toHaveTextContent('glyphh_recall');
    expect(card).toHaveTextContent('yours alone, not your org’s');
  });

  it('installs a template, then removes it once its slug is typed', async () => {
    const seen = on();
    const { user } = renderApp('/templates');
    const card = await screen.findByRole('region', { name: 'Agentic memory' });
    await user.click(within(card).getByRole('button', { name: 'Install' }));
    expect(await within(card).findByText('Installed')).toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Remove' }));
    const dialog = await screen.findByRole('dialog');
    const remove = within(dialog).getByRole('button', { name: 'Remove' });
    expect(remove).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Type agentic-memory'), 'agentic-memory');
    await user.click(remove);
    expect(await within(card).findByRole('button', { name: 'Install' })).toBeInTheDocument();
    expect(seen).toEqual(['install agentic-memory', 'remove agentic-memory']);
  });

  it('says what the server refused', async () => {
    on();
    server.use(http.post('*/api/v1/templates/:slug/install', () => apiError(503, 'E_UNAVAILABLE', 'Ada Cloud is busy.')));
    const { user } = renderApp('/templates');
    const card = await screen.findByRole('region', { name: 'Agentic memory' });
    await user.click(within(card).getByRole('button', { name: 'Install' }));
    expect(await within(card).findByText(/Ada Cloud is busy/)).toBeInTheDocument();
  });

  it('cancels a removal', async () => {
    on(true);
    const { user } = renderApp('/templates');
    await user.click(await screen.findByRole('button', { name: 'Remove' }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
