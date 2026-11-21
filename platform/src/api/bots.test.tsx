import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { botsFake, waiting } from '@/test/bots';
import { apiError, http, server } from '@/test/server';
import { ApiError } from './client';
import { connectionsOff, problemsOf, useBotRun, useBots, useConnectionTools } from './bots';

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

  it('asks for a run again while it is queued or running, and stops once it waits on the person', async () => {
    const fake = botsFake({ runs: [waiting({ id: 'r-x', status: 'queued', question: null })] });
    server.use(...fake.handlers);
    const run = renderHook(() => useBotRun('r-x', 20), { wrapper: wrapper() });
    await waitFor(() => expect(run.result.current.data?.status).toBe('needs_input'));
    expect(run.result.current.data?.question?.batch).toHaveLength(2);
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

  it('reads the SDK’s problems off a refused bot, and none off anything else', () => {
    const refused = new ApiError(422, { code: 'E_INVALID', message: 'Not valid.', trace_id: 't', problems: ['loop[0]: no step', 'gates.x: unknown'] } as never);
    expect(problemsOf(refused)).toEqual(['loop[0]: no step', 'gates.x: unknown']);
    expect(problemsOf(new Error('no'))).toEqual([]);
  });
});
