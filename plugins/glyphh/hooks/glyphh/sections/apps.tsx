// Apps: what Claude made and published to the organisation, as cards (a type
// chip, search, a type filter, a page of 24, Open at the rrotor); for a
// reviewer the views Published, Awaiting review and Rejected, with Approve,
// Reject (a reason) and Retire.
import type { Json } from '../../../types'
import {
  VIEWS,
  approveApp,
  askReason,
  cycleType,
  isReviewer,
  openApp,
  pageLine,
  pages,
  publishedLine,
  rejectApp,
  retireApp,
  rolesLine,
  searchApps,
  turnPage,
  typeChip,
  typeLabel,
  viewApps,
} from '../apps'
import { idOf, str } from '../shape'
import { kit, type Ctx, type Tone } from '../ui'

const STATE_CHIP: Record<string, { text: string; tone: Tone }> = {
  draft: { text: 'Awaiting review', tone: 'warning' },
  rejected: { text: 'Rejected', tone: 'error' },
  retired: { text: 'Retired', tone: 'subtle' },
}

function Card(ctx: Ctx, a: Json, reviewer: boolean) {
  const { gh, surface, apps: v } = ctx
  const { Box, Text, Input } = ctx.ui
  const k = kit(ctx)
  const id = idOf(a, 'app_id')
  const state = str(a.state)
  const chip = STATE_CHIP[state]
  const actions = [
    { key: `app-open-${id}`, label: 'Open', primary: true, onPress: () => openApp(gh, a, surface) },
    ...(reviewer && (state === 'draft' || state === 'rejected') ? [{ key: `app-approve-${id}`, label: 'Approve', onPress: () => approveApp(gh, id) }] : []),
    ...(reviewer && (state === 'draft' || state === 'approved') && v.rejecting !== id
      ? [{ key: `app-reject-${id}`, label: 'Reject', onPress: () => askReason(gh, id) }]
      : []),
    ...(reviewer && state === 'approved' ? [{ key: `app-retire-${id}`, label: 'Retire', onPress: () => retireApp(gh, id) }] : []),
  ]
  return k.Card(
    `app-${id}`,
    <Box flexDirection="column" gap="xs">
      <Box justifyContent="space-between" alignItems="center" gap={1}>
        <Box gap={1} alignItems="center" flexShrink={1}>
          <Text weight="semibold">{str(a.title, str(a.name))}</Text>
          {k.Chip(typeChip(a))}
          {chip ? k.Chip(chip.text, chip.tone) : null}
        </Box>
        <Text size="footnote" dimColor>
          {str(a.runtime_name, 'rrotor')} · v{str(a.version)}
        </Text>
      </Box>
      {a.description ? <Text>{str(a.description)}</Text> : null}
      <Box justifyContent="space-between" alignItems="center" gap={1}>
        <Text size="footnote" dimColor>
          {rolesLine(a)} · {publishedLine(a)}
        </Text>
        {k.Actions(actions)}
      </Box>
      {state === 'rejected' && a.reason ? <Text size="footnote" color="error">Rejected: {str(a.reason)}</Text> : null}
      {reviewer && v.rejecting === id && (
        <Box gap={1} alignItems="center">
          <Input key={`app-reason-${id}`} label="Reason" placeholder="why it is rejected" submitLabel="reject" onSubmit={why => rejectApp(gh, id, why)} />
          {k.Actions([{ key: `app-keep-${id}`, label: 'keep', onPress: () => askReason(gh, null) }])}
        </Box>
      )}
    </Box>,
  )
}

export function Apps(ctx: Ctx) {
  const { gh, me, lists, apps: v } = ctx
  const { Box, Text, Input } = ctx.ui
  const k = kit(ctx)
  const reviewer = isReviewer(me)
  const cards = lists.apps ?? []
  const last = pages(v)
  const empty = v.q
    ? `Nothing matches "${v.q}".`
    : v.type
      ? `No ${typeLabel(v).toLowerCase()} here.`
      : 'Nothing published yet. Ask Claude to publish what it made to your org, or /glyphh publish <file>.'
  return (
    <Box flexDirection="column" gap="md">
      {k.Head('Apps', 'What Claude made and published to your organisation’s rrotors. Open one at the rrotor it lives on.')}
      {reviewer &&
        k.Tabs(VIEWS.map(w => ({ key: `app-view-${w.id}`, label: w.label, active: w.id === v.state, onPress: () => viewApps(gh, w.id) })))}
      <Box gap={1} alignItems="center">
        <Input key="app-search" label="Search" value={v.q} placeholder="title, description or name" submitLabel="search" onSubmit={q => searchApps(gh, q)} />
        {k.Actions([{ key: 'app-type', label: typeLabel(v), onPress: () => cycleType(gh) }])}
      </Box>
      {cards.length === 0 ? (
        k.Empty('app-empty', empty)
      ) : (
        <Box flexDirection="column" gap="xs">
          {cards.map(a => Card(ctx, a, reviewer))}
        </Box>
      )}
      {v.total > 0 && (
        <Box justifyContent="space-between" alignItems="center" gap={1}>
          <Text size="footnote" dimColor>{pageLine(v, cards.length)}</Text>
          {k.Actions([
            ...(v.page > 1 ? [{ key: 'app-prev', label: 'Previous', onPress: () => turnPage(gh, -1) }] : []),
            ...(v.page < last ? [{ key: 'app-next', label: 'Next', onPress: () => turnPage(gh, 1) }] : []),
          ])}
        </Box>
      )}
    </Box>
  )
}
