import { screen, within } from '@testing-library/react';
import type { AdaModel, Spec } from '@/api/ada';
import { adaFake, emptyStats, modelStats, tickets, ticketSpec } from '@/test/ada';
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

  it('shows the last 30 days for a model made today, the days before it empty', async () => {
    server.use(...adaFake({ models: [{ ...tickets(), precedents: 0 }], stats: emptyStats }).handlers);
    renderApp('/models/tickets');
    expect(await screen.findByText('Reads, the last 30 days')).toBeInTheDocument();
    expect(screen.getByText('Asked a person, the last 30 days')).toBeInTheDocument();
  });

  it('shows one output of 77 outcomes as its most common and the rest as one bar, and says when it is estimated', async () => {
    const many = (model: AdaModel) => ({
      ...modelStats(model),
      outcomes: Array.from({ length: 50 }, (_, i) => ({ output: null, value: `intent-${i}`, n: 100 - i })),
      others: [{ output: null, values: 27, n: 27 }],
      estimated: true,
    });
    server.use(...adaFake({ models: [tickets()], stats: many }).handlers);
    renderApp('/models/tickets');
    const outcomes = await screen.findByRole('table', { name: 'Precedents by outcome' });
    expect(within(outcomes).getAllByRole('row')).toHaveLength(14); // the header, 12 outcomes, the rest
    expect(within(outcomes).getByRole('row', { name: 'Other (65 outcomes) 2,668' })).toBeInTheDocument();
    expect(screen.getAllByText(/Estimated from a sample/)).toHaveLength(2);
  });

  it('shows each named output’s decides apart, and when each asks a person', async () => {
    const spec: Spec = { ...ticketSpec, output: undefined, outputs: { team: { values: ['billing', 'tech'] }, urgent: { values: ['yes', 'no'], ask: 0.3 } } };
    const days = (decided: number, asked: number) => Array.from({ length: 7 }, (_, i) => (i === 6 ? { decided, asked } : { decided: 0, asked: 0 }));
    const sure = (k: number) => Array.from({ length: 10 }, (_, i) => (i === k ? 5 : 0));
    const two = (model: AdaModel) => ({
      ...modelStats(model),
      answers: [
        { output: 'team', decided: 5, asked: 1, sure: sure(8), days: days(5, 1) },
        { output: 'urgent', decided: 5, asked: 5, sure: sure(3), days: days(5, 5) },
      ],
    });
    server.use(...adaFake({ models: [{ ...tickets(), spec }], stats: two }).handlers);
    const { user } = renderApp('/models/tickets');
    const pick = await screen.findByRole('combobox', { name: 'Output' });
    expect(within(pick).getAllByRole('option').map((o) => o.textContent)).toEqual(['team', 'urgent']);
    expect(screen.getByText(/sets neither ask nor ask_below/)).toBeInTheDocument();
    const asked = () => screen.getByRole('table', { name: 'Share of decides that asked a person, a day' });
    const sureTable = () => screen.getByRole('table', { name: 'Decides by how sure they were' });
    expect(within(asked()).getByRole('row', { name: '22 Oct 20%' })).toBeInTheDocument();
    expect(within(sureTable()).getByRole('row', { name: '80–90% 5' })).toBeInTheDocument();
    await user.selectOptions(pick, 'urgent');
    expect(screen.getByText('The share of a day’s decides that asked a person: every outcome’s expected cost was above 0.3.')).toBeInTheDocument();
    expect(within(asked()).getByRole('row', { name: '22 Oct 100%' })).toBeInTheDocument();
    expect(within(sureTable()).getByRole('row', { name: '30–40% 5' })).toBeInTheDocument();
  });

  it('says when a default output asks by both cost and confidence, and lists an output no longer in the spec', async () => {
    const both: Spec = { ...ticketSpec, output: { ask: 0.5, ask_below: 0.7 } };
    const gone = (model: AdaModel) => {
      const stats = modelStats(model);
      return { ...stats, answers: [...stats.answers!, { output: 'old', decided: 1, asked: 0, sure: Array<number>(10).fill(0), days: [] }] };
    };
    server.use(...adaFake({ models: [{ ...tickets(), spec: both }], stats: gone }).handlers);
    renderApp('/models/tickets');
    const pick = await screen.findByRole('combobox', { name: 'Output' });
    expect(within(pick).getAllByRole('option').map((o) => o.textContent)).toEqual(['The outcome', 'old']);
    expect(screen.getByText(/every outcome’s expected cost was above 0.5, or the top probability under 70%/)).toBeInTheDocument();
  });

  it('says when the one output asks by confidence, with nothing to pick', async () => {
    server.use(...adaFake({ models: [tickets()] }).handlers);
    renderApp('/models/tickets');
    expect(await screen.findByText('The share of a day’s decides that asked a person: the top probability was under 60%.')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Output' })).not.toBeInTheDocument();
  });

  it('shows a model that is read but never asked to decide', async () => {
    const reads = (model: AdaModel) => {
      const stats = emptyStats(model);
      return { ...stats, days: stats.days.map((d, i) => (i === 29 ? { ...d, reads: { ...d.reads, query: 3, facts: 2 } } : d)) };
    };
    server.use(...adaFake({ models: [tickets()], stats: reads }).handlers);
    renderApp('/models/tickets');
    expect(await screen.findByRole('table', { name: 'Reads a day: decides and other reads' })).toBeInTheDocument();
    expect(screen.getByText('No decides yet')).toBeInTheDocument();
    expect(screen.getAllByText('No decides in these days yet.')).toHaveLength(2);
  });

  it('shows the server’s refusal', async () => {
    server.use(...adaFake({ models: [tickets()] }).handlers);
    server.use(http.get('*/api/ada/v1/models/tickets/stats', () => apiError(422, 'E_SPEC', 'this model is above the reader’s clearance')));
    renderApp('/models/tickets');
    expect(await screen.findByText('this model is above the reader’s clearance')).toBeInTheDocument();
  });
});
