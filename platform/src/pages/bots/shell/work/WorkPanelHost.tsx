// The panel area of the Glyphh Bot app's desk (glyphh-bot src/renderer/src/Desk.tsx), beside the shell's chat:
// panels stack in as they open (full, under, full, under) inside the layout's frames (layouts.ts decides where); each
// has a header to drag it to another frame, expand it over the whole desk, or close it (the rest reflow). A pinned
// frame takes every new panel. Every panel is placed absolutely from deskRects and rendered in a stable order, so a
// reflow never remounts an editor. Its left edge is the seam against the chat. With no panel open it draws nothing.
import { useEffect, useRef, useState } from 'react';
import { Icon } from '../icons';
import { PANEL_ICON, panelTitle, WICON } from './bits';
import { DiffPanel } from './Diff';
import { EditorPanel } from './Editor';
import { FilesPanel } from './Files';
import { cloneLayout, deskRects, evenFractions, frameSeams, moveSeam, type Rect } from './layouts';
import { PreviewPanel } from './Preview';
import { useWork, useWorkActions } from './store';
import { TerminalPanel } from './Terminal';
import './work.css';

function Panel({ panelId }: { panelId: string }) {
  switch (panelId) {
    case 'terminal':
      return <TerminalPanel />;
    case 'files':
      return <FilesPanel />;
    case 'editor':
      return <EditorPanel />;
    case 'diff':
      return <DiffPanel />;
    case 'browser':
      return <PreviewPanel />;
    default:
      return (
        <div className="empty">
          <b>Unknown panel</b>
          <p>{panelId}</p>
        </div>
      );
  }
}

