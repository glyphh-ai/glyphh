import type { Config } from './config.js';

export type Tokens = {
  accessToken: string;
  refreshToken: string;
  /** Epoch milliseconds after which the access token should be refreshed. */
  expiresAt: number;
};

export class OAuthError extends Error {
  constructor(
    readonly error: string,
    description: string,
  ) {
    super(description);
  }
}

/** A minute's grace, so a token is never sent just as it runs out. */
const refreshMarginMs = 60_000;

export function redirectUri(config: Config): string {
  return `${config.platformUrl}/auth/callback`;
}

export function authorizeUrl(config: Config, state: string, challenge: string): string {
  const query = new URLSearchParams({
    response_type: 'code',
    client_id: config.clientId,
    redirect_uri: redirectUri(config),
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    scope: 'account',
  });
  return `${config.serverUrl}/oauth/authorize?${query}`;
}

function basicAuth(config: Config): string {
  const id = encodeURIComponent(config.clientId);
  const secret = encodeURIComponent(config.clientSecret);
  return `Basic ${Buffer.from(`${id}:${secret}`).toString('base64')}`;
}

async function tokenRequest(config: Config, fetcher: typeof fetch, form: Record<string, string>, now: number): Promise<Tokens> {
  const response = await fetcher(`${config.serverUrl}/oauth/token`, {
    method: 'POST',
    headers: {
      authorization: basicAuth(config),
      'content-type': 'application/x-www-form-urlencoded',
      accept: 'application/json',
    },
    body: new URLSearchParams(form),
  });
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok || typeof data.access_token !== 'string' || typeof data.refresh_token !== 'string') {
    throw new OAuthError(String(data.error ?? 'server_error'), String(data.error_description ?? 'The sign-in could not finish.'));
  }
  const expiresIn = typeof data.expires_in === 'number' ? data.expires_in : 3600;
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: now + expiresIn * 1000 - refreshMarginMs,
  };
}

export function exchangeCode(config: Config, fetcher: typeof fetch, code: string, verifier: string, now = Date.now()): Promise<Tokens> {
  return tokenRequest(
    config,
    fetcher,
    { grant_type: 'authorization_code', code, redirect_uri: redirectUri(config), code_verifier: verifier },
    now,
  );
}

export function refresh(config: Config, fetcher: typeof fetch, refreshToken: string, now = Date.now()): Promise<Tokens> {
  return tokenRequest(config, fetcher, { grant_type: 'refresh_token', refresh_token: refreshToken }, now);
}

/** Ends the grant at the server. Best effort: signing out here never waits on it to succeed. */
export async function revoke(config: Config, fetcher: typeof fetch, refreshToken: string): Promise<void> {
  try {
    await fetcher(`${config.serverUrl}/oauth/revoke`, {
      method: 'POST',
      headers: { authorization: basicAuth(config), 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ token: refreshToken, token_type_hint: 'refresh_token' }),
    });
  } catch {
    // The cookie is cleared regardless; an unreachable server leaves only an unused grant behind.
  }
}
