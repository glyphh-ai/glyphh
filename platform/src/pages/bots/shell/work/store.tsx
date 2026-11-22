// The work panels' own state, as the Glyphh Bot app's store keeps it (glyphh-bot src/renderer/src/store.ts: setLayout,
// switchLayout, openPanel, closePanel, toggleExpand, togglePin, openFile): the layout on screen (the panel area only;
// the chat is the shell's), which panel is focused or expanded, the person's saved layouts, the files open in the
// Editor, and the workspace the panels read. Layouts are kept in this browser, per person. Nothing here asks the
// machine until a panel is open.
import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore, type ReactNode } from 'react';
import { useMe } from '@/api/queries';
import { workClient, type WorkClient } from '@/api/work';
import { useShell } from '../bits';
import {
  BUILTIN_LAYOUTS,
  cloneLayout,
  closePanel as closeIn,
  findLayout,
  frameOf,
  normalizeCurrent,
  normalizeSaved,
  openLayout,
  openPanel as openIn,
  openPanels,
  removeLayout,
  saveLayout,
  setPinned,
  withPanels,
  type Layout,
  type PanelId,
  type SavedLayout,
} from './layouts';

/** A file open in the Editor: its text as typed and as last saved; an image or a file with no text says which. */
export type OpenFile = { ws: string; path: string; content: string; saved: string; kind: 'text' | 'image' | 'binary' | 'big' };
/** What the layout manager is open on, when it is open. */
export type Managing = { edit?: SavedLayout; fromScreen?: boolean; copy?: boolean; fresh?: boolean };

export type WorkState = {
  place: string | null;
  runId: string | null;
  layout: Layout;
  layouts: SavedLayout[];
  focused: PanelId | null;
  expanded: PanelId | null;
  flash: PanelId | null;
  /** The workspace the panels read: a repository the crew worked in on the machine. */
  ws: string;
  openFiles: OpenFile[];
  activeFile: string;
  /** The file the Preview shows. */
  previewPath: string;
  manager: Managing | null;
  /** Bumped to make the panels read the machine again. */
  tick: number;
};

const start = (): Layout => openLayout(BUILTIN_LAYOUTS[0]!);
const key = (who: string, what: 'layout' | 'layouts') => `glyphh.work.${what}.${who}`;

function kept<T>(name: string, read: (raw: unknown) => T, otherwise: T): T {
  try {
    const raw = localStorage.getItem(name);
    return raw ? read(JSON.parse(raw)) : otherwise;
  } catch {
    return otherwise;
  }
}

export class Work {
  private state: WorkState;
  private readonly listeners = new Set<() => void>();
  private flashTimer: ReturnType<typeof setTimeout> | undefined;
  private who = 'me';
  client: WorkClient | null = null;
  toast: (text: string) => void = () => undefined;

  constructor() {
    this.state = { place: null, runId: null, layout: start(), layouts: [], focused: null, expanded: null, flash: null, ws: '', openFiles: [], activeFile: '', previewPath: '', manager: null, tick: 0 };
  }

