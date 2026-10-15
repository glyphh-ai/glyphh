/** A saved recipe, as `/drip save <name> <recipe>` and the Drips page keep it. */
export type CustomDrip = { name: string; recipe: string }

/** Where effects play: the /config row `display`. */
export type Display = 'claude-window' | 'fullscreen'

/** The running Drips page helper: where it listens and its token, kept in
 *  the session's memory (never on disk) so a reload of the mod finds it again. */
export type HelperInfo = { port: number; token: string }

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
    drips: {
      licence: LicenceState
      helper: HelperInfo | null
      /** The Browser pane's tab showing the Drips page, kept across reloads. */
      pageTab: string | null
      /** Node, as the session start found it (it runs the page's helper). */
      node: string | null
    }
  }
}
