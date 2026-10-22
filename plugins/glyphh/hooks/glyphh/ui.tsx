import type { Elements, RenderSurface } from 'claude-code'

import type { Json } from '../../types'
import type { Host } from './host'

/** The elements every panel uses: the terminal's and the desktop's alike. */
export type Ui = Pick<Elements['desktop'], 'Box' | 'Text' | 'Button' | 'Input' | 'Select' | 'Link'>

/** What a section draws from. */
export type Ctx = {
  gh: Host
  ui: Ui
  surface: RenderSurface
  me: Json | null
  lists: Record<string, Json[]>
}

/** Whether a surface draws `href` as a link: https, or http on localhost (a
 *  Link with any other address refuses the whole panel). */
export const isLinkable = (href: string) => /^https:\/\/[^\s]+$|^http:\/\/localhost(:\d+)?(\/[^\s]*)?$/.test(href)

/** A link where the surface takes one, else its address as text to copy. */
export function linkOrText(ui: Ui, key: string, href: string, label?: string) {
  const { Link, Text } = ui
  return isLinkable(href) ? <Link href={href} label={label} /> : <Text key={key}>{href}</Text>
}
