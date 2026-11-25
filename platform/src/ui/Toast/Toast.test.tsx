import { act, render, screen } from '@testing-library/react';
import { ToastProvider, useToast } from './Toast';

function Say({ message, tone }: { message: string; tone?: 'info' | 'error' }) {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.show(message, tone)}>
      Say it
    </button>
  );
}

describe('Toast', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('announces a message, then lets it go after four seconds', () => {
    render(
      <ToastProvider>
        <Say message="Name saved." />
      </ToastProvider>,
    );
    act(() => screen.getByRole('button', { name: 'Say it' }).click());
    expect(screen.getByRole('status')).toHaveTextContent('Name saved.');
    act(() => vi.advanceTimersByTime(3999));
    expect(screen.getByRole('status')).toHaveTextContent('Name saved.');
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });

  it('marks an error so it reads as one', () => {
    render(
      <ToastProvider>
        <Say message="That did not save." tone="error" />
      </ToastProvider>,
    );
    act(() => screen.getByRole('button', { name: 'Say it' }).click());
    expect(screen.getByText('That did not save.')).toHaveAttribute('data-tone', 'error');
  });

  it('keeps each message for its own four seconds', () => {
    render(
      <ToastProvider>
        <Say message="One" />
      </ToastProvider>,
    );
    act(() => screen.getByRole('button', { name: 'Say it' }).click());
    act(() => vi.advanceTimersByTime(2000));
    act(() => screen.getByRole('button', { name: 'Say it' }).click());
    expect(screen.getAllByText('One')).toHaveLength(2);
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getAllByText('One')).toHaveLength(1);
  });

  it('needs a ToastProvider', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Say message="x" />)).toThrow('useToast needs a ToastProvider');
    vi.mocked(console.error).mockRestore();
  });
});
