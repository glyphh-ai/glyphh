import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export const themeChoices = ['system', 'light', 'dark', 'light-hc', 'dark-hc'] as const;
export type ThemeChoice = (typeof themeChoices)[number];
export type ResolvedTheme = Exclude<ThemeChoice, 'system'>;

const storageKey = 'glyphh.theme';

/** What a new visitor gets: high-visibility dark, the site's black and white. index.html applies the same before paint. */
export const defaultTheme: ThemeChoice = 'dark-hc';

type ThemeApi = { choice: ThemeChoice; resolved: ResolvedTheme; setChoice: (choice: ThemeChoice) => void };
const ThemeContext = createContext<ThemeApi | null>(null);

function readChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(storageKey);
    return themeChoices.includes(stored as ThemeChoice) ? (stored as ThemeChoice) : defaultTheme;
  } catch {
    return defaultTheme;
  }
}

function systemTheme(): ResolvedTheme {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

/**
 * The person's theme: high-visibility dark until they choose, then kept in this browser;
 * System, when chosen, follows the operating system as it changes.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice);
  const [system, setSystem] = useState<ResolvedTheme>(systemTheme);

  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: light)');
    if (!query) return;
    const onChange = () => setSystem(systemTheme());
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  const resolved = choice === 'system' ? system : choice;

  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
  }, [resolved]);

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      // Private windows may refuse storage; the theme still applies for this visit.
    }
  }, []);

  const api = useMemo(() => ({ choice, resolved, setChoice }), [choice, resolved, setChoice]);
  return <ThemeContext.Provider value={api}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeApi {
  const api = useContext(ThemeContext);
  if (!api) throw new Error('useTheme needs a ThemeProvider');
  return api;
}
