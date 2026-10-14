// Org: name (rename, admin), members with roles (remove, admin), invites
// (send → a link to copy, revoke, pending).

import { removeMember, renameOrg, revokeInvite, sendInvite } from '../actions'
import { idOf, isAdmin, obj, orgOf, str, userOf } from '../shape'
import { say } from '../state'
import { linkOrText, type Ctx } from '../ui'

async function Invites(ctx: Ctx, admin: boolean) {
  const { gh, lists, surface } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const link = await gh.state.inviteLink.get()
  const invites = (lists.invites ?? []).filter(i => !i.accepted_at)
  return (
    <Box flexDirection="column">
      <Text bold>Invites</Text>
      {invites.length === 0 && <Text dimColor>No pending invites.</Text>}
      {invites.map(i => {
        const id = idOf(i, 'invite_id')
        return (
          <Box key={`inv-row-${id}`} gap={1}>
            <Text>{str(i.email)}{i.expires_at ? ` · expires ${str(i.expires_at)}` : ''}</Text>
            {admin && <Button key={`inv-revoke-${id}`} plain label="revoke" onPress={() => revokeInvite(gh, id)} />}
          </Box>
        )
      })}
      {admin && <Input key="inv-email" label="Invite " placeholder="email" submitLabel="send" onSubmit={v => sendInvite(gh, v)} />}
      {link && (
        <Box gap={1}>
          {linkOrText(ctx.ui, 'inv-link', link)}
          <Button
            key="inv-copy"
            label="Copy link"
            onPress={async () => {
              const copied = await gh.copy(link, surface)
              await say(gh, copied ? 'Invite link copied.' : 'Copy the invite link above.')
            }}
          />
        </Box>
      )}
    </Box>
  )
}

export async function Org(ctx: Ctx) {
  const { gh, me, lists } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const admin = isAdmin(me)
  const org = { ...orgOf(me), ...obj(lists.org?.[0]) }
  const self = idOf(userOf(me), 'user_id')
  const members = lists.members ?? []
  return (
    <Box flexDirection="column" gap={1}>
      {admin ? (
        <Input key="org-name" label="Org " value={str(org.name)} submitLabel="rename" onSubmit={v => renameOrg(gh, v)} />
      ) : (
        <Text>Org: {str(org.name, '—')}</Text>
      )}
      <Box flexDirection="column">
        <Text bold>Members</Text>
        {members.map(m => {
          const id = idOf(m, 'user_id')
          const canRemove = admin && id !== self && str(m.role) !== 'admin'
          return (
            <Box key={`mem-row-${id}`} gap={1}>
              <Text>{str(m.name || m.email)} · {str(m.email)} · {str(m.role, 'member')}</Text>
              {canRemove && <Button key={`mem-remove-${id}`} plain label="remove" onPress={() => removeMember(gh, id)} />}
            </Box>
          )
        })}
      </Box>
      {await Invites(ctx, admin)}
    </Box>
  )
}
