import { screen } from '@testing-library/react';
import { ApiError } from '@/api/client';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, server, v1 } from '@/test/server';
import { createQueryClient } from './App';

describe('when the platform’s sign-in ends mid-visit', () => {
  it('a read sends the person to log in, and back to this page after', async () => {
    const location = stubLocation();
    server.use(http.get(v1('/me'), () => apiError(401, 'E_SIGNED_OUT', 'You are signed out. Log in again.')));
    try {
      renderApp('/');
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith(`/login?returnTo=${encodeURIComponent(window.location.pathname)}`));
    } finally {
      location.restore();
    }
  });

  it('any other refusal stays on the page', async () => {
    const location = stubLocation();
    server.use(http.get(v1('/me'), () => apiError(403, 'E_FORBIDDEN', 'Not yours.')));
    try {
      renderApp('/');
      expect(await screen.findByRole('heading', { name: 'This is Glyphh’s staff console.' })).toBeInTheDocument();
      expect(location.assign).not.toHaveBeenCalled();
    } finally {
      location.restore();
    }
  });
});

describe('reads that fail', () => {
  const retry = createQueryClient().getDefaultOptions().queries!.retry as (count: number, error: unknown) => boolean;

  it('are asked again twice when the connection was lost', () => {
    expect(retry(0, new TypeError('Failed to fetch'))).toBe(true);
    expect(retry(1, new TypeError('Failed to fetch'))).toBe(true);
    expect(retry(2, new TypeError('Failed to fetch'))).toBe(false);
  });

  it('are never asked again when the server refused', () => {
    expect(retry(0, new ApiError(503, { code: 'E_UNAVAILABLE', message: 'Off.' }))).toBe(false);
  });
});
