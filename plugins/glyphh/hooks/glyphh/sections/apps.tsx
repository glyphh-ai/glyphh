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
import type { Ctx } from '../ui'

function Card(ctx: Ctx, a: Json, reviewer: boolean) {
  const { gh, surface, apps: v } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const id = idOf(a, 'app_id')
  const state = str(a.state)
  return (
    <Box key={`app-${id}`} flexDirection="column" borderStyle="round" paddingX={1}>
      <Box gap={1}>
        <Text bold>{str(a.title, str(a.name))}</Text>
        <Text dimColor>
          {typeChip(a)} · {str(a.runtime_name, 'rrotor')} · v{str(a.version)}
        </Text>
      </Box>
      {a.description ? <Text>{str(a.description)}</Text> : null}
      <Text dimColor>
        {rolesLine(a)} · {publishedLine(a)}
        {state === 'rejected' && a.reason ? ` · rejected: ${str(a.reason)}` : ''}
      </Text>
      <Box gap={1}>
        <Button key={`app-open-${id}`} label="Open" onPress={() => openApp(gh, a, surface)} />
        {reviewer && (state === 'draft' || state === 'rejected') && (
          <Button key={`app-approve-${id}`} plain label="Approve" onPress={() => approveApp(gh, id)} />
        )}
        {reviewer && (state === 'draft' || state === 'approved') && v.rejecting !== id && (
          <Button key={`app-reject-${id}`} plain label="Reject" onPress={() => askReason(gh, id)} />
        )}
        {reviewer && state === 'approved' && <Button key={`app-retire-${id}`} plain label="Retire" onPress={() => retireApp(gh, id)} />}
      </Box>
      {reviewer && v.rejecting === id && (
        <Box gap={1}>
          <Input key={`app-reason-${id}`} label="Reason " placeholder="why it is rejected" submitLabel="reject" onSubmit={why => rejectApp(gh, id, why)} />
          <Button key={`app-keep-${id}`} plain label="keep" onPress={() => askReason(gh, null)} />
        </Box>
      )}
    </Box>
  )
}

export function Apps(ctx: Ctx) {
  const { gh, me, lists, apps: v } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const reviewer = isReviewer(me)
  const cards = lists.apps ?? []
  const last = pages(v)
  const empty = v.q
    ? `Nothing matches "${v.q}".`
    : v.type
      ? `No ${typeLabel(v).toLowerCase()} here.`
      : 'Nothing published yet. Ask Claude to publish what it made to your org, or /glyphh publish <file>.'
  return (
    <Box flexDirection="column" gap={1}>
      <Text dimColor>What Claude made and published to your organisation's rrotors: pages, dashboards, docs, diagrams, decks and designs. Open one at the rrotor it lives on.</Text>
      {reviewer && (
        <Box gap={1}>
          {VIEWS.map(w => (
            <Button key={`app-view-${w.id}`} label={w.label} variant={w.id === v.state ? 'primary' : 'secondary'} onPress={() => viewApps(gh, w.id)} />
          ))}
        </Box>
      )}
      <Box gap={1}>
        <Input key="app-search" label="Search " value={v.q} placeholder="title, description or name" submitLabel="search" onSubmit={q => searchApps(gh, q)} />
        <Button key="app-type" plain label={typeLabel(v)} onPress={() => cycleType(gh)} />
      </Box>
      {cards.length === 0 && <Text dimColor>{empty}</Text>}
      {cards.map(a => Card(ctx, a, reviewer))}
      <Box gap={1}>
        <Text dimColor>{pageLine(v, cards.length)}</Text>
        {v.page > 1 && <Button key="app-prev" plain label="Previous" onPress={() => turnPage(gh, -1)} />}
        {v.page < last && <Button key="app-next" plain label="Next" onPress={() => turnPage(gh, 1)} />}
      </Box>
    </Box>
  )
}
