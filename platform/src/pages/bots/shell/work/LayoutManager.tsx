// The layout manager, the Glyphh Bot app's (glyphh-bot src/renderer/src/LayoutManager.tsx): your layouts and the
// built-ins, and the frame editor: pick a shape or set columns and rows, merge right or down, split, pin the frame
// new panels stack into, start a frame with a panel, drag a frame onto another to swap or move it, name it, save it.
// Pins are saved. Layouts are kept in this browser.
import { useState } from 'react';
import { useEscape } from '../bits';
import { panelTitle, why } from './bits';
import {
  allLayouts,
  applyDrop,
  canMergeDown,
  canMergeRight,
  canSplit,
  CHAT,
  dropModeAt,
  emptyGrid,
  fractionsFor,
  gridFromFrames,
  isBuiltin,
  MAX_GRID,
  mergeDown,
  mergeRight,
  openLayout,
  openPanels,
  PANELS,
  resizeGrid,
  saveError,
  savedFrames,
  setPinned,
  SHAPES,
  splitFrame,
  toSaved,
  withPanels,
  type Grid,
  type SavedLayout,
} from './layouts';
import { useWork, useWorkActions, type Managing } from './store';

/** A layout's frames as a small icon: filled where a frame has panels, outlined where it is pinned. */
export function MiniGrid({ l }: { l: Pick<SavedLayout, 'cols' | 'rows' | 'colWidths' | 'rowHeights' | 'frames'> }) {
  const g = gridFromFrames(l.cols, l.rows, l.frames);
  return (
    <span
      className="minigrid"
      aria-hidden
      style={{
        gridTemplateColumns: fractionsFor(l.colWidths, g.cols).map((w) => `${w}fr`).join(' '),
        gridTemplateRows: fractionsFor(l.rowHeights, g.rows).map((h) => `${h}fr`).join(' '),
      }}
    >
      {g.frames.map((f, i) => (
        <i key={i} className={`${f.stack.length ? 'on' : ''} ${f.pinned ? 'pin' : ''}`} style={{ gridColumn: `${f.col + 1} / span ${f.colSpan}`, gridRow: `${f.row + 1} / span ${f.rowSpan}` }} />
      ))}
    </span>
  );
}

interface Draft {
  name: string;
  /** The saved layout this edit replaces (a rename drops the old name). */
  replacing?: string;
  grid: Grid;
  colWidths?: number[];
  rowHeights?: number[];
  chatWidth?: number;
}

const draftOf = (l: SavedLayout, keepName: boolean): Draft => ({
  name: keepName ? l.name : '',
  replacing: keepName ? l.name : undefined,
  grid: gridFromFrames(l.cols, l.rows, l.frames),
  colWidths: l.colWidths,
  rowHeights: l.rowHeights,
  chatWidth: l.chatWidth,
});

const describe = (stack: string[]): string => (stack.length ? stack.map(panelTitle).join(', ') : 'empty');

