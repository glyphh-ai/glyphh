import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/App';
import { licenceKeys, nodes } from '@/test/fixtures';
import { http, HttpResponse, onFreeHandlers, server, v1 } from '@/test/server';
import { keys, useCreateRuntimeKey, useDeleteSelfRuntime, useLicenceKeys, useRegisterSelfRuntime, useRuntimeNodes } from './queries';

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createQueryClient()}>{children}</QueryClientProvider>;
}

describe('the hooks', () => {
  it('read nothing Glyphh no longer serves: no hosted runtimes, rates, machines or telemetry', () => {
    expect(Object.values(keys).map((key) => key[0])).not.toEqual(expect.arrayContaining(['machines', 'rates', 'telemetry']));
    expect(keys).not.toHaveProperty('runtime');
  });
});

describe('the licence hooks', () => {
  it('reads the org’s licence keys, newest first, and the newest live one', async () => {
    const { result } = renderHook(() => useLicenceKeys(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(licenceKeys));
    expect(result.current.data?.license_key).toBe(result.current.data?.keys[0]?.key);
  });

  it('reads none on Free', async () => {
    server.use(...onFreeHandlers());
    const { result } = renderHook(() => useLicenceKeys(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual({ license_key: null, keys: [] }));
  });

  it('reads the runtime nodes against the plan’s', async () => {
    const { result } = renderHook(() => useRuntimeNodes(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(nodes));
  });
});

describe('the self-hosted runtime hooks', () => {
  it('reads the nodes again when a runtime is registered or deleted', async () => {
    let reads = 0;
    server.use(
      http.get(v1('/license/nodes'), () => {
        reads += 1;
        return HttpResponse.json(nodes);
      }),
      http.post(v1('/runtimes/self'), () => HttpResponse.json({ id: 'rt-new', name: 'New', public_url: 'https://rrotor.new.com', token: 't', env: {} }, { status: 201 })),
      http.delete(v1('/runtimes/self/:id'), () => new HttpResponse(null, { status: 204 })),
    );
    const { result } = renderHook(() => ({ nodes: useRuntimeNodes(), register: useRegisterSelfRuntime(), remove: useDeleteSelfRuntime() }), { wrapper });
    await waitFor(() => expect(reads).toBe(1));
    await result.current.register.mutateAsync({ name: 'New', public_url: 'https://rrotor.new.com' });
    await waitFor(() => expect(reads).toBe(2));
    await result.current.remove.mutateAsync('rt-new');
    await waitFor(() => expect(reads).toBe(3));
  });
});

describe('the runtime key hooks', () => {
  it('makes a key for one self-hosted runtime, with no expiry when it never expires', async () => {
    const sent: unknown[] = [];
    server.use(
      http.post(v1('/runtime/keys'), async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json({ id: 'k-9', runtime_id: 'rt-self-1', name: 'App', key: 'glyphh_rk_x' }, { status: 201 });
      }),
    );
    const { result } = renderHook(() => useCreateRuntimeKey(), { wrapper });
    await result.current.mutateAsync({ name: 'App', runtime_id: 'rt-self-1', expires_in_days: 30 });
    await result.current.mutateAsync({ name: 'App', runtime_id: 'rt-self-1', expires_in_days: null });
    expect(sent).toEqual([
      { name: 'App', runtime_id: 'rt-self-1', expires_in_days: 30 },
      { name: 'App', runtime_id: 'rt-self-1' },
    ]);
  });
});
