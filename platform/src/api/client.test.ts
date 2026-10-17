import { api, ApiError, readResponse } from './client';
import { http, HttpResponse, server } from '@/test/server';

describe('the API client', () => {
  it('calls /api/v1 on this platform with JSON', async () => {
    let seen: { method: string; type: string | null; body: unknown } | undefined;
    server.use(
      http.patch('*/api/v1/me', async ({ request }) => {
        seen = { method: request.method, type: request.headers.get('content-type'), body: await request.json() };
        return HttpResponse.json({ ok: true });
      }),
    );
    expect(await api.patch('/me', { name: 'A' })).toEqual({ ok: true });
    expect(seen).toEqual({ method: 'PATCH', type: 'application/json', body: { name: 'A' } });
  });

  it('reads a 204 as nothing', async () => {
    server.use(http.delete('*/api/v1/installs/i1', () => new HttpResponse(null, { status: 204 })));
    expect(await api.delete('/installs/i1')).toBeUndefined();
  });

  it('turns the server’s refusal into an ApiError with its code, trace id and detail', async () => {
    server.use(
      http.post('*/api/v1/org/invites', () =>
        HttpResponse.json({ error: { code: 'E_LIMIT', message: 'Pro allows 1 member.', trace_id: 't1', limit: 'members' } }, { status: 403 }),
      ),
    );
    const error = await api.post('/org/invites', { email: 'a@b.c' }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, code: 'E_LIMIT', message: 'Pro allows 1 member.', traceId: 't1' });
    expect((error as ApiError).detail.limit).toBe('members');
  });

  it('gives a plain message when a failure has no body', async () => {
    const error = await readResponse(new Response('', { status: 502 })).catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 502, code: 'E_HTTP', message: 'Something went wrong. Try again.' });
  });
});