function Editor({ draft, onDone, onClose }: { draft: Draft; onDone: () => void; onClose: () => void }) {
  const work = useWorkActions();
  const [d, setD] = useState<Draft>(draft);
  const [sel, setSel] = useState(0);
  const [over, setOver] = useState<number | null>(null);
  const g = d.grid;
  const isNew = !d.replacing;

  /** Change the grid in a copy and keep it. */
  const edit = (fn: (g: Grid) => number | void) => {
    const copy: Grid = { cols: g.cols, rows: g.rows, frames: g.frames.map((f) => ({ ...f, stack: f.stack.slice() })) };
    const nextSel = fn(copy);
    setD({ ...d, grid: copy });
    if (typeof nextSel === 'number') setSel(nextSel);
    else if (!copy.frames[sel]) setSel(0);
  };

  const saved = (): SavedLayout => ({
    name: d.name,
    cols: g.cols,
    rows: g.rows,
    colWidths: fractionsFor(d.colWidths, g.cols),
    rowHeights: fractionsFor(d.rowHeights, g.rows),
    ...(d.chatWidth ? { chatWidth: d.chatWidth } : {}),
    frames: savedFrames(g),
  });

  const save = (open: boolean) => {
    const l = saved();
    const err = saveError(l, d.replacing);
    if (err) return work.toast(err);
    try {
      const layouts = work.saveLayout(l, d.replacing);
      // The layout on screen follows a save of itself; Save and open puts it on screen.
      if (open || (d.replacing && work.get().layout.name === d.replacing)) {
        work.set({ expanded: null });
        work.setLayout(withPanels(openLayout(layouts.find((x) => x.name === l.name.trim())!), openPanels(work.get().layout)));
      }
      work.toast(`Saved ${l.name.trim()}.`);
      if (open) onClose();
      else onDone();
    } catch (e) {
      work.toast(why(e));
    }
  };

  const options = PANELS.filter((p) => p.id !== CHAT).map((p) => ({ id: p.id, label: panelTitle(p.id) }));
  const frame = g.frames[sel];

  return (
    <div className="lm-edit">
      <label className="lm-name">
        Name
        <input value={d.name} autoFocus placeholder="My layout" onChange={(e) => setD({ ...d, name: e.target.value })} />
      </label>
      {isNew && (
        <div className="shapes">
          {SHAPES.map((s) => (
            <button
              key={s.name}
              type="button"
              className="shape"
              onClick={() => {
                const stacks = g.frames.map((f) => f.stack);
                const next = emptyGrid(s.cols, s.rows);
                for (const [i, dir] of s.merge ?? []) dir === 'down' ? mergeDown(next, i) : mergeRight(next, i);
                next.frames.forEach((f, i) => (f.stack = stacks[i] ?? []));
                setD({ ...d, grid: next, colWidths: undefined, rowHeights: undefined });
                setSel(0);
              }}
            >
              <MiniGrid l={{ cols: s.cols, rows: s.rows, frames: [] }} />
              <span>{s.name}</span>
            </button>
          ))}
        </div>
      )}
      <div className="lm-dims">
        <label>
          Columns
          <input type="number" min={1} max={MAX_GRID} value={g.cols} onChange={(e) => edit((x) => resizeGrid(x, Number(e.target.value), x.rows))} />
        </label>
        <label>
          Rows
          <input type="number" min={1} max={MAX_GRID} value={g.rows} onChange={(e) => edit((x) => resizeGrid(x, x.cols, Number(e.target.value)))} />
        </label>
        <span className="dim">These are the frames beside the chat. Panels stack into them as they open: full, then under.</span>
      </div>
      <div
        className="lm-grid"
        role="group"
        aria-label="Frames"
        style={{
          gridTemplateColumns: fractionsFor(d.colWidths, g.cols).map((w) => `${w}fr`).join(' '),
          gridTemplateRows: fractionsFor(d.rowHeights, g.rows).map((h) => `${h}fr`).join(' '),
        }}
      >
        {g.frames.map((f, i) => (
          <div
            key={`${f.col},${f.row}`}
            role="button"
            tabIndex={0}
            aria-pressed={i === sel}
            className={`lm-cell ${i === sel ? 'on' : ''} ${f.stack.length ? 'full' : ''} ${f.pinned ? 'pinned' : ''} ${over === i ? 'over' : ''}`}
            style={{ gridColumn: `${f.col + 1} / span ${f.colSpan}`, gridRow: `${f.row + 1} / span ${f.rowSpan}` }}
            draggable
            onClick={() => setSel(i)}
            onKeyDown={(e) => e.key === 'Enter' && setSel(i)}
            onDragStart={(e) => e.dataTransfer.setData('text/gb-lm', String(i))}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(i);
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(null);
              const from = Number(e.dataTransfer.getData('text/gb-lm'));
              const r = e.currentTarget.getBoundingClientRect();
              edit((x) => {
                applyDrop(x, from, i, dropModeAt((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height));
                return i;
              });
            }}
          >
            <b>{describe(f.stack)}</b>
            {f.pinned && <small>pinned · new panels go here</small>}
            {(f.colSpan > 1 || f.rowSpan > 1) && (
              <small>
                {f.colSpan} x {f.rowSpan}
              </small>
            )}
          </div>
        ))}
      </div>
      {frame && (
        <div className="lm-cellbar">
          <select
            value={frame.stack[0] ?? ''}
            title="The panel this frame opens with"
            aria-label="The panel this frame opens with"
            onChange={(e) =>
              edit((x) => {
                const id = e.target.value;
                for (const o of x.frames) o.stack = o.stack.filter((p) => p !== id);
                x.frames[sel]!.stack = id ? [id, ...x.frames[sel]!.stack.filter((p) => p !== id).slice(1)] : [];
              })
            }
          >
            <option value="">Starts empty</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                Starts with {o.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn" disabled={!canMergeRight(g, sel)} onClick={() => edit((x) => mergeRight(x, sel))}>
            Merge right
          </button>
          <button type="button" className="btn" disabled={!canMergeDown(g, sel)} onClick={() => edit((x) => mergeDown(x, sel))}>
            Merge down
          </button>
          <button type="button" className="btn" disabled={!canSplit(g, sel)} onClick={() => edit((x) => splitFrame(x, sel))}>
            Split
          </button>
          <button type="button" className={`btn ${frame.pinned ? 'primary' : ''}`} aria-pressed={!!frame.pinned} title="New panels stack into a pinned frame" onClick={() => edit((x) => setPinned(x, sel, !frame.pinned))}>
            {frame.pinned ? 'Pinned' : 'Pin'}
          </button>
        </div>
      )}
      <div className="row end">
        <button type="button" className="btn" onClick={onDone}>
          Back
        </button>
        <button type="button" className="btn" onClick={() => save(false)}>
          Save
        </button>
        <button type="button" className="btn primary" onClick={() => save(true)}>
          Save and open
        </button>
      </div>
    </div>
  );
}

