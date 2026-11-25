import { screen, within } from '@testing-library/react';
import { renderApp } from '@/test/render';

describe('the account menu', () => {
  it('shows the person, and goes to their account and billing', async () => {
    const { user, router } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    const menu = screen.getByRole('menu', { name: 'Account' });
    expect(within(menu).getByText('chris@example.com')).toBeInTheDocument();
    await user.click(within(menu).getByRole('menuitem', { name: 'Billing' }));
    expect(router.state.location.pathname).toBe('/settings/billing');
    expect(screen.queryByRole('menu', { name: 'Account' })).not.toBeInTheDocument();
  });

  it('switches theme, keeps it in this browser, and ticks the current one', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    await user.click(screen.getByRole('menuitem', { name: 'Theme' }));
    const themes = screen.getByRole('menu', { name: 'Theme' });
    expect(within(themes).getAllByRole('menuitemradio').map((item) => item.textContent)).toEqual([
      'High-visibility dark',
      'Dark mode',
      'Light mode',
      'Light high contrast',
      'System preference',
    ]);
    expect(within(themes).getByRole('menuitemradio', { name: 'High-visibility dark' })).toHaveAttribute('aria-checked', 'true');
    await user.click(within(themes).getByRole('menuitemradio', { name: 'Light high contrast' }));
    expect(document.documentElement.dataset.theme).toBe('light-hc');
    expect(localStorage.getItem('glyphh.theme')).toBe('light-hc');
  });

  it('opens the theme list from the keyboard', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    screen.getByRole('menuitem', { name: 'Theme' }).focus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('menu', { name: 'Theme' })).toBeInTheDocument();
    await user.keyboard('{ArrowLeft}');
    expect(screen.queryByRole('menu', { name: 'Theme' })).not.toBeInTheDocument();
  });

  it('moves between items with the arrows, and closes on Escape', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    expect(screen.getByRole('menuitem', { name: 'Account' })).toHaveFocus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Billing' })).toHaveFocus();
    await user.keyboard('{ArrowUp}{ArrowUp}');
    expect(screen.getByRole('menuitem', { name: 'Log out' })).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu', { name: 'Account' })).not.toBeInTheDocument();
  });

  it('logs out with a POST to the platform’s own route', async () => {
    const submit = vi.spyOn(HTMLFormElement.prototype, 'submit').mockImplementation(() => {});
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    await user.click(screen.getByRole('menuitem', { name: 'Log out' }));
    const form = submit.mock.contexts[0] as HTMLFormElement;
    expect(form.method).toBe('post');
    expect(form.getAttribute('action')).toBe('/auth/logout');
    submit.mockRestore();
  });

  it('opens settings', async () => {
    const { user, router } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    await user.click(screen.getByRole('menuitem', { name: 'Settings' }));
    expect(router.state.location.pathname).toBe('/settings/general');
  });

  it('goes to the person’s account', async () => {
    const { user, router } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    await user.click(screen.getByRole('menuitem', { name: 'Account' }));
    expect(router.state.location.pathname).toBe('/settings/profile');
  });

  it('closes on a click outside it, not inside, and on its button pressed again', async () => {
    const { user } = renderApp('/');
    const trigger = await screen.findByRole('button', { name: 'Chris Timmerman' });
    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await user.click(screen.getByRole('main'));
    expect(screen.queryByRole('menu', { name: 'Account' })).not.toBeInTheDocument();
    await user.click(trigger);
    await user.click(screen.getByText('chris@example.com'));
    expect(screen.getByRole('menu', { name: 'Account' })).toBeInTheDocument();
    await user.click(trigger);
    expect(screen.queryByRole('menu', { name: 'Account' })).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it.each([['{Enter}'], [' ']])('opens the theme list with %s, on its first theme', async (key) => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    screen.getByRole('menuitem', { name: 'Theme' }).focus();
    await user.keyboard(key);
    const themes = screen.getByRole('menu', { name: 'Theme' });
    expect(within(themes).getByRole('menuitemradio', { name: 'High-visibility dark' })).toHaveFocus();
  });

  it('moves on past the theme item with the arrows, and between themes inside it', async () => {
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Chris Timmerman' }));
    screen.getByRole('menuitem', { name: 'Theme' }).focus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Log out' })).toHaveFocus();
    expect(screen.queryByRole('menu', { name: 'Theme' })).not.toBeInTheDocument();

    screen.getByRole('menuitem', { name: 'Theme' }).focus();
    await user.keyboard('{ArrowRight}{ArrowDown}');
    const themes = screen.getByRole('menu', { name: 'Theme' });
    expect(within(themes).getByRole('menuitemradio', { name: 'Dark mode' })).toHaveFocus();
    expect(screen.getByRole('menu', { name: 'Account' })).toBeInTheDocument();
  });
});
