// Org: name (rename, admin), members with roles (remove, admin), invites
// (send → a link to copy, revoke, pending).

import { removeMember, renameOrg, revokeInvite, sendInvite } from '../actions'
import { idOf, isAdmin, obj, orgOf, str, userOf } from '../shape'
import { say } from '../state'
import { day, kit, linkOrText, type Ctx } from '../ui'

async function Invites(ctx: Ctx, admin: boolean) {
  const { gh, lists, surface } = ctx
  const { Box, Input } = ctx.ui
  const k = kit(ctx)
  const link = await gh.state.inviteLink.get()
  const invites = (lists.invites ?? []).filter(i => !i.accepted_at)
  return k.Group(
    'invites',
    'Invites',
    <Box flexDirection="column" gap="xs">
      {invites.length === 0 && k.Empty('inv-none', 'No pending invites.')}
      {invites.map(i => {
        const id = idOf(i, 'invite_id')
        return k.Row({
          key: `inv-row-${id}`,
          primary: str(i.email),
          secondary: i.expires_at ? `Expires ${day(i.expires_at)}` : 'Pending',
          actions: admin ? [{ key: `inv-revoke-${id}`, label: 'revoke', onPress: () => revokeInvite(gh, id) }] : [],
        })
      })}
      {admin && <Input key="inv-email" label="Invite" placeholder="email" submitLabel="send" onSubmit={v => sendInvite(gh, v)} />}
      {link &&
        k.Row({
          key: 'inv-link-row',
          primary: 'Invite link',
          below: <Box paddingLeft={0}>{linkOrText(ctx.ui, 'inv-link', link)}</Box>,
          actions: [
            {
              key: 'inv-copy',
              label: 'Copy link',
              onPress: async () => {
                const copied = await gh.copy(link, surface)
                await say(gh, copied ? 'Invite link copied.' : 'Copy the invite link above.')
              },
            },
          ],
        })}
    </Box>,
    admin ? 'An invite is a link: send it yourself, or the email on it opens the same door.' : undefined,
  )
}

export async function Org(ctx: Ctx) {
  const { gh, me, lists } = ctx
  const { Box, Input } = ctx.ui
  const k = kit(ctx)
  const admin = isAdmin(me)
  const org = { ...orgOf(me), ...obj(lists.org?.[0]) }
  const self = idOf(userOf(me), 'user_id')
  const members = lists.members ?? []
  return (
    <Box flexDirection="column" gap="md">
      {k.Head('Organisation', 'Your organisation on Glyphh: its people, and who is invited.')}
      {admin ? (
        <Input key="org-name" label="Name" value={str(org.name)} submitLabel="rename" onSubmit={v => renameOrg(gh, v)} />
      ) : (
        k.Field('org-name', 'Name', str(org.name, '—'))
      )}
      {k.Group(
        'members',
        `Members · ${members.length}`,
        <Box flexDirection="column" gap="xs">
          {members.length === 0 && k.Empty('mem-none', 'Nobody yet.')}
          {members.map(m => {
            const id = idOf(m, 'user_id')
            const role = str(m.role, 'member')
            const canRemove = admin && id !== self && role !== 'admin'
            return k.Row({
              key: `mem-row-${id}`,
              primary: str(m.name || m.email),
              chip: role === 'admin' ? { text: 'Admin', tone: 'claude' } : id === self ? { text: 'You' } : undefined,
              secondary: str(m.email),
              actions: canRemove ? [{ key: `mem-remove-${id}`, label: 'remove', onPress: () => removeMember(gh, id) }] : [],
            })
          })}
        </Box>,
      )}
      {await Invites(ctx, admin)}
    </Box>
  )
}
