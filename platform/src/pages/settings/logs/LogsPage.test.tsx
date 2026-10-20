import { screen, within } from '@testing-library/react';
import { auditEvents, logs } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, nothingSentHandlers, server, v1 } from '@/test/server';

/** Records each telemetry read's query, answering as `answer` says. */
function recordReads(path: string, answer: (url: URL) => Record<string, unknown>) {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(v1(path), ({ request }) => {
      const url = new URL(request.url);
      seen.push(url.searchParams);
      return HttpResponse.json(answer(url));
    }),
  );
  return seen;
}

const rows = (name: string) => within(screen.getByRole('list', { name })).getAllByRole('listitem');

describe('Logs', () => {
  it('opens from the settings rail, after Usage', async () => {
    const { user, router } = renderApp('/usage');
    const rail = await screen.findByRole('complementary', { name: 'Main' });
    const links = within(rail).getAllByRole('link').map((link) => link.textContent);
    expect(links.indexOf('Logs')).toBe(links.indexOf('Usage') + 1);
    await user.click(within(rail).getByRole('link', { name: 'Logs' }));
    expect(router.state.location.pathname).toBe('/logs');
    expect(await screen.findByRole('heading', { name: 'Logs', level: 1 })).toBeInTheDocument();
  });

  it('shows the log lines newest first: time in UTC, level, message, where from, and the details kept', async () => {
    const { user } = renderApp('/logs');
    expect(await screen.findByRole('tab', { name: 'Logs' })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByRole('list', { name: 'Log lines' })).toBeInTheDocument();
    const lines = rows('Log lines');
    expect(lines).toHaveLength(4);
    expect(within(lines[0]!).getByText('16 Oct 13:58:12')).toHaveAttribute('datetime', logs[0]!.at);
    expect(within(lines[0]!).getByText('Error')).toBeInTheDocument();
    expect(within(lines[0]!).getByText('Sync to rrotor-2 failed: connection reset')).toBeInTheDocument();
    expect(within(lines[0]!).getByText('Acme production · rrotor-1')).toBeInTheDocument();
    expect(within(lines[1]!).getByText('Warning')).toBeInTheDocument();
    await user.click(within(lines[0]!).getByText('Details'));
    expect(within(lines[0]!).getByText(/"attempt": 3/)).toBeVisible();
    // No attributes, nothing more to show.
    expect(within(lines[3]!).queryByText('Details')).not.toBeInTheDocument();
    expect(screen.getByText(/Newest first, read again every 10 seconds\. Times in UTC\./)).toBeInTheDocument();
  });

  it('reads a line tolerantly: fields it does not know shown in its details, missing ones left out', async () => {
    server.use(
      http.get(v1('/telemetry/logs'), () =>
        HttpResponse.json({ records: [{ at: '2026-10-16T13:00:00Z', runtime_id: 'rt-self-1', body: 'Started', trace_id: 'abc', region: 'eu' }], next_cursor: null }),
      ),
    );
    const { user } = renderApp('/logs');
    const line = (await screen.findByRole('list', { name: 'Log lines' })).querySelector('li')!;
    expect(within(line).getByText('Acme production')).toBeInTheDocument();
    await user.click(within(line).getByText('Details'));
    expect(within(line).getByText(/"trace_id": "abc"/)).toBeInTheDocument();
    expect(within(line).getByText(/"region": "eu"/)).toBeInTheDocument();
  });

  it('filters by runtime, node, level and above and time at once, and by words when searched', async () => {
    const seen = recordReads('/telemetry/logs', () => ({ records: logs, next_cursor: null }));
    const { user } = renderApp('/logs');
    await screen.findByRole('list', { name: 'Log lines' });
    const filters = screen.getByRole('form', { name: 'Filter log lines' });
    await user.selectOptions(await within(filters).findByLabelText('Runtime'), 'rt-self-1');
    await user.selectOptions(within(filters).getByLabelText('Node'), 'rrotor-2');
    await user.selectOptions(within(filters).getByLabelText('Level'), 'error');
    await user.selectOptions(within(filters).getByLabelText('Time'), '1h');
    await user.type(within(filters).getByLabelText('Words'), 'sync');
    expect(seen.at(-1)?.get('text')).toBeNull();
    expect(within(filters).getByRole('option', { name: 'Warning and above' })).toHaveValue('warn');
    await user.click(within(filters).getByRole('button', { name: 'Search' }));
    const last = seen.at(-1)!;
    expect(last.get('runtime')).toBe('rt-self-1');
    expect(last.get('node')).toBe('rrotor-2');
    expect(last.get('level')).toBe('error');
    expect(last.get('text')).toBe('sync');
    expect(Date.now() - new Date(last.get('since')!).getTime()).toBeGreaterThanOrEqual(3_600_000);
    expect(Date.now() - new Date(last.get('since')!).getTime()).toBeLessThan(3_660_000);
    expect(last.get('limit')).toBe('50');
  });

  it('pages back with Load older by the server’s cursor, until there is no more', async () => {
    const seen = recordReads('/telemetry/logs', (url) =>
      url.searchParams.get('cursor') === 'c2' ? { records: logs.slice(2), next_cursor: null } : { records: logs.slice(0, 2), next_cursor: 'c2' },
    );
    const { user } = renderApp('/logs');
    await screen.findByRole('list', { name: 'Log lines' });
    expect(rows('Log lines')).toHaveLength(2);
    await user.click(screen.getByRole('button', { name: 'Load older' }));
    await screen.findByText('Heartbeat sent');
    expect(rows('Log lines')).toHaveLength(4);
    expect(seen.at(-1)?.get('cursor')).toBe('c2');
    expect(screen.queryByRole('button', { name: 'Load older' })).not.toBeInTheDocument();
  });

  it('says nothing matches the filters, and clears them', async () => {
    recordReads('/telemetry/logs', (url) => (url.searchParams.get('level') ? { records: [], next_cursor: null } : { records: logs, next_cursor: null }));
    const { user } = renderApp('/logs');
    await screen.findByRole('list', { name: 'Log lines' });
    await user.selectOptions(screen.getByLabelText('Level'), 'error');
    expect(await screen.findByText('No log lines match')).toBeInTheDocument();
    expect(screen.queryByText(/RROTOR_SERVER_LOGS/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(await screen.findByRole('list', { name: 'Log lines' })).toBeInTheDocument();
    expect(screen.getByLabelText('Level')).toHaveValue('');
  });

  it('shows a refusal', async () => {
    server.use(http.get(v1('/telemetry/logs'), () => apiError(503, 'E_UNAVAILABLE', 'Logs are unavailable.')));
    renderApp('/logs');
    expect(await screen.findByText('Logs are unavailable.')).toBeInTheDocument();
    expect(screen.getByText('Trace trace-123')).toBeInTheDocument();
  });
  it('starts again from the newest when the server refuses a cursor no page gave', async () => {
    let refuse = true;
    server.use(
      http.get(v1('/telemetry/logs'), ({ request }) => {
        if (!new URL(request.url).searchParams.get('cursor')) return HttpResponse.json({ records: logs.slice(0, 2), next_cursor: 'stale' });
        return refuse ? apiError(422, 'E_INVALID', 'This cursor is not one a page gave.', { reason: 'cursor' }) : HttpResponse.json({ records: [], next_cursor: null });
      }),
    );
    const { user } = renderApp('/logs');
    await screen.findByRole('list', { name: 'Log lines' });
    await user.click(screen.getByRole('button', { name: 'Load older' }));
    expect(await screen.findByText('The older pages could not be found. Start again from the newest.')).toBeInTheDocument();
    refuse = false;
    await user.click(screen.getByRole('button', { name: 'Start again' }));
    expect(await screen.findByRole('list', { name: 'Log lines' })).toBeInTheDocument();
    expect(screen.queryByText(/older pages could not be found/)).not.toBeInTheDocument();
    expect(rows('Log lines')).toHaveLength(2);
  });
});

describe('Logs while the runtimes send nothing, rrotor’s default', () => {
  it('says the data stays on rrotor, recommends your own collector, and warns what opting in sends', async () => {
    server.use(...nothingSentHandlers());
    renderApp('/logs');
    const nothing = await screen.findByRole('region', { name: 'No log lines yet' });
    expect(nothing).toHaveTextContent('Your runtimes have sent Glyphh nothing. That is how rrotor works by default: its logs, metrics, traces and audit events stay on your rrotor.');
    expect(nothing).toHaveTextContent('Stream to your own collectorRecommended');
    expect(within(nothing).getByText('OTEL_EXPORTER_OTLP_ENDPOINT')).toBeInTheDocument();
    expect(within(nothing).getByRole('link', { name: 'rrotor’s self-hosting docs' })).toHaveAttribute(
      'href',
      'https://github.com/glyphh-ai/rrotor/tree/main/docs/self-hosting',
    );
    expect(within(nothing).getByText('RROTOR_SERVER_LOGS=on')).toBeInTheDocument();
    expect(within(nothing).getByRole('note')).toHaveTextContent(
      'Your logs, metrics, traces and audit events then leave your rrotor for Glyphh. Inputs, results and client addresses never do.',
    );
  });

  it('says so on Audit and Metrics too', async () => {
    server.use(...nothingSentHandlers());
    const { user } = renderApp('/logs');
    await user.click(await screen.findByRole('tab', { name: 'Audit' }));
    expect(await screen.findByRole('region', { name: 'No audit events yet' })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Metrics' }));
    expect(await screen.findByRole('region', { name: 'No metrics yet' })).toBeInTheDocument();
  });
});

describe('Logs’ Audit tab', () => {
  it('opens from the address, says audit is recorded on Enterprise, and lists who did what and how it ended', async () => {
    const { user } = renderApp('/logs?tab=audit');
    expect(await screen.findByRole('tab', { name: 'Audit' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'Audit' })).toBeInTheDocument();
    const note = screen.getByText(/rrotor records audit events on Enterprise/);
    expect(note).toHaveTextContent('rrotor records audit events on Enterprise. Below Enterprise it sends them as log lines instead: see Logs.');
    expect(within(note).getByRole('link', { name: 'Logs' })).toHaveAttribute('href', '/logs');
    await screen.findByRole('list', { name: 'Audit events' });
    const events = rows('Audit events');
    expect(events).toHaveLength(auditEvents.length);
    expect(within(events[0]!).getByText('run.call')).toBeInTheDocument();
    expect(within(events[0]!).getByText('Done')).toBeInTheDocument();
    expect(within(events[0]!).getByText('By API key 9f86d081 · via rest · Acme production · rrotor-1')).toBeInTheDocument();
    expect(within(events[1]!).getByText('access.denied')).toBeInTheDocument();
    expect(within(events[1]!).getByText('Refused 401')).toBeInTheDocument();
    expect(within(events[1]!).getByText('By No credential · via mcp · Acme production · rrotor-1')).toBeInTheDocument();
    await user.click(within(events[1]!).getByText('Details'));
    expect(within(events[1]!).getByText(/"outcome.code": "E_UNAUTHORIZED"/)).toBeInTheDocument();
    expect(within(events[1]!).queryByText(/actor.type/)).not.toBeInTheDocument();
  });

  it('filters by kind when searched', async () => {
    const seen = recordReads('/telemetry/audit', () => ({ events: auditEvents, next_cursor: null }));
    const { user } = renderApp('/logs?tab=audit');
    await screen.findByRole('list', { name: 'Audit events' });
    await user.type(screen.getByLabelText('Kind'), 'run.call{Enter}');
    expect(seen.at(-1)?.get('kind')).toBe('run.call');
  });

  it('keeps the tab in the address', async () => {
    const { user, router } = renderApp('/logs');
    await user.click(await screen.findByRole('tab', { name: 'Audit' }));
    expect(router.state.location.search).toBe('?tab=audit');
    await user.click(screen.getByRole('tab', { name: 'Logs' }));
    expect(router.state.location.search).toBe('');
  });
});

describe('Logs’ Metrics tab', () => {
  it('gathers each node’s series: runs, run time, precedents of the cap, link, drops and when sent', async () => {
    renderApp('/logs?tab=metrics');
    const table = await screen.findByRole('table', { name: 'Metrics by node' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Node', 'Runs', 'Run time', 'Precedents', 'Link', 'Dropped', 'Sent']);
    const [, first, second] = within(table).getAllByRole('row');
    expect(within(first!).getByRole('rowheader')).toHaveTextContent('rrotor-1Acme production');
    expect(within(first!).getAllByRole('cell').map((td) => td.textContent).slice(0, 5)).toEqual(['1,28484 not done', '1 h 30 min', '12,050 of 50,000', 'Up', '0']);
    expect(within(second!).getAllByRole('cell').map((td) => td.textContent).slice(0, 5)).toEqual(['310', '1 min 30 s', '12,050 of 50,000', 'Reconnecting', '12']);
    expect(screen.queryByRole('list', { name: 'Other series' })).not.toBeInTheDocument();
  });

  it('says what a node did not send, and lists series it has no column for', async () => {
    server.use(
      http.get(v1('/telemetry/metrics'), () =>
        HttpResponse.json({
          metrics: [
            { runtime_id: 'rt-7f3a9c', node_id: null, name: 'rrotor.precedents', kind: 'gauge', value: 10, attributes: { model: 'm' } },
            { runtime_id: 'rt-7f3a9c', node_id: null, name: 'rrotor.precedents.cap', kind: 'gauge', value: 10, attributes: {} },
            { runtime_id: 'rt-7f3a9c', node_id: null, name: 'rrotor.queue.depth', unit: '{item}', kind: 'gauge', value: 4, attributes: { queue: 'runs' } },
          ],
        }),
      ),
    );
    renderApp('/logs?tab=metrics');
    const table = await screen.findByRole('table', { name: 'Metrics by node' });
    const [, row] = within(table).getAllByRole('row');
    expect(within(row!).getByRole('rowheader')).toHaveTextContent('Main');
    expect(within(row!).getAllByRole('cell').map((td) => td.textContent)).toEqual(['Not sent', 'Not sent', '10 of 10 Full', 'Not said', 'Not sent', 'Not sent']);
    const other = screen.getByRole('list', { name: 'Other series' });
    expect(other).toHaveTextContent('rrotor.queue.depth');
    expect(other).toHaveTextContent('Main · queue=runs');
    expect(other).toHaveTextContent('4 {item}');
  });
});
