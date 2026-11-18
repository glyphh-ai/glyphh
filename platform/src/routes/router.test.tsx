import { render, screen, within } from '@testing-library/react';
import { RouterProvider } from 'react-router';
import { createQueryClient, Providers } from '@/App';
import { createRouter, routes } from './router';

describe('the browser router', () => {
  afterEach(() => window.history.replaceState(null, '', '/'));

  it('opens the page at the browser’s address: Home, empty, in the console’s shell', async () => {
    window.history.replaceState(null, '', '/');
    const router = createRouter();
    render(
      <Providers client={createQueryClient()}>
        <RouterProvider router={router} />
      </Providers>,
    );
    expect(await screen.findByRole('heading', { name: 'Home' })).toBeInTheDocument();
    expect(screen.getByText('Nothing here yet.')).toBeInTheDocument();
    const rail = screen.getByRole('complementary', { name: 'Main' });
    expect(within(rail).getAllByRole('link').map((link) => link.textContent)).toEqual(['Home']);
    router.dispose();
  });

  it('has only the sign-in, Home and the staff view left since the products were retired', () => {
    expect(routes.map((route) => route.path ?? '/')).toEqual(['/', 'admin', 'login', 'authorize', 'allow', 'error', '*']);
    expect(routes[0]!.children).toHaveLength(1); // Home, alone
  });
});
