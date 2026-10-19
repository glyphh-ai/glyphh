import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/App';
import { auditEvents, hostingOff, licenceKeys, logs, machines, metrics, nodes, plans, rates } from '@/test/fixtures';
import { hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';
import {
  hostedRates,
  hostingOn,
  liveEvery,
  readRates,
  sinceAt,
  telemetryPath,
  useAudit,
  useDeleteMachine,
  useHosting,
  useLicenceKeys,
  useLogs,
  useMachine,
  useMetrics,
  useRates,
  useRuntimeNodes,
} from './queries';

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createQueryClient()}>{children}</QueryClientProvider>;
}

describe('the machine hooks', () => {
  it('reads one machine by its id', async () => {
    server.use(http.get(v1('/runtimes/:id'), ({ params }) => HttpResponse.json(machines.find((m) => m.id === params.id))));
    const { result } = renderHook(() => useMachine('rt-2b8e41'), { wrapper });
    await waitFor(() => expect(result.current.data?.name).toBe('Experiments'));
  });

  it('deletes with the name typed as the confirmation, encoded', async () => {
    let seen = '';
    server.use(
      http.delete(v1('/runtimes/:id'), ({ request }) => {
        seen = new URL(request.url).search;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { result } = renderHook(() => useDeleteMachine(), { wrapper });
    await result.current.mutateAsync({ id: 'rt-2b8e41', confirm: 'My lab & co' });
    expect(seen).toBe('?confirm=My%20lab%20%26%20co');
  });
});

describe('whether Glyphh hosts machines', () => {
  it('reads the rates as off from either answer the server may give', () => {
    expect(hostedRates({ hosting: 'off' })).toBeNull();
    expect(hostedRates({ ...rates, plans: {} })).toBeNull();
    expect(hostedRates(rates)).toBe(rates);
  });

  it('is off from the rates alone, never from the plans’ runtime nodes', () => {
    expect(hostingOn(null)).toBe(false);
    expect(hostingOn(rates)).toBe(true);
    expect(hostingOn(undefined)).toBe(true);
    expect(hostingOff.plans.map((plan) => plan.limits.machines)).toEqual([1, 3, 10, null]);
  });

  it('is on while the rates are read, even with every plan at no runtime nodes', async () => {
    server.use(http.get(v1('/plans'), () => HttpResponse.json(plans.map((plan) => ({ ...plan, limits: { ...plan.limits, machines: 0 } })))));
    const on = renderHook(() => useHosting(), { wrapper });
    await waitFor(() => expect(on.result.current).toBe(true));
  });

  it('reads the server’s hosting_off refusal of the rates as no rates, and passes any other refusal on', async () => {
    server.use(...hostingOffHandlers());
    await expect(readRates()).resolves.toBeNull();
    const { result } = renderHook(() => useRates(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
    server.use(http.get(v1('/rates'), () => HttpResponse.json({ error: { code: 'E_UNAVAILABLE', message: 'Down.' } }, { status: 503 })));
    await expect(readRates()).rejects.toThrow('Down.');
  });

  it('is off when the rates are refused with hosting_off, whatever the plans say', async () => {
    server.use(http.get(v1('/rates'), () => HttpResponse.json({ error: { code: 'E_UNAVAILABLE', message: 'Off.', reason: 'hosting_off' } }, { status: 503 })));
    const { result } = renderHook(() => useHosting(), { wrapper });
    await waitFor(() => expect(result.current).toBe(false));
  });

  it('is undefined until both are read, then the server’s answer', async () => {
    server.use(...hostingOffHandlers());
    const { result } = renderHook(() => useHosting(), { wrapper });
    expect(result.current).toBeUndefined();
    await waitFor(() => expect(result.current).toBe(false));
  });

  it('is on with the hosting fixtures', async () => {
    const { result } = renderHook(() => useHosting(), { wrapper });
    await waitFor(() => expect(result.current).toBe(true));
  });
});

describe('the licence hooks', () => {
  it('reads the org’s licence keys, newest first, and the newest live one', async () => {
    const { result } = renderHook(() => useLicenceKeys(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(licenceKeys));
    expect(result.current.data?.license_key).toBe(result.current.data?.keys[0]?.key);
  });

  it('reads none on Free', async () => {
    server.use(...hostingOffHandlers());
    const { result } = renderHook(() => useLicenceKeys(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual({ license_key: null, keys: [] }));
  });

  it('reads the runtime nodes against the plan’s', async () => {
    const { result } = renderHook(() => useRuntimeNodes(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(nodes));
  });
});

describe('the telemetry hooks', () => {
  const now = new Date('2026-10-16T14:00:00Z');

  it('counts a window back from now; any time is no window', () => {
    expect(sinceAt('1h', now)).toBe('2026-10-16T13:00:00.000Z');
    expect(sinceAt('24h', now)).toBe('2026-10-15T14:00:00.000Z');
    expect(sinceAt('7d', now)).toBe('2026-10-09T14:00:00.000Z');
    expect(sinceAt('', now)).toBeUndefined();
  });

  it('asks with the filters set, trimmed, a page’s worth and the cursor; the empty ones left out', () => {
    expect(telemetryPath('/telemetry/logs', {}, null, now)).toBe('/telemetry/logs?limit=50');
    expect(telemetryPath('/telemetry/logs', { runtime: 'rt-1', node: '', level: 'warn', since: '1h', text: ' sync failed ' }, 'c2', now)).toBe(
      '/telemetry/logs?runtime=rt-1&level=warn&since=2026-10-16T13%3A00%3A00.000Z&text=sync+failed&limit=50&cursor=c2',
    );
    expect(telemetryPath('/telemetry/audit', { kind: 'run.call', since: '' }, null, now)).toBe(
      '/telemetry/audit?kind=run.call&limit=50',
    );
  });

  it('reads log lines a page at a time, older pages by the server’s cursor', async () => {
    const seen: string[] = [];
    server.use(
      http.get(v1('/telemetry/logs'), ({ request }) => {
        const url = new URL(request.url);
        seen.push(url.search);
        return url.searchParams.get('cursor') === 'c2'
          ? HttpResponse.json({ records: logs.slice(2), next_cursor: null })
          : HttpResponse.json({ records: logs.slice(0, 2), next_cursor: 'c2' });
      }),
    );
    const { result } = renderHook(() => useLogs({ level: 'error' }), { wrapper });
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(1));
    expect(result.current.hasNextPage).toBe(true);
    await result.current.fetchNextPage();
    await waitFor(() => expect(result.current.data?.pages.flatMap((page) => page.records)).toEqual(logs));
    expect(result.current.hasNextPage).toBe(false);
    expect(seen).toEqual(['?level=error&limit=50', '?level=error&limit=50&cursor=c2']);
  });

  it('reads audit events and metrics, keeping fields it does not know', async () => {
    server.use(
      http.get(v1('/telemetry/audit'), () => HttpResponse.json({ events: [{ ...auditEvents[0], region: 'eu' }], next_cursor: null, total: 1 })),
    );
    const audit = renderHook(() => useAudit({}), { wrapper });
    await waitFor(() => expect(audit.result.current.data?.pages[0]?.events?.[0]?.region).toBe('eu'));
    expect(audit.result.current.data?.pages[0]?.total).toBe(1);
    expect(audit.result.current.hasNextPage).toBe(false);
    const read = renderHook(() => useMetrics(), { wrapper });
    await waitFor(() => expect(read.result.current.data?.metrics).toEqual(metrics));
    let asked = '';
    server.use(
      http.get(v1('/telemetry/metrics'), ({ request }) => {
        asked = new URL(request.url).search;
        return HttpResponse.json({ metrics: [] });
      }),
    );
    const one = renderHook(() => useMetrics({ runtime: 'rt-self-1', node: '' }), { wrapper });
    await waitFor(() => expect(one.result.current.isSuccess).toBe(true));
    expect(asked).toBe('?runtime=rt-self-1');
  });

  it('reads again every 10 seconds while in use', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      let reads = 0;
      server.use(
        http.get(v1('/telemetry/logs'), () => {
          reads += 1;
          return HttpResponse.json({ records: logs, next_cursor: null });
        }),
      );
      const { result, unmount } = renderHook(() => useLogs({}), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(liveEvery).toBe(10_000);
      expect(reads).toBe(1);
      await vi.advanceTimersByTimeAsync(liveEvery);
      await waitFor(() => expect(reads).toBe(2));
      unmount();
      await vi.advanceTimersByTimeAsync(liveEvery * 2);
      expect(reads).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
