import type { Register } from 'claude-code'

import { registerGlyphh } from './glyphh/index'

export const register: Register = on => {
  registerGlyphh(on)
}
