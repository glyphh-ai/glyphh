import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/App';
import { hostingOff, licenceKeys, machines, nodes, plans, rates } from '@/test/fixtures';
import { hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';
import { hostedRates, hostingOn, readRates, useDeleteMachine, useHosting, useLicenceKeys, useMachine, useRates, useRuntimeNodes } from './queries';

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
