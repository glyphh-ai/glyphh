// Games: games over Claude's window or the whole screen.
// The licence's hooks (the one-time unlock) go first, so they stand around the mod's own.
import type { Register } from 'claude-code'

import { arcade } from './arcade/hooks.tsx'
import { licensing } from './unlock/hooks.tsx'

export const register: Register = (on, options) => {
  licensing(on)
  arcade(on, options)
}
