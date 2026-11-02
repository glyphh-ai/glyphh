// The panel's kit: the few shapes every section is built from, so the
// sections read as one and sit in Claude's own look (its type scale, its
// theme colours, its buttons). A section composes Head, Group, Row, Field,
// Chip, Actions and Empty; nothing else draws text of its own style.
import type { Elements, RenderSurface } from 'claude-code'

import type { AppsView, Json } from '../../types'
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
  /** Where the Apps section stands (its search, page, view and type). */
  apps: AppsView
  /** rrotor's parts of the panel shown (GLYPHH_RROTOR=1); shelved otherwise (2026-11-02, ./shelved). */
  rrotor?: boolean
}

/** A colour with a meaning, from Claude's theme. */
export type Tone = 'success' | 'error' | 'warning' | 'claude' | 'subtle'

/** Whether a surface draws `href` as a link: https, or http on localhost (a
 *  Link with any other address refuses the whole panel). */
export const isLinkable = (href: string) => /^https:\/\/[^\s]+$|^http:\/\/localhost(:\d+)?(\/[^\s]*)?$/.test(href)

/** A link where the surface takes one, else its address as text to copy. */
export function linkOrText(ui: Ui, key: string, href: string, label?: string) {
  const { Link, Text } = ui
  return isLinkable(href) ? <Link href={href} label={label} /> : <Text key={key}>{href}</Text>
}

type Node = ReturnType<Ui['Box']>
type Action = { key: string; label: string; onPress: () => unknown; primary?: boolean }

/** One row of a list: what it is, a dim line under it (beside it on the
 *  terminal, which has one text size), and its actions at the right, drawn
 *  plain and dim so the row's words lead. */
export type RowProps = {
  key: string
  primary: string
  secondary?: string
  /** The primary's colour, for a state (an online rrotor, a plan the org is on). */
  tone?: Tone
  /** A small word after the primary: the row's kind or state. */
  chip?: { text: string; tone?: Tone }
  actions?: Action[]
  /** Drawn under the row (an input the row opened). */
  below?: Node | null | false
}

export function kit(ctx: Pick<Ctx, 'ui' | 'surface'>) {
  const { Box, Text, Button } = ctx.ui
  const terminal = ctx.surface === 'terminal'

  const Chip = (text: string, tone: Tone = 'subtle') => (
    <Text size="caption" weight="semibold" color={tone}>{text}</Text>
  )

  const Actions = (actions: Action[]) => (
    <Box gap={1} flexShrink={0}>
      {actions.map(a =>
        a.primary ? (
          <Button key={a.key} label={a.label} variant="primary" onPress={a.onPress} />
        ) : (
          <Button key={a.key} plain dimColor label={a.label} onPress={a.onPress} />
        ),
      )}
    </Box>
  )

  return {
    /** The section's title and the one line that says what it is for. */
    Head: (title: string, description?: string) => (
      <Box flexDirection="column">
        <Text size="heading" weight="semibold">{title}</Text>
        {description ? <Text size="footnote" dimColor>{description}</Text> : null}
      </Box>
    ),

    /** Rows under a small label. */
    Group: (key: string, label: string, children: unknown, note?: string) => (
      <Box key={key} flexDirection="column" gap="xs">
        <Text size="caption" weight="semibold" color="subtle">{label.toUpperCase()}</Text>
        {children}
        {note ? <Text size="footnote" dimColor>{note}</Text> : null}
      </Box>
    ),

    Row: (r: RowProps) => (
      <Box key={r.key} flexDirection="column">
        <Box justifyContent="space-between" alignItems="center" gap={1}>
          <Box flexDirection={terminal ? 'row' : 'column'} gap={terminal ? 1 : 0} flexShrink={1}>
            <Box gap={1} alignItems="center">
              <Text color={r.tone} weight={r.tone ? 'medium' : undefined}>{r.primary}</Text>
              {r.chip ? Chip(r.chip.text, r.chip.tone) : null}
            </Box>
            {r.secondary ? <Text size="footnote" dimColor>{r.secondary}</Text> : null}
          </Box>
          {r.actions && r.actions.length ? Actions(r.actions) : null}
        </Box>
        {r.below || null}
      </Box>
    ),

    /** A label and its value on one line, the labels of a column lined up. */
    Field: (key: string, label: string, value: string | Node, tone?: Tone) => (
      <Box key={key} gap={1} alignItems="center">
        <Box width={11} flexShrink={0}>
          <Text size="footnote" dimColor>{label}</Text>
        </Box>
        {typeof value === 'string' ? <Text color={tone}>{value}</Text> : value}
      </Box>
    ),

    Chip,
    Actions,

    /** A list with nothing in it, in one quiet line. */
    Empty: (key: string, text: string) => (
      <Text key={key} size="footnote" dimColor>{text}</Text>
    ),

    /** A sentence in a tone: the panel's last word, a warning in a section. */
    Note: (key: string, text: string, tone: Tone, link?: Node | null) => (
      <Box key={key} borderStyle="round" borderColor={tone} borderDimColor paddingX={1} gap={1} alignItems="center">
        <Text size="footnote" color={tone}>{text}</Text>
        {link || null}
      </Box>
    ),

    /** The main and secondary buttons of a section, in one row. */
    Buttons: (buttons: Action[]) => (
      <Box gap={1}>
        {buttons.map(b => (
          <Button key={b.key} label={b.label} variant={b.primary ? 'primary' : 'secondary'} onPress={b.onPress} />
        ))}
      </Box>
    ),

    /** A card: a bordered block with its own rows. */
    Card: (key: string, children: unknown) => (
      <Box key={key} flexDirection="column" borderStyle="round" borderDimColor paddingX={1} gap="xs">
        {children}
      </Box>
    ),

    /** Tabs: the open one in Claude's colour, the others dim; one press each. */
    Tabs: (tabs: { key: string; label: string; active: boolean; onPress: () => unknown }[]) => (
      <Box gap="md" alignItems="center">
        {tabs.map(t => (
          <Button key={t.key} plain label={t.label} onPress={t.onPress}>
            <Text weight={t.active ? 'semibold' : 'regular'} color={t.active ? 'claude' : undefined} dimColor={!t.active}>
              {t.label}
            </Text>
          </Button>
        ))}
      </Box>
    ),
  }
}

/** When the server stamps something, the date alone reads better than the stamp. */
export const day = (stamp: unknown): string => {
  const s = String(stamp ?? '')
  return /^\d{4}-\d{2}-\d{2}/.test(s) ? s.slice(0, 10) : s
}
