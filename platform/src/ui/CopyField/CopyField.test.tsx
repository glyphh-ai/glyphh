import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CopyButton, CopyField } from './CopyField';

describe('CopyField', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => vi.useRealTimers());

  it('copies the value, says so for a moment, then offers to copy again', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CopyField value="tr-77" label="trace id" />);
    await user.click(screen.getByRole('button', { name: 'Copy trace id' }));
    expect(await navigator.clipboard.readText()).toBe('tr-77');
    expect(screen.getByRole('button', { name: 'Copy trace id' })).toHaveTextContent('Copied');
    act(() => vi.advanceTimersByTime(1600));
    expect(screen.getByRole('button', { name: 'Copy trace id' })).toHaveTextContent('Copy');
  });

  it('starts the moment afresh on a second copy', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CopyField value="tr-77" label="trace id" />);
    const button = screen.getByRole('button', { name: 'Copy trace id' });
    await user.click(button);
    act(() => vi.advanceTimersByTime(1000));
    await user.click(button);
    act(() => vi.advanceTimersByTime(1000));
    expect(button).toHaveTextContent('Copied');
    act(() => vi.advanceTimersByTime(600));
    expect(button).toHaveTextContent('Copy');
  });
});

describe('CopyButton', () => {
  it('copies the value beside it, and its name says when it has', async () => {
    const user = userEvent.setup();
    render(<CopyButton value="https://chris-7f3a.glyphh.app" label="address" />);
    await user.click(screen.getByRole('button', { name: 'Copy address' }));
    expect(await navigator.clipboard.readText()).toBe('https://chris-7f3a.glyphh.app');
    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
  });
});
