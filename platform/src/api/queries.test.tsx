import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/App';
import { machines } from '@/test/fixtures';
import { http, HttpResponse, server, v1 } from '@/test/server';
import { useDeleteMachine, useMachine } from './queries';

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
