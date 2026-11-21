import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { botsFake } from '@/test/bots';
import { apiError, http, server } from '@/test/server';
import { ApiError } from './client';
import { connectionsOff, useBotRun, useBots, useConnectionTools } from './bots';

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('the bots API', () => {
  it('reads the bots and a connection’s tools', async () => {
    server.use(...botsFake().handlers);
    const bots = renderHook(() => useBots(), { wrapper: wrapper() });
    await waitFor(() => expect(bots.result.current.data?.map((b) => b.slug)).toEqual(['inbox-helper']));
    const tools = renderHook(() => useConnectionTools('c-gmail'), { wrapper: wrapper() });
    await waitFor(() => expect(tools.result.current.data).toHaveLength(3));
  });

  it('asks for a run again while it is queued or running, and stops once it is done', async () => {
    const fake = botsFake();
    server.use(...fake.handlers);
    fake.state.runs.push({
      id: 'r-x', bot_slug: 'inbox-helper', status: 'queued', input: 'Go.', output: null, error: null, steps: [],
      input_tokens: 0, output_tokens: 0, cost_micros: 0, created_at: '2026-11-20T09:00:00Z', started_at: null, finished_at: null,
    });
    const run = renderHook(() => useBotRun('r-x', 20), { wrapper: wrapper() });
    await waitFor(() => expect(run.result.current.data?.status).toBe('done'));
    const reads = fake.state.reads.get('r-x');
    await new Promise((r) => setTimeout(r, 100));
    expect(fake.state.reads.get('r-x')).toBe(reads);
  });

  it('asks nothing for no run', () => {
    const run = renderHook(() => useBotRun(null), { wrapper: wrapper() });
    expect(run.result.current.fetchStatus).toBe('idle');
  });

  it('knows a server with no Pipedream project from any other refusal', async () => {
    server.use(http.get('*/api/v1/bots', () => apiError(503, 'E_UNAVAILABLE', 'Off.', { reason: 'pipedream_off' })));
    const bots = renderHook(() => useBots(), { wrapper: wrapper() });
    await waitFor(() => expect(bots.result.current.error).toBeInstanceOf(ApiError));
    expect(connectionsOff(bots.result.current.error)).toBe(true);
    expect(connectionsOff(new Error('no'))).toBe(false);
  });
});
