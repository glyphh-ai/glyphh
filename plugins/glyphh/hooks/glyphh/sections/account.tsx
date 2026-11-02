// Account: name (rename), email, sign-ins (add, remove), installs (revoke),
// this machine's rrotor (link), sign out.
import type { AuthState } from '../../../types'
import { signOut } from '../account'
import { linkLocalRrotor, rename, revokeInstall } from '../actions'
import { isLinked, linkLine, type RrotorHealth } from '../link'
import { idOf, str, userOf } from '../shape'
import { SignIns } from './signins'
import type { Ctx } from '../ui'

/** This machine's rrotor: where its link stands, and Link (again) when it runs. */
function LocalRrotor(ctx: Ctx) {
  const { gh, lists } = ctx
  const { Box, Text, Button } = ctx.ui
  const health = (lists.rrotor?.[0] ?? { status: 'none' }) as unknown as RrotorHealth
  return (
    <Box flexDirection="column">
      <Text bold>This machine's rrotor</Text>
      <Box gap={1}>
        <Text key="rrotor-link-state">{linkLine(health)}</Text>
        {health.status === 'up' && (
          <Button key="rrotor-link" plain label={isLinked(health) ? 'link again' : 'link'} onPress={() => linkLocalRrotor(gh)} />
        )}
      </Box>
    </Box>
  )
}

export function Account(ctx: Ctx, a: AuthState) {
  const { gh, me, lists } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const user = userOf(me)
  const installs = lists.installs ?? []
  const mine = a.status === 'in' ? a.install_id : ''
  return (
    <Box flexDirection="column" gap={1}>
      <Input key="me-name" label="Name " value={str(user.name)} submitLabel="rename" onSubmit={v => rename(gh, v)} />
      <Text>Email: {str(user.email, '—')}</Text>
      {SignIns(ctx)}
      {LocalRrotor(ctx)}
      <Box flexDirection="column">
        <Text bold>Installs</Text>
        {installs.length === 0 && <Text dimColor>None listed.</Text>}
        {installs.map(i => {
          const id = idOf(i, 'install_id')
          return (
            <Box key={`inst-row-${id}`} gap={1}>
              <Text>
                {str(i.name, 'install')} · {str(i.surface, '?')}
                {i.last_seen_at ? ` · seen ${str(i.last_seen_at)}` : ''}
                {id === mine ? ' · this device' : ''}
              </Text>
              <Button key={`inst-revoke-${id}`} plain label="revoke" onPress={() => revokeInstall(gh, id)} />
            </Box>
          )
        })}
      </Box>
      <Box>
        <Button key="signout" label="Sign out" onPress={() => signOut(gh)} />
      </Box>
    </Box>
  )
}
