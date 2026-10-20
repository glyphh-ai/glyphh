import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, useTheme } from './ThemeProvider';

function Show() {
  const { choice, resolved, setChoice } = useTheme();
  return (
    <>
      <p>{`${choice} → ${resolved}`}</p>
      <button type="button" onClick={() => setChoice('light')}>
        Light mode
      </button>
    </>
  );
}

/** A stand-in for the operating system's light/dark setting, which can change while the page is open. */
function fakeSystem(light: boolean) {
  const listeners = new Set<() => void>();
  const original = window.matchMedia;
  const state = { light };
  window.matchMedia = ((media: string) =>
    ({
      media,
      get matches() {
        return state.light;
      },
      addEventListener: (_: string, listener: () => void) => listeners.add(listener),
      removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
    }) as unknown as MediaQueryList) as typeof window.matchMedia;
  return {
    listeners,
    change(next: boolean) {
      state.light = next;
      listeners.forEach((listener) => listener());
    },
    restore: () => (window.matchMedia = original),
  };
}

describe('ThemeProvider', () => {
  it('gives a new visitor high-visibility dark, whatever the system prefers', () => {
    const system = fakeSystem(true);
    try {
      render(
        <ThemeProvider>
          <Show />
        </ThemeProvider>,
      );
      expect(screen.getByText('dark-hc → dark-hc')).toBeInTheDocument();
      expect(document.documentElement.dataset.theme).toBe('dark-hc');
    } finally {
      system.restore();
    }
  });

  it('follows the system once chosen, and keeps following it as it changes', () => {
    localStorage.setItem('glyphh.theme', 'system');
    const system = fakeSystem(true);
    try {
      const view = render(
        <ThemeProvider>
          <Show />
        </ThemeProvider>,
      );
      expect(screen.getByText('system → light')).toBeInTheDocument();
      expect(document.documentElement.dataset.theme).toBe('light');
      act(() => system.change(false));
      expect(screen.getByText('system → dark')).toBeInTheDocument();
      expect(document.documentElement.dataset.theme).toBe('dark');
      view.unmount();
      expect(system.listeners.size).toBe(0);
    } finally {
      system.restore();
    }
  });

  it('uses the theme kept in this browser', () => {
    localStorage.setItem('glyphh.theme', 'light-hc');
    render(
      <ThemeProvider>
        <Show />
      </ThemeProvider>,
    );
    expect(screen.getByText('light-hc → light-hc')).toBeInTheDocument();
  });

  it('ignores a kept value it does not know', () => {
    localStorage.setItem('glyphh.theme', 'sepia');
    render(
      <ThemeProvider>
        <Show />
      </ThemeProvider>,
    );
    expect(screen.getByText('dark-hc → dark-hc')).toBeInTheDocument();
  });

  it('still works when the browser refuses storage', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError');
    });
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError');
    });
    try {
      render(
        <ThemeProvider>
          <Show />
        </ThemeProvider>,
      );
      expect(screen.getByText('dark-hc → dark-hc')).toBeInTheDocument();
      await userEvent.setup().click(screen.getByRole('button', { name: 'Light mode' }));
      expect(screen.getByText('light → light')).toBeInTheDocument();
      expect(document.documentElement.dataset.theme).toBe('light');
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
  });

  it('falls back to dark in a browser that cannot report the system theme', () => {
    localStorage.setItem('glyphh.theme', 'system');
    const original = window.matchMedia;
    // @ts-expect-error: older browsers have no matchMedia at all.
    delete window.matchMedia;
    try {
      render(
        <ThemeProvider>
          <Show />
        </ThemeProvider>,
      );
      expect(screen.getByText('system → dark')).toBeInTheDocument();
    } finally {
      window.matchMedia = original;
    }
  });

  it('needs a ThemeProvider', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Show />)).toThrow('useTheme needs a ThemeProvider');
    vi.mocked(console.error).mockRestore();
  });
});
