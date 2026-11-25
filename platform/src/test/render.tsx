import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { createQueryClient, Providers } from '@/App';
import { routes } from '@/routes/router';

/** Renders the whole app at `path`, against the fake server, as a person would see it. */
export function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const client = createQueryClient();
  const defaults = client.getDefaultOptions();
  client.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, retry: false } });
  const user = userEvent.setup();
  const view = render(
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>,
  );
  return { ...view, router, user, client };
}

/** Pages move the browser for full-page steps; tests read where it would have gone. */
export function stubLocation() {
  const assign = vi.fn();
  const replace = vi.fn();
  const original = window.location;
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...original, assign, replace, pathname: original.pathname, search: original.search, href: original.href },
  });
  return {
    assign,
    replace,
    restore: () => Object.defineProperty(window, 'location', { configurable: true, value: original }),
  };
}