  get = (): WorkState => this.state;
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => void this.listeners.delete(fn);
  };
  set = (change: Partial<WorkState> | ((s: WorkState) => Partial<WorkState>)) => {
    this.state = { ...this.state, ...(typeof change === 'function' ? change(this.state) : change) };
    for (const fn of this.listeners) fn();
  };

  /** Whose layouts these are: read from this browser once the person is known. */
  signIn(who: string) {
    if (who === this.who) return;
    this.who = who;
    this.set({ layouts: kept(key(who, 'layouts'), normalizeSaved, []), layout: kept(key(who, 'layout'), normalizeCurrent, null) ?? start() });
  }

  /** The machine the panels read; another machine starts with nothing open in the Editor. */
  setPlace(place: string | null, runId: string | null) {
    if (place === this.state.place) return this.set({ runId });
    this.client = place ? workClient(place) : null;
    this.set({ place, runId, ws: '', openFiles: [], activeFile: '', previewPath: '', expanded: null });
  }

  private keep(what: 'layout' | 'layouts', value: unknown) {
    try {
      localStorage.setItem(key(this.who, what), JSON.stringify(value));
    } catch {
      // A full or closed store: the layout still holds for this visit.
    }
  }

  /** Put a layout on screen; it is kept so the panels come back as they were. */
  setLayout = (layout: Layout) => {
    const s = this.state;
    this.set({
      layout,
      focused: s.focused && frameOf(layout, s.focused) >= 0 ? s.focused : null,
      expanded: s.expanded && frameOf(layout, s.expanded) >= 0 ? s.expanded : null,
    });
    this.keep('layout', layout);
  };

  /** Open one of the layouts (built-in or yours) by name: its frames and panels, and the panels open stack in. */
  switchLayout = (name: string) => {
    const l = findLayout(this.state.layouts, name);
    if (!l) return this.toast(`No layout called ${name}.`);
    this.set({ expanded: null });
    this.setLayout(withPanels(openLayout(l), openPanels(this.state.layout)));
  };

  private lightUp(panelId: PanelId) {
    this.set({ flash: panelId, focused: panelId });
    clearTimeout(this.flashTimer);
    this.flashTimer = setTimeout(() => this.set({ flash: null }), 900);
  }

  /** Open a panel: one already open is focused; a new one stacks in (full, under, full, under); `into` picks the frame. */
  openPanel = (panelId: PanelId, into?: number) => {
    const o = openIn(this.state.layout, panelId, into);
    if (o.how !== 'chat' && o.how !== 'already') this.setLayout(o.layout);
    const ex = this.state.expanded;
    if (ex && ex !== panelId) this.set({ expanded: null });
    this.lightUp(panelId);
  };

  /** Close a panel; the rest reflow. Closing the last one gives the chat the whole width. */
  closePanel = (panelId: PanelId) => this.setLayout(closeIn(this.state.layout, panelId));

  closeAllPanels = () => {
    let l = this.state.layout;
    for (const p of openPanels(l)) l = closeIn(l, p);
    this.set({ expanded: null });
    this.setLayout(l);
  };

  /** Fill the whole desk with a panel, or put it back. */
  toggleExpand = (panelId: PanelId) => this.set((s) => ({ expanded: s.expanded === panelId ? null : panelId, focused: panelId }));

  /** Pin a frame (new panels stack into it), or unpin it. */
  togglePin = (frame: number) => {
    const l = cloneLayout(this.state.layout);
    setPinned(l, frame, !l.frames[frame]?.pinned);
    this.setLayout(l);
  };

  /** Keep one of the person's layouts (a rename drops the old name); throws the reason when it cannot be kept. */
  saveLayout = (l: SavedLayout, replacing?: string): SavedLayout[] => {
    const layouts = saveLayout(this.state.layouts, l, replacing);
    this.set({ layouts });
    this.keep('layouts', layouts);
    return layouts;
  };

  removeLayout = (name: string) => {
    const layouts = removeLayout(this.state.layouts, name);
    this.set({ layouts });
    this.keep('layouts', layouts);
  };

  pickWorkspace = (ws: string) => {
    if (ws !== this.state.ws) this.set({ ws, openFiles: [], activeFile: '', previewPath: '' });
  };

  /** Open a file of the workspace in the Editor (read from the machine the first time). */
  openFile = async (path: string): Promise<void> => {
    const { ws, openFiles } = this.state;
    if (!this.client || !ws) return;
    if (!openFiles.some((f) => f.path === path)) {
      const image = /\.(png|jpe?g|gif|webp|bmp|ico)$/i.test(path);
      const read = image ? null : await this.client.file(ws, path);
      const kind: OpenFile['kind'] = image ? 'image' : read!.binary ? 'binary' : read!.truncated || read!.text === null ? 'big' : 'text';
      const content = kind === 'text' ? (read!.text ?? '') : '';
      if (this.state.ws !== ws) return;
      this.set((s) => ({ openFiles: [...s.openFiles.filter((f) => f.path !== path), { ws, path, content, saved: content, kind }] }));
    }
    this.set({ activeFile: path });
    this.openPanel('editor');
  };

  /** Show a file of the workspace in the Preview. */
  preview = (path: string) => {
    this.set({ previewPath: path });
    this.openPanel('browser');
  };

  refresh = () => this.set((s) => ({ tick: s.tick + 1 }));
}

const WorkContext = createContext<Work | null>(null);

/** The work panels' state for what is selected: inert (no machine asked, nothing drawn) unless it runs on a rrotor. */
export function WorkProvider({ runsOn, runId, children }: { runsOn: string | null | undefined; runId?: string | null; children: ReactNode }) {
  const work = useMemo(() => new Work(), []);
  const me = useMe();
  const shell = useShell();
  const toast = useRef(shell.toast);
  toast.current = shell.toast;
  work.toast = (text) => toast.current(text);
  const who = me.data?.id;
  useEffect(() => {
    if (who) work.signIn(who);
  }, [work, who]);
  useEffect(() => work.setPlace(runsOn ?? null, runId ?? null), [work, runsOn, runId]);
  return <WorkContext.Provider value={work}>{children}</WorkContext.Provider>;
}

/** The store itself, for its actions; null outside a WorkProvider. */
export const useWorkStore = (): Work | null => useContext(WorkContext);

const NOTHING = new Work();

/** A part of the work panels' state, read again when it changes. */
export function useWork<T>(select: (s: WorkState) => T): T {
  const work = useContext(WorkContext) ?? NOTHING;
  return useSyncExternalStore(work.subscribe, () => select(work.get()));
}

/** The store, where it must be there (inside the panels). */
export function useWorkActions(): Work {
  return useContext(WorkContext) ?? NOTHING;
}
