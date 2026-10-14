// The sign-in, inline in the chat: drawn in place of /glyphh login's reply row
// and of the glyphh_login tool's result, live (it redraws as the sign-in moves
// on). The code here; the login page beside it, in the browser pane.
import type { AuthState, Json } from '../../types'
import { planName, str, userOf } from './shape'
import type { Ui } from './ui'

export function InlineSignIn(ui: Ui, a: AuthState, me: Json | null) {
  const { Box, Text } = ui
  if (a.status === 'in') {
    const who = me ? str(userOf(me).email) : ''
    return (
      <Box flexDirection="column" borderStyle="round" paddingX={1}>
        <Text bold>Glyphh</Text>
        <Text color="success">{who ? `Signed in as ${who} · ${planName(me)}` : 'Signed in.'}</Text>
      </Box>
    )
  }
  if (a.status === 'pending') {
    return (
      <Box flexDirection="column" borderStyle="round" paddingX={1}>
        <Text bold>Sign in to Glyphh</Text>
        <Text dimColor>Your sign-in code:</Text>
        <Text bold color="claude">{a.user_code}</Text>
        <Text dimColor>Approve this code on the Glyphh page in the browser pane. This updates when you're signed in.</Text>
      </Box>
    )
  }
  return (
    <Box flexDirection="column" borderStyle="round" paddingX={1}>
      <Text bold>Glyphh</Text>
      <Text color={a.error ? 'error' : undefined}>{a.error ?? 'Signed out.'}</Text>
    </Box>
  )
}
