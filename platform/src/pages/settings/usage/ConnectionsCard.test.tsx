import { screen, within } from '@testing-library/react';
import type { ConnectionUsage } from '@/api/types';
import { adaFake } from '@/test/ada';
import { billing } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server, v1 } from '@/test/server';

const connections = (given: Partial<ConnectionUsage> = {}): ConnectionUsage => ({
  used: 2,
  included: null,
  over: 0,
  cents_a_month: null,
  due_cents: null,
  ...given,
});

const answer = (c: ConnectionUsage) => server.use(http.get(v1('/billing'), () => HttpResponse.json({ ...billing, connections: c })));

async function card() {
  return screen.findByRole('region', { name: 'Connections' });
}

describe('Usage’s connections', () => {
  it('counts them, every one included while no price is set', async () => {
    answer(connections());
    renderApp('/usage');
    const shown = await card();
    expect(shown).toHaveTextContent('2connections');
    expect(shown).toHaveTextContent('Every connection is included in your plan.');
    expect(within(shown).getByRole('link', { name: 'See them' })).toHaveAttribute('href', '/connections');
    expect(within(shown).queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('says one connection, and a cap with no price yet charges nothing', async () => {
    answer(connections({ used: 1, included: 3 }));
    const first = renderApp('/usage');
    const shown = await card();
    expect(shown).toHaveTextContent('1of 3 connections');
    expect(within(shown).getByRole('progressbar', { name: 'Connections' })).toHaveAttribute('aria-valuemax', '3');
    expect(shown).toHaveTextContent('Past 3, connections are not charged yet.');
    first.unmount();
    answer(connections({ used: 1 }));
    renderApp('/usage');
    expect(await card()).toHaveTextContent('1connection');
  });

  it('prices those past the plan, once priced', async () => {
    answer(connections({ used: 1, included: 2, cents_a_month: 500 }));
    const first = renderApp('/usage');
    expect(await card()).toHaveTextContent('Past 2, $5 a connection a month.');
    first.unmount();
    answer(connections({ used: 4, included: 2, over: 2, cents_a_month: 500, due_cents: 1_000 }));
    renderApp('/usage');
    expect(await card()).toHaveTextContent('2 past the plan at $5 each: $10 a month.');
  });

  it('shows on Ada Cloud’s Usage too, and not at all from a server without them', async () => {
    server.use(...adaFake({}).handlers, http.get(v1('/billing'), () => HttpResponse.json({ ...billing, connections: connections() })));
    renderApp('/usage');
    expect(await card()).toHaveTextContent('Every connection is included');
  });

  it('is not there from a server that leaves them out', async () => {
    renderApp('/usage');
    expect(await screen.findByText('On Pro.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Connections' })).not.toBeInTheDocument();
  });
});