const pct = (r: Rect): React.CSSProperties => ({ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%` });

/** Drop data: a panel's header. */
const PANEL_DRAG = 'text/gb-panel';
const CHAT_MIN_PX = 420;
const AREA_MIN_PX = 360;

export function WorkPanelHost() {
  const work = useWorkActions();
  const place = useWork((s) => s.place);
  const layout = useWork((s) => s.layout);
  const focused = useWork((s) => s.focused);
  const flash = useWork((s) => s.flash);
  const expanded = useWork((s) => s.expanded);
  const host = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const [over, setOver] = useState<number | null>(null);
  const [desk, setDesk] = useState(1200);

  // The desk is the row the chat and the panels share: the panel area takes its share of that width.
  useEffect(() => {
    const row = host.current?.closest('.deskrow') ?? host.current?.parentElement;
    if (!row || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => setDesk(row.clientWidth || 1200));
    ro.observe(row);
    setDesk(row.clientWidth || 1200);
    return () => ro.disconnect();
  }, [place]);

  if (!place) return null;

  // The chat keeps at least 420px, so its composer stays on one line.
  const r = deskRects(layout, expanded, false, CHAT_MIN_PX / desk);
  const showing = r.area !== null || (expanded !== null && r.panels.some((p) => !p.hidden));
  const area = r.area ?? { x: 0, y: 0, w: 1, h: 1 };
  // deskRects speaks in fractions of the desk; this host is the panel area alone.
  const inArea = (x: Rect): Rect => (r.area ? { x: (x.x - area.x) / area.w, y: x.y, w: x.w / area.w, h: x.h } : x);
  const multi = layout.frames.length > 1;
  // A stable order: React never moves a panel's DOM, so an editor never remounts.
  const panels = r.panels.slice().sort((a, b) => (a.panelId < b.panelId ? -1 : 1));
  const width = Math.max(AREA_MIN_PX, Math.round(area.w * desk));

  const drag = (e: React.MouseEvent, move: (fx: number, fy: number) => void, dir: 'v' | 'h', within: 'desk' | 'area' = 'area') => {
    e.preventDefault();
    const el = body.current;
    const row = host.current?.closest('.deskrow') ?? host.current?.parentElement;
    if (!el || !row) return;
    document.body.classList.add(dir === 'v' ? 'resizing-v' : 'resizing-h');
    const mv = (ev: MouseEvent) => {
      const b = el.getBoundingClientRect();
      const d = row.getBoundingClientRect();
      // fx is in the desk's width for the chat's seam, in the panel area's for a frame's.
      move(within === 'desk' ? (ev.clientX - d.left) / d.width : (ev.clientX - b.left) / b.width, (ev.clientY - b.top) / b.height);
    };
    const up = () => {
      document.body.classList.remove('resizing-v', 'resizing-h');
      window.removeEventListener('mousemove', mv);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', up);
  };

  const dropOn = (frame: number) => ({
    onDragOver: (e: React.DragEvent) => {
      if (!e.dataTransfer.types.includes(PANEL_DRAG)) return;
      e.preventDefault();
      if (over !== frame) setOver(frame);
    },
    onDragLeave: (e: React.DragEvent) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null);
    },
    onDrop: (e: React.DragEvent) => {
      setOver(null);
      const p = e.dataTransfer.getData(PANEL_DRAG);
      if (!p) return;
      e.preventDefault();
      work.openPanel(p, frame);
    },
  });

  return (
    <div ref={host} className={`wk-host ${showing ? '' : 'shut'} ${expanded && showing ? 'expanded' : ''}`} style={showing && !expanded ? { width } : undefined} data-layout={layout.name}>
      <div className="dbodyw" ref={body}>
        {/* frames holding open panels: their outline when pinned or dragged over (empty frames are never drawn) */}
        {r.frames.map(({ idx, rect }) => {
          const f = layout.frames[idx]!;
          return <div key={`f${f.col},${f.row}`} className={`dframe ${f.pinned && multi ? 'pinned' : ''} ${over === idx ? 'over' : ''}`} style={pct(inArea(rect))} {...dropOn(idx)} />;
        })}

        {/* the panels, each where its frame's stack puts it */}
        {panels.map((p) => {
          const f = layout.frames[p.frame]!;
          const head = f.stack[0] === p.panelId;
          const isEx = expanded === p.panelId;
          const title = panelTitle(p.panelId);
          const rect = isEx ? p.rect : inArea(p.rect);
          return (
            <section
              key={p.panelId}
              aria-label={title}
              className={`dslot panel ${focused === p.panelId ? 'focus' : ''} ${flash === p.panelId ? 'flash' : ''} ${over === p.frame ? 'over' : ''}`}
              style={p.hidden ? { ...pct(rect), display: 'none' } : pct(rect)}
              onMouseDownCapture={() => focused !== p.panelId && work.set({ focused: p.panelId })}
              {...dropOn(p.frame)}
            >
              <div
                className="dhead"
                draggable
                title="Drag onto another frame to move it there"
                onDragStart={(e) => {
                  e.dataTransfer.setData(PANEL_DRAG, p.panelId);
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onDoubleClick={() => work.toggleExpand(p.panelId)}
              >
                <Icon d={PANEL_ICON[p.panelId] ?? WICON.layout} size={14} />
                <span className="dtitle">{title}</span>
                <span className="spacer" />
                {multi && head && !isEx && (
                  <button
                    type="button"
                    className={`pinbtn ${f.pinned ? 'on' : ''}`}
                    aria-pressed={!!f.pinned}
                    aria-label={f.pinned ? `Unpin the frame ${title} is in` : `Pin the frame ${title} is in`}
                    title={f.pinned ? 'Pinned: new panels stack into this frame' : 'Pin this frame: new panels stack into it'}
                    onClick={() => work.togglePin(p.frame)}
                  >
                    <Icon d={WICON.pin} size={13} />
                    {f.pinned && 'Pinned'}
                  </button>
                )}
                <button type="button" title={isEx ? 'Put it back' : 'Expand'} aria-label={isEx ? `Put ${title} back` : `Expand ${title}`} onClick={() => work.toggleExpand(p.panelId)}>
                  <Icon d={isEx ? WICON.shrink : WICON.grow} size={13} />
                </button>
                <button type="button" title="Close" aria-label={`Close ${title}`} onClick={() => work.closePanel(p.panelId)}>
                  ×
                </button>
              </div>
              <div className="dbody">
                <Panel panelId={p.panelId} />
              </div>
            </section>
          );
        })}

        {/* seams: chat | panels, and between frames */}
        {r.area && (
          <div
            className="seam v"
            style={{ left: 0, top: 0, height: '100%' }}
            title="Drag to resize"
            onMouseDown={(e) =>
              drag(
                e,
                (fx) => {
                  const l = cloneLayout(work.get().layout);
                  l.chatWidth = Math.max(0.2, Math.min(0.8, +fx.toFixed(4)));
                  work.setLayout(l);
                },
                'v',
                'desk',
              )
            }
          />
        )}
        {r.area &&
          r.exact &&
          frameSeams(layout).map((s) => (
            <div
              key={`${s.dir}${s.i}-${s.rect.x}-${s.rect.y}`}
              className={`seam ${s.dir}`}
              style={s.dir === 'v' ? { left: `${s.rect.x * 100}%`, top: `${s.rect.y * 100}%`, height: `${s.rect.h * 100}%` } : { top: `${s.rect.y * 100}%`, left: `${s.rect.x * 100}%`, width: `${s.rect.w * 100}%` }}
              title="Drag to resize · double-click to even out"
              onMouseDown={(e) =>
                drag(
                  e,
                  (fx, fy) => {
                    const l = cloneLayout(work.get().layout);
                    if (s.dir === 'v') l.colWidths = moveSeam(l.colWidths, s.i, fx);
                    else l.rowHeights = moveSeam(l.rowHeights, s.i, fy);
                    work.setLayout(l);
                  },
                  s.dir,
                )
              }
              onDoubleClick={() => {
                const l = cloneLayout(work.get().layout);
                if (s.dir === 'v') l.colWidths = evenFractions(l.cols);
                else l.rowHeights = evenFractions(l.rows);
                work.setLayout(l);
              }}
            />
          ))}
      </div>
    </div>
  );
}
