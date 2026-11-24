import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/App';
import { billing, org } from '@/test/fixtures';
import { http, HttpResponse, server, v1 } from '@/test/server';
import { keys, useBilling, useChangePlan } from './queries';

function wrapper({ children }: { children: ReactNode }) {
  const client = createQueryClient();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('the hooks', () => {
  it('read nothing Glyphh no longer serves: no runtimes, licence keys, nodes or apps', () => {
    const first = Object.values(keys).map((key) => key[0]);
    expect(first).not.toEqual(expect.arrayContaining(['runtime', 'runtimes', 'license', 'apps', 'machines']));
    expect(keys).not.toHaveProperty('runtimeKeys');
    expect(keys).not.toHaveProperty('licenceKeys');
  });

  it('reads billing again when the plan changes', async () => {
    let reads = 0;
    server.use(
      http.get(v1('/billing'), () => {
        reads += 1;
        return HttpResponse.json(billing);
      }),
      http.post(v1('/billing/plan'), () => HttpResponse.json(org)),
    );
    const { result } = renderHook(() => ({ billing: useBilling(), change: useChangePlan() }), { wrapper });
    await waitFor(() => expect(reads).toBe(1));
    await result.current.change.mutateAsync('Team');
    await waitFor(() => expect(reads).toBe(2));
  });
});
