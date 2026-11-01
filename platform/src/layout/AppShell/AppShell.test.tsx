import { screen, within } from '@testing-library/react';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server, v1 } from '@/test/server';

// The stylesheets as written: the tests run in Node, and the UI's tsconfig carries no Node types, hence the narrow one.
type Fs = { readFileSync(path: string, encoding: 'utf8'): string };
const fs = (globalThis as unknown as { process: { getBuiltinModule(id: 'node:fs'): Fs } }).process.getBuiltinModule('node:fs');
const stylesheet = (path: string) => fs.readFileSync(`src/${path}`, 'utf8');
const shellCss = stylesheet('layout/AppShell/AppShell.module.css');
const sidebarCss = stylesheet('layout/Sidebar/Sidebar.module.css');
const menuCss = stylesheet('ui/Menu/Menu.module.css');

const shell = () => screen.getByRole('complementary', { name: 'Main' }).parentElement!;

describe('the sidebar on a phone', () => {
  it('opens from the Menu button and closes from the scrim', async () => {
    const { user } = renderApp('/runtimes');
    await screen.findByRole('heading', { name: 'Runtimes', level: 1 });
    await user.click(await screen.findByRole('button', { name: 'Menu' }));
    expect(shell()).toHaveAttribute('data-sidebar', 'open');
    await user.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(shell()).toHaveAttribute('data-sidebar', 'closed');
    expect(screen.queryByRole('button', { name: 'Close menu' })).not.toBeInTheDocument();
  });

  it('closes when the Menu button is pressed again', async () => {
    const { user } = renderApp('/runtimes');
    await screen.findByRole('heading', { name: 'Runtimes', level: 1 });
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

/** The declarations of the first rule for `selector` in `css` from `from` (jsdom lays nothing out, so the rules are read). */
const rule = (css: string, selector: string, from = 0) => {
  const start = css.indexOf(`${selector} {`, from);
  expect(start, `${selector} in the stylesheet`).toBeGreaterThanOrEqual(0);
  return css.slice(start, css.indexOf('}', start)).replace(/\s+/g, ' ');
};

describe('the account menu on a phone', () => {
  it('is in the rail in both sidebars, the main one and settings', async () => {
    for (const path of ['/', '/settings/general']) {
      const { unmount } = renderApp(path);
      const rail = await screen.findByRole('complementary', { name: 'Main' });
      expect(await within(rail).findByRole('button', { name: /Chris Timmerman/ })).toBeInTheDocument();
      unmount();
    }
  });

  // On a phone 100vh is the viewport with the browser's toolbar hidden: with it out, a 100vh rail's foot, the account
  // menu, sat behind the toolbar and no one could reach settings, billing or log out.
  it('sits in a rail as tall as the visible viewport, not 100vh', () => {
    expect(rule(shellCss, '.sidebar')).toMatch(/height: 100vh; height: 100dvh;/);
    expect(rule(shellCss, '.sidebar', shellCss.indexOf('@media (max-width: 860px)'))).toMatch(/position: fixed;.*top: 0;/);
  });

  it('stays pinned while the nav scrolls, clear of the home indicator', () => {
    expect(rule(sidebarCss, '.nav')).toMatch(/flex: 1;.*min-height: 0;.*overflow-y: auto;/);
    expect(rule(sidebarCss, '.footer')).toMatch(/flex: none;/);
    expect(rule(sidebarCss, '.sidebar')).toMatch(/padding-bottom: max\(var\(--space-4\), env\(safe-area-inset-bottom\)\)/);
  });

  it('opens its Theme submenu over the menu, not off the side of the screen', () => {
    expect(rule(menuCss, '.subPanel', menuCss.indexOf('@media (max-width: 520px)'))).toMatch(/left: 0;/);
  });
});

describe('the main sidebar', () => {
  it('has the logo, Runtimes & licences and Ada, and no organisation group: settings is in the account menu', async () => {
    renderApp('/');
    const main = await screen.findByRole('complementary', { name: 'Main' });
    // The links come once the account says Ada Cloud is off.
    await within(main).findByRole('link', { name: 'Runtimes' });
    expect(within(main).getByRole('img', { name: 'Glyphh' })).toBeInTheDocument();
    for (const name of ['Runtimes', 'Licence', 'API Keys', 'Models']) expect(within(main).getByRole('link', { name })).toBeInTheDocument();
    expect(within(main).queryByRole('group', { name: 'Organisation' })).not.toBeInTheDocument();
    for (const name of ['Billing', 'Members', 'Settings']) expect(within(main).queryByRole('link', { name })).not.toBeInTheDocument();
  });

  it('has nothing Glyphh hosted: no Machines and no Logs', async () => {
    server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([])));
    renderApp('/');
    const main = await screen.findByRole('complementary', { name: 'Main' });
    await screen.findByRole('heading', { name: 'Runtimes', level: 1 });
    expect(within(main).getAllByRole('link').map((link) => link.textContent)).toEqual(['Runtimes', 'Licence', 'API Keys', 'Usage', 'Models']);
  });
});
