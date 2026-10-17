import { screen } from '@testing-library/react';
import { renderApp } from '@/test/render';

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
