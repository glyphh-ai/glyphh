import { useQuery } from '@tanstack/react-query';
import { readResponse } from './client';
import type { Consent, Providers } from './types';

export type Session = {
  signedIn: boolean;
  /** The server's public address, for the sign-in links a browser follows there. */
  serverUrl: string;
  /** Ada Cloud's address, which apps call with an API key. */
  adaUrl?: string;
  /** The name the platform signs in under, so its own consent screens can be recognised. */
  clientName: string;
};

/** The platform's own session: signed in or not. Never a token. */
export const useSession = () =>
  useQuery({
    queryKey: ['session'],
    queryFn: async () => readResponse<Session>(await fetch('/auth/session', { credentials: 'same-origin' })),
    staleTime: Infinity,
  });

/** Sign-in providers the server has set up, in its order, and whether single sign-on is offered too. */
export const useProviders = () =>
  useQuery({
    queryKey: ['providers'],
    queryFn: async () => {
      const found = await readResponse<Providers>(await fetch('/auth/providers'));
      return { providers: found.providers, sso: found.sso === true };
    },
    staleTime: Infinity,
  });

/** Where a provider's sign-in starts on the server for a step (`code=`, `oauth=`); single sign-on carries the email. */
export function startUrl(serverUrl: string, provider: string, step: string, email?: string): string {
  const mail = email ? `&email=${encodeURIComponent(email)}` : '';
  return `${serverUrl}/auth/${provider}/start?${step}${mail}`;
}

/**
 * What a sign-in or a client is asking for. The server ties a consent to the browser that started it
 * with its own cookie, so this one call goes from the browser straight to the server.
 */
export const useConsent = (serverUrl: string | undefined, consent: string) =>
  useQuery({
    queryKey: ['consent', consent],
    enabled: Boolean(serverUrl),
    retry: false,
    queryFn: async () =>
      readResponse<Consent>(await fetch(`${serverUrl}/auth/consent?consent=${encodeURIComponent(consent)}`, { credentials: 'include' })),
  });

/** Where the platform's own sign-in starts, coming back to `returnTo` afterwards. */
export function loginUrl(returnTo: string): string {
  return `/auth/login?returnTo=${encodeURIComponent(returnTo)}`;
}
