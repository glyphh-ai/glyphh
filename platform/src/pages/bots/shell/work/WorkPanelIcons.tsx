// The top bar's panel buttons, the Glyphh Bot app's (glyphh-bot src/renderer/src/App.tsx PanelButtons): each opens
// its panel (or closes it when it is open), and the last opens the layouts: put one on screen, close every panel, or
// open the layout manager. Drawn only when what is selected runs on a rrotor.
import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from '../icons';
import { Menu, PANEL_ICON, panelTitle, QUICK, WICON } from './bits';
import { LayoutManager } from './LayoutManager';
import { allLayouts, frameOf, openPanels } from './layouts';
import { useWork, useWorkActions } from './store';

export function WorkPanelIcons() {
  const work = useWorkActions();
  const place = useWork((s) => s.place);
  const layout = useWork((s) => s.layout);
  const saved = useWork((s) => s.layouts);
  const manager = useWork((s) => s.manager);
  const [more, setMore] = useState<{ x: number; y: number } | null>(null);
  const bar = useRef<HTMLDivElement>(null);
  if (!place) return null;
  const isOpen = (id: string): boolean => frameOf(layout, id) >= 0;
  const any = openPanels(layout).length > 0;
  return (
    <div className="pbtns" role="toolbar" aria-label="Work panels" ref={bar}>
      {QUICK.map((id) => (
        <button
          key={id}
          type="button"
          className={`icon ${isOpen(id) ? 'on' : ''}`}
          title={`${panelTitle(id)}${isOpen(id) ? ' (open: click to close)' : ''}`}
          aria-label={panelTitle(id)}
          aria-pressed={isOpen(id)}
          onClick={() => (isOpen(id) ? work.closePanel(id) : work.openPanel(id))}
        >
          <Icon d={PANEL_ICON[id]!} size={16} />
        </button>
      ))}
      <button
        type="button"
        className="icon"
        title="Layouts"
        aria-label="Layouts"
        aria-haspopup="menu"
        aria-expanded={!!more}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setMore({ x: r.right - 200, y: r.bottom + 4 });
        }}
      >
        <Icon d={WICON.dots} size={16} />
      </button>
      {/* The manager is a modal over the whole app, as the app draws it: it mounts on the shell, not in the bar. */}
      {manager && createPortal(<LayoutManager managing={manager} />, bar.current?.closest('.app') ?? document.body)}
      {more && (
        <Menu
          x={more.x}
          y={more.y}
          label="Layouts"
          onClose={() => setMore(null)}
          items={[
            ...allLayouts(saved).map((l) => ({ label: `${l.name === layout.name ? '✓ ' : ''}${l.name}`, onPick: () => work.switchLayout(l.name) })),
            ...(any ? [{ label: 'Close all panels', onPick: work.closeAllPanels }] : []),
            { label: 'Manage layouts…', onPick: () => work.set({ manager: {} }) },
          ]}
        />
      )}
    </div>
  );
}
