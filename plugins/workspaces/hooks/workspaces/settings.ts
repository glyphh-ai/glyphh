// The mod's settings, rows of Claude's own /config menu (plugin.json's
// userConfig: each a picker over its options), as the layout page reads them.
import type { PluginOptions } from 'claude-code'

import type { PageSettings } from '../../types'

export const ICONS_PER_PAGE = ['24', '40', '56'] as const

const pick = <T extends string>(v: unknown, allowed: readonly T[], fallback: T): T => (allowed.includes(v as T) ? (v as T) : fallback)

/** The settings made whole: a value outside a field's options takes its default. */
export function settingsOf(options: PluginOptions): PageSettings {
  return {
    home: pick(options.home, ['wall', 'last workspace'], 'wall'),
    dock: pick(options.dock, ['on', 'off'], 'on') === 'on',
    dockAutoHide: pick(options.dockAutoHide, ['on', 'off'], 'on') === 'on',
    iconsPerPage: Number(pick(options.iconsPerPage, ICONS_PER_PAGE, '40')),
  }
}
