import { screen, within } from '@testing-library/react';
import { renderApp } from '@/test/render';
import { models } from '@/test/fixtures';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

describe('Models', () => {
  it('shows each version by commit, newest first, and where it is active', async () => {
    renderApp('/models');
    expect(await screen.findByRole('heading', { name: 'invoice-triage' })).toBeInTheDocument();
    expect(screen.getByText('glyphh-ai/invoice-triage')).toBeInTheDocument();
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]!).getByText('v2')).toBeInTheDocument();
    expect(within(rows[0]!).getByText('8be41c0')).toBeInTheDocument();
    expect(within(rows[0]!).getByText('Active')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Not active')).toBeInTheDocument();
  });

  it('deletes a model after asking', async () => {
    let deleted = '';
    server.use(
      http.delete(v1('/models/:id'), ({ params }) => {
        deleted = String(params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderApp('/models');
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Delete this model?' })).getByRole('button', { name: 'Delete' }));
    await vi.waitFor(() => expect(deleted).toBe('m-1'));
  });

  it('says how to make the first one', async () => {
    server.use(http.get(v1('/models'), () => HttpResponse.json([])));
    renderApp('/models');
    expect(await screen.findByText('No models yet')).toBeInTheDocument();
  });

  it('says when a model has no versions yet', async () => {
    server.use(http.get(v1('/models'), () => HttpResponse.json([{ ...models[0], repo: null, versions: [] }])));
    renderApp('/models');
    expect(await screen.findByText('No versions yet.')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('keeps the model when the person cancels', async () => {
    let deleted = false;
    server.use(
      http.delete(v1('/models/:id'), () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderApp('/models');
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Delete this model?' })).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'invoice-triage' })).toBeInTheDocument();
    expect(deleted).toBe(false);
  });

  it('shows the server’s refusal when the models cannot be read', async () => {
    server.use(http.get(v1('/models'), () => apiError(403, 'E_FORBIDDEN', 'Ada is not on your plan.')));
    renderApp('/models');
    expect(await screen.findByText('Ada is not on your plan.')).toBeInTheDocument();
  });
});
