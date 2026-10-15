// Drips: visual effects over Claude, in its window or over the whole screen.
// The licence's hooks go first, so they stand around the mod's own.
import type { Register } from 'claude-code'

import { drips } from './drips/hooks.tsx'
import { licensing } from './licence/hooks.tsx'

export const register: Register = (on, options) => {
  licensing(on)
  drips(on, options)
}
