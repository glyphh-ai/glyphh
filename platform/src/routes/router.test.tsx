import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router';
import { createQueryClient, Providers } from '@/App';
import { createRouter } from './router';

describe('the browser router', () => {
  afterEach(() => window.history.replaceState(null, '', '/'));

  it('opens the page at the browser’s address, moving an old path to its place under Settings with its query', async () => {
    window.history.replaceState(null, '', '/account?from=mail');
    const router = createRouter();
    render(
      <Providers client={createQueryClient()}>
        <RouterProvider router={router} />
      </Providers>,
    );
    expect(await screen.findByRole('heading', { name: 'Profile' })).toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe('/settings/profile?from=mail');
    router.dispose();
  });
});
