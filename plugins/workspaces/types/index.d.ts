/** What a cell shows: a favourite's live page, or one of the desktop app's panes. */
export type Panel = 'browser' | 'files' | 'changes' | 'terminal'

/** A page kept once and shown in any workspace: `~/.glyphh/favorites.json`.
 *  `keep_in_panel` keeps it in its cell: a jump to the native app (Slack,
 *  Teams, Zoom) and a popup load in the same page. */
export type Favorite = { id: string; name: string; url: string; keep_in_panel: boolean }

/** A cell of a workspace's grid, `col_span` × `row_span` slots (1 when
 *  absent); a browser cell shows a favourite, by id. */
export type FileCell = { panel: Panel; col: number; row: number; col_span?: number; row_span?: number; favorite?: string }

/** A workspace's file, `~/.glyphh/workspaces/<slug>.json`. */
export type WorkspaceFile = {
  name: string
  /** The folder the session moves to (absolute); null leaves it where it is. */
  folder: string | null
  /** The model and effort the session takes on a switch (for this session
   *  only, as /model and /effort set them); null leaves them as they are. */
  model: string | null
  effort: string | null
  cols: number
  rows: number
  /** Column widths and row heights, as fractions; dragged in the layout page. */
  col_widths: number[]
  row_heights: number[]
  cells: FileCell[]
}

/** A workspace as read: its file and the slug the file is named by. */
export type Entry = { slug: string; file: WorkspaceFile }

/** What the editor offers for a workspace's model and effort: the /config
 *  menu's model row's values, and /effort's levels. */
export type Choices = { models: string[]; efforts: string[] }

/** The mod's settings (rows of Claude's /config menu), as the page reads them. */
export type PageSettings = { home: 'wall' | 'last workspace'; dock: boolean; dockAutoHide: boolean; iconsPerPage: number }

/** The running layout page helper: where it listens and its token, kept in
 *  the session's memory (never on disk) so a reload of the mod finds it again. */
export type HelperInfo = { port: number; token: string }

/** Where Google Chrome and Node are, as the session start found them. */
export type Requirements = { chrome: string | null; node: string | null }

/** The licence as this install holds it. */
export type LicenceState = {
  /** A licence that checked out, kept in the store. */
  licence: string | null
  /** When this install first ran, in ms: the trial counts from it. */
  trialStartedAt: number | null
  /** Checkout is open and the site is being asked whether it went through. */
  isWaiting: boolean
  /** What the last unlock attempt came to. */
  note: string | null
}

declare module 'claude-code' {
  interface PluginState {
    workspaces: {
      licence: LicenceState
      entries: Entry[]
      favorites: Favorite[]
      active: string | null
      /** The workspace before the last switch: where `/dip back` goes. */
      previous: string | null
      requirements: Requirements | null
      helper: HelperInfo | null
      choices: Choices
      /** The Browser pane's tab showing the layout page, kept across reloads. */
      layoutTab: string | null
    }
  }
}
