import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ApiError, signedOutCode } from '@/api/client';
import { ThemeProvider } from '@/theme/ThemeProvider';
import { ToastProvider } from '@/ui';

/** When the platform's sign-in ends mid-visit, the next read sends the person to log in, back here after. */
function onSignedOut(error: unknown) {
  if (error instanceof ApiError && error.code === signedOutCode) {
    window.location.assign(`/login?returnTo=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }
}

export function createQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({ onError: onSignedOut }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: true,
        // A refusal is the server's answer; only a lost connection is worth asking again.
        retry: (count, error) => !(error instanceof ApiError) && count < 2,
      },
      mutations: { onError: onSignedOut },
    },
  });
}

export function Providers({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>{children}</ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
