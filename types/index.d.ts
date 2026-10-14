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

/** What a browser cell's page last reported. */
export type PageInfo = { url: string; title: string }

export type HelperState =
  | { status: 'off' }
  | { status: 'starting' }
  | { status: 'ready' }
  | { status: 'failed'; error: string }

declare module 'claude-code' {
  interface PluginState {
    workspaces: {
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
    }
  }
}
