// xterm as the Glyphh Bot app's Terminal panel sets it up (glyphh-bot src/renderer/src/panels/Terminal.tsx: its
// theme, font and scrollback), behind one small door so the panel can be tested without a canvas. Here it only shows
// what the machine ran: it takes no typing (a rrotor serves a record of commands, not a shell).
import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

const THEME = {
  background: '#000000',
  foreground: '#e8e8e8',
  cursor: '#000000',
  cursorAccent: '#000000',
  selectionBackground: 'rgba(255,255,255,0.22)',
  black: '#000000',
  red: '#ff6b6b',
  green: '#7ee2a8',
  yellow: '#f5d97a',
  blue: '#8ab4ff',
  magenta: '#d7a6ff',
  cyan: '#7fdbea',
  white: '#d0d0d0',
  brightBlack: '#999999',
  brightRed: '#ff8f8f',
  brightGreen: '#a4f0c4',
  brightYellow: '#fbe7a6',
  brightBlue: '#b1ccff',
  brightMagenta: '#e6c6ff',
  brightCyan: '#a9eaf4',
  brightWhite: '#ffffff',
};

export type Term = { write: (text: string) => void; clear: () => void; dispose: () => void };

/** A terminal drawn in `el` that fits it as it is resized. */
export function makeTerm(el: HTMLElement): Term {
  const term = new Terminal({
    cursorBlink: false,
    disableStdin: true,
    convertEol: true,
    fontFamily: "'JetBrains Mono Variable', 'JetBrains Mono', 'SF Mono', Menlo, monospace",
    fontSize: 12,
    theme: THEME,
    scrollback: 10_000,
    allowProposedApi: true,
  });
  const fit = new FitAddon();
  term.loadAddon(fit);
  term.open(el);
  let gone = false;
  const size = () => {
    if (gone || !el.clientWidth || !el.clientHeight) return;
    try {
      fit.fit();
    } catch {
      // Not laid out yet: the next resize fits it.
    }
  };
  const ro = new ResizeObserver(() => requestAnimationFrame(size));
  ro.observe(el);
  requestAnimationFrame(size);
  return {
    write: (text) => term.write(text),
    clear: () => term.reset(),
    dispose: () => {
      gone = true;
      ro.disconnect();
      term.dispose();
    },
  };
}
