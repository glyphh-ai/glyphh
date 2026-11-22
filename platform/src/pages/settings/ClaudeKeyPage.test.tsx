import { screen, within } from '@testing-library/react';
import { botsFake } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

describe('the Claude key settings', () => {
  it('saves a key showing only its end, and removes it, saying nothing of how it is billed', async () => {
    const fake = on();
    const { user } = renderApp('/settings/claude-key');
    expect(await screen.findByRole('heading', { name: 'Claude key', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(/billed|markup|20%/)).not.toBeInTheDocument();

    const field = await screen.findByLabelText('Claude API key');
    expect(field).toHaveAttribute('type', 'password');
    await user.type(field, 'nope');
    await user.click(screen.getByRole('button', { name: 'Save key' }));
    expect(await screen.findByText(/That is not a Claude key/)).toBeInTheDocument();
    await user.clear(field);
    await user.type(field, 'sk-ant-api03-abcd1234');
    await user.click(screen.getByRole('button', { name: 'Save key' }));
    expect(await screen.findByText('Key ending 1234')).toBeInTheDocument();
    expect(screen.queryByText(/abcd1234/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Remove' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('Your Claude key is removed.')).toBeInTheDocument();
    expect(await screen.findByLabelText('Claude API key')).toBeInTheDocument();
    expect(fake.state.seen).toEqual(['key set', 'key removed']);
  });

  it('is in the settings sidebar', async () => {
    on();
    renderApp('/settings/general');
    expect(await screen.findByRole('link', { name: 'Claude key' })).toHaveAttribute('href', '/settings/claude-key');
  });
});
