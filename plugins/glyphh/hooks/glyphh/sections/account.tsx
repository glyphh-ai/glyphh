// Account: name (rename), email, sign-ins (add, remove), this machine's
// rrotor (link), installs (revoke), sign out.
import type { AuthState } from '../../../types'
import { signOut } from '../account'
import { linkLocalRrotor, rename, revokeInstall, updateRrotor } from '../actions'
import { isLinked, linkLine, type RrotorHealth } from '../link'
import { RROTOR_PINNED, isBehind } from '../rrotor'
import { idOf, str, userOf } from '../shape'
import { SignIns } from './signins'
import { day, kit, type Ctx, type Tone } from '../ui'

/** This machine's rrotor: where its link stands, and Link (again) when it runs. */
function LocalRrotor(ctx: Ctx) {
  const { gh, lists } = ctx
  const k = kit(ctx)
  const health = (lists.rrotor?.[0] ?? { status: 'none' }) as unknown as RrotorHealth
  const tone: Tone | undefined = isLinked(health) ? 'success' : health.status === 'up' ? 'warning' : undefined
  const behind = health.status === 'up' && isBehind(health.version)
  return k.Group(
    'rrotor',
    "This machine's rrotor",
    k.Row({
      key: 'rrotor-row',
      primary: linkLine(health),
      tone,
      chip: behind ? { text: `Update to ${RROTOR_PINNED}`, tone: 'warning' } : undefined,
      actions:
        health.status === 'up'
          ? [
              ...(behind ? [{ key: 'rrotor-update', label: 'update', onPress: () => updateRrotor(gh) }] : []),
              { key: 'rrotor-link', label: isLinked(health) ? 'link again' : 'link', onPress: () => linkLocalRrotor(gh) },
            ]
          : [],
    }),
    health.status === 'none' || health.status === 'down'
      ? undefined
      : behind
        ? `rrotor ${health.version} is older than this plugin’s ${RROTOR_PINNED}: update pulls the release and keeps everything on the volume.`
        : 'Linked, it shows on the platform’s Runtimes page and its apps reach your organisation’s catalogue.',
  )
}

export function Account(ctx: Ctx, a: AuthState) {
  const { gh, me, lists } = ctx
  const { Box, Input } = ctx.ui
  const k = kit(ctx)
  const user = userOf(me)
  const installs = lists.installs ?? []
  const mine = a.status === 'in' ? a.install_id : ''
  return (
    <Box flexDirection="column" gap="md">
      {k.Head('Account', 'Who you are to Glyphh, how you sign in, and the machines signed in as you.')}
      <Box flexDirection="column" gap="xs">
        <Input key="me-name" label="Name" value={str(user.name)} submitLabel="rename" onSubmit={v => rename(gh, v)} />
        {k.Field('me-email', 'Email', str(user.email, '—'))}
      </Box>
      {SignIns(ctx)}
      {LocalRrotor(ctx)}
      {k.Group(
        'installs',
        'Installs',
        <Box flexDirection="column" gap="xs">
          {installs.length === 0 && k.Empty('inst-none', 'None listed.')}
          {installs.map(i => {
            const id = idOf(i, 'install_id')
            return k.Row({
              key: `inst-row-${id}`,
              primary: str(i.name, 'install'),
              chip: id === mine ? { text: 'This device', tone: 'claude' } : undefined,
              secondary: `${str(i.surface, '?')}${i.last_seen_at ? ` · seen ${day(i.last_seen_at)}` : ''}`,
              actions: [{ key: `inst-revoke-${id}`, label: 'revoke', onPress: () => revokeInstall(gh, id) }],
            })
          })}
        </Box>,
      )}
      {k.Buttons([{ key: 'signout', label: 'Sign out', onPress: () => signOut(gh) }])}
    </Box>
  )
}
