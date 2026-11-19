import { render, screen, within } from '@testing-library/react';
import { RouterProvider } from 'react-router';
import { createQueryClient, Providers } from '@/App';
import { staffHandlers } from '@/test/admin';
import { server } from '@/test/server';
import { createRouter, routes } from './router';

describe('the browser router', () => {
  afterEach(() => window.history.replaceState(null, '', '/'));

  it('opens the page at the browser’s address: the games, at the root, in the console’s shell', async () => {
    server.use(...staffHandlers());
    window.history.replaceState(null, '', '/');
    const router = createRouter();
    render(
      <Providers client={createQueryClient()}>
        <RouterProvider router={router} />
      </Providers>,
    );
    expect(await screen.findByRole('heading', { name: 'Games', level: 1 })).toBeInTheDocument();
    const rail = screen.getByRole('complementary', { name: 'Main' });
    expect(within(rail).getByRole('link', { name: 'All games' })).toHaveAttribute('href', '/');
    router.dispose();
  });

  it('has the console at the root, the old /admin addresses, and the sign-in', () => {
    expect(routes.map((route) => route.path ?? '/')).toEqual(['/', 'admin/*', 'login', 'authorize', 'allow', 'error', '*']);
    expect(routes[0]!.children!.map((route) => route.path ?? '/')).toEqual(['/', 'games/:id', 'traffic', 'events', 'audit']);
  });
});
