// Account: name (rename), email, providers, installs (revoke), sign out.
import type { AuthState } from '../../../types'
import { signOut } from '../account'
import { rename, revokeInstall } from '../actions'
import { idOf, str, userOf } from '../shape'
import type { Ctx } from '../ui'

export function Account(ctx: Ctx, a: AuthState) {
  const { gh, me, lists } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const user = userOf(me)
  const providers = Array.isArray(user.providers) ? (user.providers as unknown[]).map(p => str(p)).join(', ') : ''
  const installs = lists.installs ?? []
  const mine = a.status === 'in' ? a.install_id : ''
  return (
    <Box flexDirection="column" gap={1}>
      <Input key="me-name" label="Name " value={str(user.name)} submitLabel="rename" onSubmit={v => rename(gh, v)} />
      <Text>Email: {str(user.email, '—')}</Text>
      {providers && <Text>Signs in with: {providers}</Text>}
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
                {id === mine ? ' · this machine' : ''}
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
