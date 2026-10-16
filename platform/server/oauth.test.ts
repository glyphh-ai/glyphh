import { exchangeCode, OAuthError, refresh, revoke } from './oauth.js';
import { testConfig } from './testing.js';

/** A token endpoint that answers every request with `response`, recording what it was sent. */
function tokenEndpoint(response: () => Response) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fetcher = (async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return response();
  }) as typeof fetch;
  return { calls, fetcher };
}

describe('the token endpoint', () => {
  it('keeps a token for an hour, less a minute, when the server gives no lifetime', async () => {
    const { fetcher } = tokenEndpoint(() => Response.json({ access_token: 'a', refresh_token: 'r' }));
    const tokens = await exchangeCode(testConfig, fetcher, 'code', 'verifier', 1_000);
    expect(tokens).toEqual({ accessToken: 'a', refreshToken: 'r', expiresAt: 1_000 + 3_600_000 - 60_000 });
  });

  it('uses the server’s lifetime when it gives one', async () => {
    const { fetcher } = tokenEndpoint(() => Response.json({ access_token: 'a', refresh_token: 'r', expires_in: 120 }));
    const tokens = await refresh(testConfig, fetcher, 'r0', 0);
    expect(tokens.expiresAt).toBe(60_000);
  });

  it('refuses a reply that is missing a token, even with a 200', async () => {
    const { fetcher } = tokenEndpoint(() => Response.json({ access_token: 'a' }));
    const error = await exchangeCode(testConfig, fetcher, 'code', 'verifier').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(OAuthError);
    expect(error).toMatchObject({ error: 'server_error', message: 'The sign-in could not finish.' });
  });

  it('treats a reply that is not JSON as a server error', async () => {
    const { fetcher } = tokenEndpoint(() => new Response('<html>Bad gateway</html>', { status: 502 }));
    await expect(refresh(testConfig, fetcher, 'r0')).rejects.toMatchObject({ error: 'server_error' });
  });

  it('passes the server’s OAuth error and description on', async () => {
    const { fetcher } = tokenEndpoint(() => Response.json({ error: 'invalid_grant', error_description: 'Bad code.' }, { status: 400 }));
    await expect(exchangeCode(testConfig, fetcher, 'code', 'verifier')).rejects.toMatchObject({ error: 'invalid_grant', message: 'Bad code.' });
  });
});

describe('revoke', () => {
  it('asks the server to end the refresh token’s grant', async () => {
    const { calls, fetcher } = tokenEndpoint(() => new Response(null, { status: 200 }));
    await revoke(testConfig, fetcher, 'refresh-9');
    expect(calls[0]!.url).toBe('https://api.test/oauth/revoke');
    expect(new URLSearchParams(String(calls[0]!.init!.body)).get('token')).toBe('refresh-9');
  });

  it('does not fail when the server cannot be reached', async () => {
    const fetcher = (() => Promise.reject(new TypeError('fetch failed'))) as typeof fetch;
    await expect(revoke(testConfig, fetcher, 'refresh-9')).resolves.toBeUndefined();
  });
});
