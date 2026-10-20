import { screen, within } from '@testing-library/react';
import { renderApp } from '@/test/render';
import { hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

const shell = () => screen.getByRole('complementary', { name: 'Main' }).parentElement!;

describe('the sidebar on a phone', () => {
  it('opens from the Menu button and closes from the scrim', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Menu' }));
    expect(shell()).toHaveAttribute('data-sidebar', 'open');
    await user.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(shell()).toHaveAttribute('data-sidebar', 'closed');
    expect(screen.queryByRole('button', { name: 'Close menu' })).not.toBeInTheDocument();
  });

  it('closes when the Menu button is pressed again', async () => {
    const { user } = renderApp('/');
    const menu = await screen.findByRole('button', { name: 'Menu' });
    await user.click(menu);
    await user.click(menu);
    expect(shell()).toHaveAttribute('data-sidebar', 'closed');
  });

  it('closes on moving to another page', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Menu' }));
    await user.click(screen.getByRole('link', { name: 'API Keys' }));
    expect(await screen.findByRole('heading', { name: 'API Keys' })).toBeInTheDocument();
    expect(shell()).toHaveAttribute('data-sidebar', 'closed');
  });
});

describe('the main sidebar', () => {
  it('has the logo, the runtime and Ada, and no organisation group: settings is in the account menu', async () => {
    renderApp('/');
    const main = await screen.findByRole('complementary', { name: 'Main' });
    expect(within(main).getByRole('img', { name: 'Glyphh' })).toBeInTheDocument();
    for (const name of ['Runtimes', 'API Keys', 'Models']) expect(within(main).getByRole('link', { name })).toBeInTheDocument();
    expect(within(main).queryByRole('group', { name: 'Organisation' })).not.toBeInTheDocument();
    for (const name of ['Billing', 'Members', 'Settings']) expect(within(main).queryByRole('link', { name })).not.toBeInTheDocument();
  });
});

describe('the main sidebar while Glyphh hosts nothing', () => {
  it.each(['refused', 'off', 'empty'] as const)('has no Machines when the rates answer %s', async (rates) => {
    server.use(...hostingOffHandlers(rates), http.get(v1('/runtimes/self'), () => HttpResponse.json([])));
    renderApp('/');
    const main = await screen.findByRole('complementary', { name: 'Main' });
    // Home's empty state for running rrotor yourself shows once the plans and rates are read.
    await screen.findByRole('button', { name: 'Run rrotor yourself' });
    expect(within(main).queryByRole('link', { name: 'Machines' })).not.toBeInTheDocument();
    expect(within(main).getAllByRole('link').map((link) => link.textContent)).toEqual(['Getting started', 'Runtimes', 'API Keys', 'Usage', 'Logs', 'Licence', 'Models']);
  });
});
