import { screen, waitFor, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { llmBilling, tokenUsage } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, llmHandlers, server, v1 } from '@/test/server';
import { axisDays, rangeDays, tokensOn } from './days';

const rowsOf = (name: string) =>
  within(screen.getByRole('table', { name }))
    .getAllByRole('row')
    .slice(1)
    .map((row) => row.textContent);

const sonnet = { id: 'claude-sonnet-5-5', name: 'Claude Sonnet 5.5', kind: 'bot' as const, input_tokens: 1_000, output_tokens: 200, requests: 3, charged_cents: 2.5 };
const sonnetDay = { day: '2026-11-09', model: 'claude-sonnet-5-5', input_tokens: 5_000, output_tokens: 1_000, requests: 4, charged_cents: 40 };

/** The days each request for the series and the tokens asked for. */
function watchDays() {
  const asked: string[] = [];
  server.use(
    http.get(v1('/billing'), () => HttpResponse.json({ ...llmBilling, tokens: { ...tokenUsage, models: [...tokenUsage.models, sonnet] } })),
    http.get(v1('/llm/usage'), ({ request }) => {
      asked.push(`tokens ${new URL(request.url).searchParams.get('days')}`);
      return HttpResponse.json({
        days: [
          { day: '2026-11-07', model: 'adal-34b-1-0', input_tokens: 1_200_000, output_tokens: 400_000, requests: 300, charged_cents: 0 },
          { day: '2026-11-09', model: 'adal-34b-1-0', input_tokens: 2_000_000, output_tokens: 900_000, requests: 610, charged_cents: 1129.6 },
          sonnetDay,
        ],
      });
    }),
    ...llmHandlers(),
  );
  return asked;
}

describe('Usage over time', () => {
  it('charts tokens, charges, bot runs and connections by day over the last 30 days', async () => {
    watchDays();
    renderApp('/usage');
    const tokens = await screen.findByRole('region', { name: 'Tokens in and out' });
    // The card is there once the series is read; the tokens' days are a read of their own and may come after it.
    await waitFor(() => expect(tokens).toHaveTextContent('4,506,000 tokens'));
    expect(rowsOf('Input and output tokens by day, last 30 days').at(-1)).toBe('9 Nov2,005,000901,000');
    expect(screen.getByRole('region', { name: 'Charged to the balance' })).toHaveTextContent('$11.70');
    expect(rowsOf('Charged to the balance by day, last 30 days').at(-1)).toBe('9 Nov$11.70');
    expect(rowsOf('Bot runs by day, last 30 days').at(-1)).toBe('9 Nov2');
    expect(screen.getByRole('region', { name: 'Connections held' })).toHaveTextContent('4 now');
    expect(rowsOf('Connections held by day, last 30 days').slice(-5)).toEqual(['5 Nov3', '6 Nov3', '7 Nov3', '8 Nov3', '9 Nov4']);
    // Ada Cloud is off here: no requests chart.
    expect(screen.queryByRole('region', { name: 'Ada requests' })).not.toBeInTheDocument();
  });

  it('narrows the tokens and charges to one model, a bot’s among them', async () => {
    watchDays();
    const { user } = renderApp('/usage');
    const picker = await screen.findByRole('combobox', { name: 'Model' });
    expect(within(picker).getAllByRole('option').map((o) => o.textContent)).toEqual(['All models', 'adaL 34B 1.0', 'Claude Sonnet 5.5 (bots)']);
    await user.selectOptions(picker, 'claude-sonnet-5-5');
    // The picker is there with the billing; the series and the tokens' days are reads of their own.
    await waitFor(() => expect(screen.getByRole('region', { name: 'Tokens in and out' })).toHaveTextContent('6,000 tokens'));
    expect(rowsOf('Input and output tokens by day, last 30 days').at(-1)).toBe('9 Nov5,0001,000');
    expect(screen.getByRole('region', { name: 'Charged to the balance' })).toHaveTextContent('$0.40');
  });

  it('asks for the days of the range picked', async () => {
    const asked = watchDays();
    const { user } = renderApp('/usage');
    await screen.findByRole('region', { name: 'Tokens in and out' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Range' }), '7');
    expect(await screen.findByRole('table', { name: 'Bot runs by day, last 7 days' })).toBeInTheDocument();
    expect(rowsOf('Bot runs by day, last 7 days')).toHaveLength(7);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Range' }), 'month');
    const today = new Date().getUTCDate();
    await waitFor(() => expect(asked).toContain(`tokens ${today}`));
    expect(asked).toEqual(expect.arrayContaining(['tokens 30', 'tokens 7']));
  });

  it('charts Ada’s requests and decides on Ada Cloud’s Usage', async () => {
    server.use(...adaFake({ models: [tickets()] }).handlers);
    renderApp('/usage');
    const requests = await screen.findByRole('region', { name: 'Ada requests' });
    // 120 a day more each day, over 30 days: 120 x (1 + ... + 30).
    expect(requests).toHaveTextContent('55,800 requests');
    expect(rowsOf('Ada requests and decides by day, last 30 days').at(-1)).toBe('9 Nov3,6002,400');
    // Hosted models off: no tokens, no model picker.
    expect(screen.queryByRole('combobox', { name: 'Model' })).not.toBeInTheDocument();
  });

  it('shows the refusal when the days cannot be read', async () => {
    server.use(http.get(v1('/billing/series'), () => apiError(503, 'E_UNAVAILABLE', 'Usage is down.')));
    renderApp('/usage');
    expect(await screen.findByText('Usage is down.')).toBeInTheDocument();
  });
});

describe('Usage’s days', () => {
  it('counts this month’s days so far, UTC', () => {
    expect(rangeDays('month', new Date('2026-11-21T23:00:00Z'))).toBe(21);
    expect(rangeDays('7')).toBe(7);
  });

  it('runs to today without a series, and puts a day not on the axis nowhere', () => {
    const days = axisDays(undefined, 3, new Date('2026-11-21T10:00:00Z'));
    expect(days).toEqual(['2026-11-19', '2026-11-20', '2026-11-21']);
    const row = { day: '2026-10-01', model: 'm', input_tokens: 5, output_tokens: 5, requests: 1, charged_cents: 1 };
    expect(tokensOn(days, [row])).toEqual({ input: [0, 0, 0], output: [0, 0, 0], charged: [0, 0, 0] });
  });
});
