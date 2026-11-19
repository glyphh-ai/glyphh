import { screen, within } from '@testing-library/react';
import { renderApp } from '@/test/render';
import { staffHandlers } from '@/test/admin';
import { server } from '@/test/server';

// The stylesheets as written: the tests run in Node, and the UI's tsconfig carries no Node types, hence the narrow one.
type Fs = { readFileSync(path: string, encoding: 'utf8'): string; existsSync(path: string): boolean };
const fs = (globalThis as unknown as { process: { getBuiltinModule(id: 'node:fs'): Fs } }).process.getBuiltinModule('node:fs');
const stylesheet = (path: string) => fs.readFileSync(`src/${path}`, 'utf8');
const shellCss = stylesheet('layout/AppShell/AppShell.module.css');
const sidebarCss = stylesheet('layout/Sidebar/Sidebar.module.css');
const menuCss = stylesheet('ui/Menu/Menu.module.css');

const shell = () => screen.getByRole('complementary', { name: 'Main' }).parentElement!;

// The console is staff only: every test here signs in as staff.
beforeEach(() => server.use(...staffHandlers()));

describe('the sidebar on a phone', () => {
  it('opens from the Menu button and closes from the scrim', async () => {
    const { user } = renderApp('/');
    await screen.findByRole('heading', { name: 'Games', level: 1 });
    await user.click(await screen.findByRole('button', { name: 'Menu' }));
    expect(shell()).toHaveAttribute('data-sidebar', 'open');
    await user.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(shell()).toHaveAttribute('data-sidebar', 'closed');
    expect(screen.queryByRole('button', { name: 'Close menu' })).not.toBeInTheDocument();
  });

  it('closes when the Menu button is pressed again', async () => {
    const { user } = renderApp('/');
    await screen.findByRole('heading', { name: 'Games', level: 1 });
    const menu = await screen.findByRole('button', { name: 'Menu' });
    await user.click(menu);
    await user.click(menu);
    expect(shell()).toHaveAttribute('data-sidebar', 'closed');
  });

  it('closes on moving to another page', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Menu' }));
    await user.click(screen.getByRole('link', { name: 'Audit log' }));
    expect(await screen.findByRole('heading', { name: 'Audit log' })).toBeInTheDocument();
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
  it('is in the rail', async () => {
    renderApp('/');
    const rail = await screen.findByRole('complementary', { name: 'Main' });
    expect(await within(rail).findByRole('button', { name: /Chris Timmerman/ })).toBeInTheDocument();
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
  it('has the logo, the games and Glyphh’s own pages, all at the root', async () => {
    renderApp('/');
    const main = await screen.findByRole('complementary', { name: 'Main' });
    await screen.findByRole('heading', { name: 'Games', level: 1 });
    expect(within(main).getByRole('img', { name: 'Glyphh' })).toBeInTheDocument();
    const links = within(main).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(['All games', 'Free Fall Frank', 'Crabby Knife Fight', 'Bams & Brags', 'Send a Carol', 'Traffic', 'Log alerts', 'Audit log']);
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/', '/games/frank', '/games/crabby', '/games/mahj', '/games/carol', '/traffic', '/events', '/audit']);
  });

  it('crumbs a game’s page back to the games', async () => {
    renderApp('/games/frank');
    expect(await screen.findByRole('link', { name: 'Games' })).toHaveAttribute('href', '/');
  });

  // The file glyphh.ai's header shows, at its 38px: the cat and the name in black with a white outline.
  it('shows the logo file at 38px high, never typed', () => {
    const logoCss = stylesheet('ui/Logo/Logo.module.css');
    expect(rule(logoCss, '.logo')).toMatch(/height: var\(--logo-h, 38px\);.*url\('\/glyphh-logo-black\.png'\)/);
    expect(fs.existsSync('public/glyphh-logo-black.png')).toBe(true);
  });
});
