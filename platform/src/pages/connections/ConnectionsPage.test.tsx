import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { apps, botsFake } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

afterEach(() => vi.restoreAllMocks());

describe('the Connections page', () => {
  it('connects a catalog app from its card’s + straight away, then lands on its tools; the card itself opens its page', async () => {
    const fake = on();
    const popup = { closed: false, close: vi.fn() };
    const open = vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
    const { user, router } = renderApp('/connections?tab=catalog');
    const catalog = await screen.findByRole('list', { name: 'Catalog' });
    const notion = await within(catalog).findByRole('button', { name: 'Connect Notion' });
    expect(within(catalog).getByRole('button', { name: 'Add another Gmail account' })).toBeInTheDocument();
    // The + sits beside the card's link, never inside it.
    expect(notion.closest('a')).toBeNull();
    await user.click(notion);
    await waitFor(() => expect(open).toHaveBeenCalledWith('https://pipedream.test/connect/notion', 'glyphh-connect', expect.any(String)));
    expect(within(await screen.findByRole('dialog')).getByRole('status')).toHaveTextContent('Connecting Notion…');
    window.dispatchEvent(new Event('focus'));
    expect(await screen.findByText('Notion is connected.')).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/connections/notion'));
    expect(router.state.location.search).toBe('?tab=tools');
    expect(fake.state.seen).toEqual(['link notion', 'sync']);

    const again = renderApp('/connections?tab=catalog');
    await user.click(await within(await screen.findAllByRole('list', { name: 'Catalog' }).then((l) => l.at(-1)!)).findByRole('link', { name: /Slack/ }));
    expect(again.router.state.location.pathname).toBe('/connections/slack');
  });

  it('shows your connections first, one row an app, searchable', async () => {
    on();
    const { user } = renderApp('/connections');
    const yours = await screen.findByRole('list', { name: 'Your connections' });
    expect(within(yours).getAllByRole('link').map((l) => l.textContent)).toEqual([expect.stringContaining('Gmail'), expect.stringContaining('Slack')]);
    expect(yours).toHaveTextContent('chris@example.com · Connected');
    expect(screen.getByRole('tab', { name: 'Yours' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('BotsConnections');
    await user.type(screen.getByLabelText('Search'), 'sla');
    await waitFor(() => expect(within(screen.getByRole('list', { name: 'Your connections' })).getAllByRole('link')).toHaveLength(1));
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'zzz');
    expect(await screen.findByText('Nothing matches')).toBeInTheDocument();
  });

  it('sorts your connections by the newest', async () => {
    const at = (day: number) => `2026-11-${String(day).padStart(2, '0')}T00:00:00Z`;
    on({
      connections: [
        { id: 'c-a', app: 'airtable', app_name: 'Airtable', app_icon: null, account_id: 'a', label: null, permissions: {}, created_at: at(1) },
        { id: 'c-z', app: 'zoom', app_name: 'Zoom', app_icon: 'https://icons.test/zoom.png', account_id: 'z', label: null, permissions: {}, created_at: at(20) },
        { id: 'c-z2', app: 'zoom', app_name: 'Zoom', app_icon: null, account_id: 'z2', label: null, permissions: {}, created_at: at(19) },
      ],
    });
    const { user } = renderApp('/connections');
    const names = async () => within(await screen.findByRole('list', { name: 'Your connections' })).getAllByRole('link').map((l) => l.textContent);
    expect(await names()).toEqual([expect.stringContaining('Airtable'), expect.stringContaining('2 accounts')]);
    await user.click(screen.getByRole('button', { name: 'Filter' }));
    await user.click(screen.getByRole('menuitemradio', { name: 'Recently connected' }));
    await waitFor(async () => expect((await names())[0]).toContain('Zoom'));
  });

  it('shows the catalog with what is added, filtered and searched', async () => {
    on();
    const { user } = renderApp('/connections');
    await user.click(await screen.findByRole('tab', { name: 'Catalog' }));
    const catalog = await screen.findByRole('list', { name: 'Catalog' });
    await waitFor(() => expect(within(catalog).getAllByRole('link')).toHaveLength(3));
    expect(within(catalog).getByRole('link', { name: /Gmail/ })).toHaveTextContent('Added');
    expect(within(catalog).getByRole('link', { name: /Notion/ })).not.toHaveTextContent('Added');
    await user.click(screen.getByRole('button', { name: 'Filter' }));
    await user.click(screen.getByRole('menuitemradio', { name: 'Not connected' }));
    await waitFor(() => expect(within(screen.getByRole('list', { name: 'Catalog' })).getAllByRole('link')).toHaveLength(1));
    await user.click(screen.getByRole('button', { name: 'Filter' }));
    await user.click(screen.getByRole('menuitemradio', { name: 'All apps' }));
    await user.type(screen.getByLabelText('Search'), 'xyz');
    expect(await screen.findByText('No app matches “xyz”.')).toBeInTheDocument();
  });

  it('pages through the catalog by its cursor', async () => {
    on();
    const asked: string[] = [];
    server.use(
      http.get('*/api/v1/connections/apps', ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor') ?? '';
        asked.push(cursor);
        return cursor ? HttpResponse.json({ apps: [apps[2]], next_cursor: null }) : HttpResponse.json({ apps: apps.slice(0, 2), next_cursor: 'c2' });
      }),
    );
    const { user } = renderApp('/connections?tab=catalog');
    const catalog = await screen.findByRole('list', { name: 'Catalog' });
    await waitFor(() => expect(within(catalog).getAllByRole('link')).toHaveLength(2));
    await user.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(within(catalog).getAllByRole('link')).toHaveLength(3));
    expect(screen.queryByRole('button', { name: 'Show more' })).not.toBeInTheDocument();
    expect(asked).toEqual(['', 'c2']);
  });

  it('sends you to the catalog when nothing is connected', async () => {
    on({ connections: [] });
    const { user } = renderApp('/connections');
    expect(await screen.findByText('No connections yet')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Browse the catalog' }));
    expect(await screen.findByRole('tab', { name: 'Catalog' })).toHaveAttribute('aria-selected', 'true');
  });

  it('says plainly when Pipedream is not set up', async () => {
    on({ off: true });
    renderApp('/connections');
    expect(await screen.findByText('Connections are not set up')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Catalog' })).not.toBeInTheDocument();
  });
});
