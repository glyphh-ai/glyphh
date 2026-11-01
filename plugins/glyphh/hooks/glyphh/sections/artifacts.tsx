// Artifacts: the organisation's published pages as cards (search, a page of
// 24, Open at the rrotor); for a reviewer the views Published, Awaiting review
// and Rejected, with Approve, Reject (a reason) and Retire.
import type { Json } from '../../../types'
import {
  VIEWS,
  approveArtifact,
  askReason,
  isReviewer,
  openArtifact,
  pageLine,
  pages,
  publishedLine,
  rejectArtifact,
  retireArtifact,
  rolesLine,
  searchArtifacts,
  turnPage,
  viewArtifacts,
} from '../artifacts'
import { idOf, str } from '../shape'
import type { Ctx } from '../ui'

function Card(ctx: Ctx, a: Json, reviewer: boolean) {
  const { gh, surface, artifacts: v } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const id = idOf(a, 'artifact_id')
  const state = str(a.state)
  return (
    <Box key={`art-${id}`} flexDirection="column" borderStyle="round" paddingX={1}>
      <Box gap={1}>
        <Text bold>{str(a.title, str(a.name))}</Text>
        <Text dimColor>{str(a.runtime_name, 'rrotor')} · v{str(a.version)}</Text>
      </Box>
      {a.description ? <Text>{str(a.description)}</Text> : null}
      <Text dimColor>
        {rolesLine(a)} · {publishedLine(a)}
        {state === 'rejected' && a.reason ? ` · rejected: ${str(a.reason)}` : ''}
      </Text>
      <Box gap={1}>
        <Button key={`art-open-${id}`} label="Open" onPress={() => openArtifact(gh, a, surface)} />
        {reviewer && (state === 'draft' || state === 'rejected') && (
          <Button key={`art-approve-${id}`} plain label="Approve" onPress={() => approveArtifact(gh, id)} />
        )}
        {reviewer && (state === 'draft' || state === 'approved') && v.rejecting !== id && (
          <Button key={`art-reject-${id}`} plain label="Reject" onPress={() => askReason(gh, id)} />
        )}
        {reviewer && state === 'approved' && <Button key={`art-retire-${id}`} plain label="Retire" onPress={() => retireArtifact(gh, id)} />}
      </Box>
      {reviewer && v.rejecting === id && (
        <Box gap={1}>
          <Input key={`art-reason-${id}`} label="Reason " placeholder="why it is rejected" submitLabel="reject" onSubmit={why => rejectArtifact(gh, id, why)} />
          <Button key={`art-keep-${id}`} plain label="keep" onPress={() => askReason(gh, null)} />
        </Box>
      )}
    </Box>
  )
}

export function Artifacts(ctx: Ctx) {
  const { gh, me, lists, artifacts: v } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const reviewer = isReviewer(me)
  const cards = lists.artifacts ?? []
  const last = pages(v)
  return (
    <Box flexDirection="column" gap={1}>
      <Text dimColor>The pages Claude published to your organisation's rrotors. Open one at the rrotor it lives on.</Text>
      {reviewer && (
        <Box gap={1}>
          {VIEWS.map(w => (
            <Button key={`art-view-${w.id}`} label={w.label} variant={w.id === v.state ? 'primary' : 'secondary'} onPress={() => viewArtifacts(gh, w.id)} />
          ))}
        </Box>
      )}
      <Input key="art-search" label="Search " value={v.q} placeholder="title, description or name" submitLabel="search" onSubmit={q => searchArtifacts(gh, q)} />
      {cards.length === 0 && (
        <Text dimColor>{v.q ? `Nothing matches "${v.q}".` : 'Nothing published yet. Ask Claude to publish an artifact to your org, or /glyphh publish <file>.'}</Text>
      )}
      {cards.map(a => Card(ctx, a, reviewer))}
      <Box gap={1}>
        <Text dimColor>{pageLine(v, cards.length)}</Text>
        {v.page > 1 && <Button key="art-prev" plain label="Previous" onPress={() => turnPage(gh, -1)} />}
        {v.page < last && <Button key="art-next" plain label="Next" onPress={() => turnPage(gh, 1)} />}
      </Box>
    </Box>
  )
}
