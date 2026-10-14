/** One cell of a layout: a live browser or a file, at a grid position. */
export type Cell = {
  panel: 'browser' | 'file' | 'tree' | 'editor' | 'terminal' | 'diff' | 'claude'
  col: number
  row: number
  /** Rows the cell covers, from `row` down; default 1. */
  rowSpan?: number
  /** browser: the page it opens on. */
  url?: string
  /** file: a path, absolute or relative to the session's directory. */
  path?: string
}

/** A layout: the Glyphh workspace grid (cols × rows, fractional widths). */
export type Layout = {
  name: string
  cols: number
  rows: number
  colWidths: number[]
  rowHeights: number[]
  cells: Cell[]
  /** On the Claude desktop app: the app's own side panes this layout opens
   *  (the rest close), in order, the last in front; and the sidebar. */
  desktop?: {
    /** The app's View-menu panes, opened in this order (the rest close):
     *  `files` the Files pane as a browser, `editor` the Files pane at the
     *  open file, `changes` the diff, `terminal`, `browser`. */
    panes: ('files' | 'editor' | 'changes' | 'terminal' | 'browser')[]
    collapseSidebar?: boolean
    /** The folder the session moves to (absolute); absent, it stays put. */
    folder?: string
  }
}

/** A workspace's file, `~/.glyphh/workspaces/<slug>.json`: its session, its
 *  grid with the saved sizes, the desktop panes it opens, its cells and tabs. */
export type WorkspaceFile = {
  name: string
  model: string | null
  folder: string | null
  permission_mode: string | null
  effort: string | null
  cols: number
  rows: number
  col_widths: number[]
  row_heights: number[]
  desktop_panes: ('files' | 'editor' | 'changes' | 'terminal' | 'browser')[]
  collapse_sidebar: boolean
  cells: WorkspaceCell[]
  tabs: WorkspaceTab[]
}

/** A cell of a workspace file; a browser cell shows `tabs[tab]`. */
export type WorkspaceCell = {
  panel: Cell['panel']
  col: number
  row: number
  row_span?: number
  tab?: number
  path?: string
}

/** A tab: a URL with its name, no redirect, and its RPA (commands, sequences). */
export type WorkspaceTab = {
  url: string
  name: string
  no_redirect: boolean
  rpa: { commands: unknown[]; sequences: unknown[] }
}

/** The sign-in state the panels draw. The device code stays in session memory. */
export type AuthState =
  | { status: 'out'; error?: string }
  | {
      status: 'pending'
      device_code: string
      user_code: string
      verification_uri: string
      verification_uri_complete: string
      interval: number
      expires_at: number
      opened: boolean
    }
  | { status: 'in'; install_id: string }

export type GlyphhSection = 'account' | 'org' | 'plan' | 'billing' | 'workspaces'

/** The panel's last word: what an action did or why not, and a page to open. */
export type GlyphhNote = { text: string; isError: boolean; link?: string }

/** A JSON object the server answered, kept as it came. */
export type Json = { [key: string]: unknown }

/** The checked license: what it says, and whether it checked out. */
export type LicenseInfo = { ok: boolean; error?: string; plan?: string; features: Record<string, boolean>; limits: Record<string, number | null>; expires_at?: string }

/** What a browser cell's page last reported. */
export type PageInfo = { url: string; title: string }

export type HelperState =
  | { status: 'off' }
  | { status: 'starting' }
  | { status: 'ready' }
  | { status: 'failed'; error: string }

declare module 'claude-code' {
  interface PluginState {
    glyphh: {
      layouts: Layout[]
      active: string
      /** The layout before the last switch: where `/dip back` goes. */
      previous: string | null
      pages: Record<string, PageInfo>
      scroll: Record<string, number>
      helper: HelperState
      /** The file the layout's editor shows, absolute. */
      openFile: string | null
      /** The file browser's open folders, absolute. */
      expanded: string[]
      /** Files with unsaved edits. */
      dirty: Record<string, boolean>
      /** The terminal cell's lines. */
      termLog: string[]
      /** Browser-pane tab per cell id: kept across the mod's reloads. */
      paneTabs: Record<string, string>
      /** Glyphh account panels: sign-in, the open section, what the server said. */
      auth: AuthState
      section: GlyphhSection
      me: Json | null
      lists: Record<string, Json[]>
      note: GlyphhNote | null
      /** The workspace the Workspaces section edits. */
      selected: string | null
      inviteLink: string | null
      license: LicenseInfo | null
    }
  }
}
