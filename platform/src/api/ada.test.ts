import { http, HttpResponse, server } from '@/test/server';
import { adaRefusal } from './ada';
import { adaApi, ApiError } from './client';

describe('Ada’s plan refusals', () => {
  it('reads a 429 E_RATE with its Retry-After header', async () => {
    server.use(
      http.post('*/api/ada/v1/decide', () =>
        HttpResponse.json({ error: { code: 'E_RATE', message: 'Your plan allows 5 Ada calls a second: try again in 3 seconds.', trace_id: 't', retry_after: 3 } }, { status: 429, headers: { 'retry-after': '3' } }),
      ),
    );
    const error = await adaApi.post('/decide', {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).retryAfter).toBe(3);
    expect(adaRefusal(error)).toEqual({ kind: 'rate', retryAfter: 3 });
  });

  it('falls back to retry_after in the body without the header', () => {
    expect(adaRefusal(new ApiError(429, { code: 'E_RATE', message: 'Slow down.', retry_after: 2 }))).toEqual({ kind: 'rate', retryAfter: 2 });
  });

  it('reads a 403 E_LIMIT for the month’s requests: the plan, its upgrade and when they start again', () => {
    const error = new ApiError(403, { code: 'E_LIMIT', message: 'Used.', reason: 'requests', used: 5_000, max: 5_000, plan: 'Free', upgrade: 'Basic', resets_at: '2026-11-01' });
    expect(adaRefusal(error)).toEqual({ kind: 'requests', plan: 'Free', upgrade: 'Basic', resetsAt: '2026-11-01' });
  });

  it('reads a failed job’s E_LIMIT for precedents', () => {
    expect(adaRefusal({ code: 'E_LIMIT', message: 'Too many.', reason: 'precedents', used: 900, max: 1_000, adding: 200 })).toEqual({ kind: 'precedents', used: 900, max: 1_000 });
  });

  it('is none for any other refusal, or an E_LIMIT that is not Ada’s', () => {
    expect(adaRefusal(new ApiError(404, { code: 'E_MODEL_MISSING', message: 'No model.' }))).toBeNull();
    expect(adaRefusal(new ApiError(413, { code: 'E_LIMIT', message: 'At most 1,000 cases.', reason: 'cases' }))).toBeNull();
    expect(adaRefusal(new Error('offline'))).toBeNull();
    expect(adaRefusal(null)).toBeNull();
  });
});
