// The mod's /config rows (plugin.json `userConfig`), as `register` receives
// them: where effects play, and the two optional fun hooks (off unless set).
import type { PluginOptions } from 'claude-code'

import type { Display } from '../../types'

export type Settings = {
  display: Display
  /** Confetti when a turn that ran longer than LONG_TURN_MS ends. */
  confettiAfterLongTurn: boolean
  /** A matrix rain while Claude's tools run. */
  matrixWhileTools: boolean
}

export const DEFAULT_SETTINGS: Settings = { display: 'claude-window', confettiAfterLongTurn: false, matrixWhileTools: false }

export function settingsOf(options: PluginOptions): Settings {
  return {
    display: options.display === 'fullscreen' ? 'fullscreen' : 'claude-window',
    confettiAfterLongTurn: options.confetti_after_long_turn === true,
    matrixWhileTools: options.matrix_while_tools === true,
  }
}
