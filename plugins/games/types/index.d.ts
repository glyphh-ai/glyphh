/** The page's helper, as the unlock module reads it: Games has no
 *  page, so it is always null. */
export type HelperInfo = { port: number; token: string }

/** The licence as this install holds it (hooks/unlock). */
export type LicenceState = {
  /** A licence that checked out, kept in the store. */
  licence: string | null
  /** Checkout is open and the site is being asked whether it went through. */
  isWaiting: boolean
  /** What the last unlock attempt came to. */
  note: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'games': {
      licence: LicenceState
      helper: HelperInfo | null
    }
  }
}
