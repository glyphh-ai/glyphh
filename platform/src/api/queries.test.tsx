import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/App';
import { hostingOff, machines, plans, rates } from '@/test/fixtures';
import { hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';
import { hostedRates, hostingOn, useDeleteMachine, useHosting, useMachine } from './queries';

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

  it('is off when the rates are off or no plan has a hosted machine, and on otherwise', () => {
    expect(hostingOn(plans, null)).toBe(false);
    expect(hostingOn(hostingOff.plans, rates)).toBe(false);
    expect(hostingOn(plans, rates)).toBe(true);
    expect(hostingOn(plans, undefined)).toBe(true);
    expect(hostingOn(undefined, undefined)).toBe(true);
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
