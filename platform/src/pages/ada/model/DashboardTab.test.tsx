import { screen, within } from '@testing-library/react';
import { adaFake, emptyStats, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

describe('a model’s dashboard', () => {
  it('shows its precedents against the plan, its reads, how many asked, the live version, its charts and latest jobs', async () => {
    const fake = adaFake({ models: [tickets()] });
    server.use(...fake.handlers);
    renderApp('/models/tickets');
    expect(await screen.findByText('1,240 of 100,000 across your org’s models on Pro')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Your org’s precedents' })).toBeInTheDocument();
    expect(screen.getByText('Reads, the last 7 days')).toBeInTheDocument();
    expect(screen.getByText('238')).toBeInTheDocument(); // 210 decides, 21 queries, 7 facts
    expect(screen.getByText('Asked a person, the last 7 days').nextElementSibling).toHaveTextContent('10%'); // 21 of 210
    expect(screen.getByText('21 of 210 decides')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
    expect(screen.getByText(/Ask more ·/)).toBeInTheDocument();
    // Each chart is drawn on a canvas, with its numbers in a table for a screen reader.
    expect(screen.getByRole('img', { name: 'Reads a day: decides and other reads' })).toBeInTheDocument();
    const reads = screen.getByRole('table', { name: 'Reads a day: decides and other reads' });
    expect(within(reads).getByRole('row', { name: '22 Oct 60 7' })).toBeInTheDocument();
    const growth = screen.getByRole('table', { name: 'Precedents over time, by each case’s date' });
    expect(within(growth).getByRole('row', { name: '15 Oct 2026 1,240' })).toBeInTheDocument();
    const asked = screen.getByRole('table', { name: 'Share of decides that asked a person, a day' });
    expect(within(asked).getByRole('row', { name: '16 Oct –' })).toBeInTheDocument();
    expect(within(asked).getByRole('row', { name: '17 Oct 10%' })).toBeInTheDocument();
    const sure = screen.getByRole('table', { name: 'Decides by how sure they were' });
    expect(within(sure).getByRole('row', { name: '90–100% 102' })).toBeInTheDocument();
    const outcomes = screen.getByRole('table', { name: 'Precedents by outcome' });
    expect(within(outcomes).getByRole('row', { name: 'Ungraded 140' })).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Latest jobs' })).getByText('Import')).toBeInTheDocument();
  });

  it('says what will show before anything was read or recorded', async () => {
    const fake = adaFake({ models: [{ ...tickets(), precedents: 0 }], stats: emptyStats });
    server.use(...fake.handlers);
    renderApp('/models/tickets');
    expect(await screen.findByText('No reads in these days yet. Decides and other reads show here as they are made.')).toBeInTheDocument();
    expect(screen.getByText('No precedents yet. Import or record cases and they show here.')).toBeInTheDocument();
    expect(screen.getAllByText('No decides in these days yet.')).toHaveLength(2);
    expect(screen.getByText('No precedents yet.')).toBeInTheDocument();
    expect(screen.getByText('No imports, learns or backtests yet.')).toBeInTheDocument();
    expect(screen.getByText('Shows once decides are made')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: /Reads a day|Precedents/ })).not.toBeInTheDocument();
  });

  it('charts each named output, says when none is graded, and shows a plan with no limit', async () => {
    const named = (model: Parameters<typeof emptyStats>[0]) => ({
      ...emptyStats(model),
      precedents: 30,
      plan: { plan: 'Enterprise', precedents: { used: 30, max: null } },
      outcomes: [
        { output: null, value: null, n: 30 },
        { output: 'team', value: 'billing', n: 20 },
        { output: 'urgent', value: 'yes', n: 4 },
      ],
      jobs: [{ id: 'j', model: 'tickets', kind: 'learn', state: 'running' as const, percent: 40, args: {}, result: null, error: null, created_at: '2026-10-20T09:00:00Z', started_at: null, finished_at: null, made_by: 'u-chris' }],
    });
    server.use(...adaFake({ models: [tickets()], stats: named }).handlers);
    renderApp('/models/tickets');
    expect(await screen.findByRole('table', { name: 'Precedents by team' })).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Precedents by urgent' })).toBeInTheDocument();
    expect(screen.getByText('30 across your org’s models, no limit')).toBeInTheDocument();
    expect(screen.getByText('Running · 40%')).toBeInTheDocument();
  });

  it('says when no precedent is graded yet', async () => {
    const ungraded = (model: Parameters<typeof emptyStats>[0]) => ({ ...emptyStats(model), precedents: 5, outcomes: [{ output: null, value: null, n: 5 }] });
    server.use(...adaFake({ models: [tickets()], stats: ungraded }).handlers);
    renderApp('/models/tickets');
    expect(await screen.findByText('No precedent has an outcome yet.')).toBeInTheDocument();
  });

  it('shows the server’s refusal', async () => {
    server.use(...adaFake({ models: [tickets()] }).handlers);
    server.use(http.get('*/api/ada/v1/models/tickets/stats', () => apiError(422, 'E_SPEC', 'this model is above the reader’s clearance')));
    renderApp('/models/tickets');
    expect(await screen.findByText('this model is above the reader’s clearance')).toBeInTheDocument();
  });
});
