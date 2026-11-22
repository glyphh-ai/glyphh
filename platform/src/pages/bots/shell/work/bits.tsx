// The small parts the work panels share, from the Glyphh Bot app: the icons the shell's own set leaves out
// (glyphh-bot src/renderer/src/Menu.tsx), the menu at a point, and each panel's name and icon (panelInfo.ts).
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ICON } from '../icons';
import { PANELS, type PanelId } from './layouts';

export const WICON = {
  ...ICON,
  file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6',
  eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  code: 'M16 18l6-6-6-6M8 6l-6 6 6 6',
  back: 'M15 18l-6-6 6-6',
  forward: 'M9 18l6-6-6-6',
  editor: 'M8.5 8 4.5 12l4 4M15.5 8l4 4-4 4M13.5 5.5l-3 13',
  diff: 'M12 3v6M9 6h6M9 17h6M5 21h14a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1z',
  browser: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.5 12h17M12 3c2.6 2.6 3.6 6 3.6 9s-1 6.4-3.6 9M12 3C9.4 5.6 8.4 9 8.4 12s1 6.4 3.6 9',
  files: 'M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2h7.5A2.5 2.5 0 0 1 21 9.5v8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z',
  layout: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  grow: 'M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7',
  shrink: 'M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7',
  pin: 'M12 17v5M9 3h6l-1 6 3 3v2H7v-2l3-3z',
  terminal: 'M4 4h16a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM7 9l3 3-3 3M12.5 15H17',
  dots: 'M12 5h.01M12 12h.01M12 19h.01',
} as const;

/** The top bar's panels, in the app's order. */
export const QUICK = ['files', 'browser', 'terminal', 'editor', 'diff'] as const;

export const PANEL_ICON: Record<string, string> = {
  files: WICON.files,
  editor: WICON.editor,
  diff: WICON.diff,
  browser: WICON.browser,
  terminal: WICON.terminal,
};

/** A panel's name. The app's Browser is the Preview here: a page in a browser cannot browse the web inside itself. */
export function panelTitle(panelId: PanelId): string {
  if (panelId === 'browser') return 'Preview';
  return PANELS.find((p) => p.id === panelId)?.label ?? panelId;
}

export const why = (e: unknown): string => (e instanceof Error ? e.message : String(e));

export interface MenuItem {
  label: string;
  onPick: () => void;
  danger?: boolean;
}

/** A menu at a point; closes on a pick, a click elsewhere or Escape. */
export function Menu({ x, y, items, onClose, label = 'Menu' }: { x: number; y: number; items: MenuItem[]; onClose: () => void; label?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x, top: y });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setPos({
      left: Math.max(6, Math.min(x, window.innerWidth - el.offsetWidth - 6)),
      top: Math.max(6, Math.min(y, window.innerHeight - el.offsetHeight - 6)),
    });
  }, [x, y]);
  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', away, true);
    document.addEventListener('keydown', key, true);
    return () => {
      document.removeEventListener('mousedown', away, true);
      document.removeEventListener('keydown', key, true);
    };
  }, [onClose]);
  return (
    <div className="ctxmenu" role="menu" aria-label={label} ref={ref} style={pos}>
      {items.map((it) => (
        <button
          key={it.label}
          type="button"
          role="menuitem"
          className={it.danger ? 'danger' : ''}
          onClick={() => {
            onClose();
            it.onPick();
          }}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}
