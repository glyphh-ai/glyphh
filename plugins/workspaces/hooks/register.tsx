// Workspaces: one command sets up the Claude desktop app for a kind of work.
// The licence's hooks go first, so they stand around the mod's own.
import type { Register } from 'claude-code'

import { licensing } from './licence/hooks.tsx'
import { workspaces } from './workspaces/hooks.tsx'

export const register: Register = (on, options) => {
  licensing(on)
  workspaces(on, options)
}