const startOf = (m: Managing, saved: SavedLayout[]): Draft | null =>
  m.fresh
    ? { name: '', grid: emptyGrid(2, 1) }
    : m.edit
      ? m.copy
        ? { ...draftOf(m.edit, false), name: `${m.edit.name} copy` }
        : draftOf(m.edit, !!m.fromScreen && !isBuiltin(m.edit.name) && saved.some((l) => l.name === m.edit!.name))
      : null;

export function LayoutManager({ managing }: { managing: Managing }) {
  const work = useWorkActions();
  const saved = useWork((s) => s.layouts);
  const layout = useWork((s) => s.layout);
  const [draft, setDraft] = useState<Draft | null>(() => startOf(managing, saved));
  const [deleting, setDeleting] = useState<string | null>(null);
  const all = allLayouts(saved);
  const leave = () => work.set({ manager: null });
  useEscape(leave);
  const title = draft ? (draft.replacing ? `Edit ${draft.replacing}` : 'New layout') : 'Layouts';

  return (
    <div className="veil" onMouseDown={(e) => e.target === e.currentTarget && leave()}>
      <div className="modal wide" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="icon" aria-label="Close" onClick={leave}>
            ×
          </button>
        </div>
        {draft ? (
          <Editor draft={draft} onDone={() => setDraft(null)} onClose={leave} />
        ) : (
          <div className="lm-list">
            <p className="dim wk-lmnote">Make, edit, rename and delete layouts, and pin the frame new panels go into.</p>
            {all.map((l) => {
              const mine = !isBuiltin(l.name);
              const pinned = l.frames.some((f) => f.pinned);
              return (
                <div key={l.name} className={`lm-row ${l.name === layout.name ? 'on' : ''}`}>
                  <MiniGrid l={l} />
                  <div className="lm-main">
                    <b>{l.name}</b>
                    <small>
                      {mine ? 'yours' : 'built in'} · {l.frames.length} {l.frames.length === 1 ? 'frame' : 'frames'}
                      {pinned ? ' · one pinned' : ''}
                      {l.name === layout.name ? ' · on screen' : ''}
                    </small>
                  </div>
                  <button
                    type="button"
                    className="btn primary"
                    aria-label={`Open ${l.name}`}
                    onClick={() => {
                      work.set({ manager: null, expanded: null });
                      work.setLayout(withPanels(openLayout(l), openPanels(work.get().layout)));
                    }}
                  >
                    Open
                  </button>
                  <button type="button" className="btn" aria-label={`${mine ? 'Edit' : 'Copy'} ${l.name}`} onClick={() => setDraft(mine ? draftOf(l, true) : { ...draftOf(l, false), name: `${l.name} copy` })}>
                    {mine ? 'Edit' : 'Copy'}
                  </button>
                  {mine &&
                    (deleting === l.name ? (
                      <button
                        type="button"
                        className="btn danger"
                        aria-label={`Delete ${l.name} for good`}
                        onClick={() => {
                          work.removeLayout(l.name);
                          setDeleting(null);
                        }}
                      >
                        Delete it
                      </button>
                    ) : (
                      <button type="button" className="btn danger" aria-label={`Delete ${l.name}`} onClick={() => setDeleting(l.name)}>
                        Delete
                      </button>
                    ))}
                </div>
              );
            })}
            <div className="row end">
              <button type="button" className="btn" onClick={() => setDraft(draftOf(toSaved(layout), !isBuiltin(layout.name) && saved.some((l) => l.name === layout.name)))}>
                Save the one on screen…
              </button>
              <button type="button" className="btn primary" onClick={() => setDraft({ name: '', grid: emptyGrid(2, 1) })}>
                + New layout
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
