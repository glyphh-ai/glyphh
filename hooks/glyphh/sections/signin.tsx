// Sign in: the code, the link, waiting; every section shows this signed out.
import type { RenderSurface } from 'claude-code'

import type { AuthState } from '../../../types'
import { describe } from '../api'
import { startSignIn, stopPolling } from '../device'
import { openUrl } from '../open'
import { say } from '../state'
import { linkOrText, type Ctx } from '../ui'
import type { Host } from '../host'

export async function beginSignIn(gh: Host, surface?: RenderSurface) {
  try {
    await startSignIn(gh, surface)
  } catch (err) {
    await gh.state.auth.set((): AuthState => ({ status: 'out', error: describe(err) }))
  }
}

async function cancel(gh: Host) {
  stopPolling()
  await gh.state.auth.set((): AuthState => ({ status: 'out' }))
}

export function SignIn(ctx: Ctx, a: AuthState) {
  const { gh, surface } = ctx
  const { Box, Text, Button } = ctx.ui
  if (a.status === 'pending') {
    return (
      <Box flexDirection="column" gap={1}>
        <Text>Enter this code on the sign-in page:</Text>
        <Text bold color="claude">{a.user_code}</Text>
        {linkOrText(ctx.ui, 'signin-link', a.verification_uri_complete, a.verification_uri)}
        <Text dimColor>
          {a.opened ? 'The page is open in the browser pane.' : 'Open the link in your browser.'} Waiting for approval…
        </Text>
        <Box gap={1}>
          {surface === 'desktop' && (
            <Button key="signin-open" label="Open page" onPress={() => void openUrl(gh, a.verification_uri_complete, surface)} />
          )}
          <Button
            key="signin-copy"
            label="Copy link"
            onPress={async () => {
              const copied = await gh.copy(a.verification_uri_complete, surface)
              await say(gh, copied ? 'Link copied.' : 'Copy the link above.')
            }}
          />
          <Button key="signin-cancel" label="Cancel" onPress={() => cancel(gh)} />
        </Box>
      </Box>
    )
  }
  return (
    <Box flexDirection="column" gap={1}>
      <Text>Sign in to Glyphh with Google or GitHub to see your account, org, plan and workspaces.</Text>
      {a.status === 'out' && a.error && <Text color="error">{a.error}</Text>}
      <Box>
        <Button key="signin" label="Sign in" variant="primary" onPress={() => beginSignIn(gh, surface)} />
      </Box>
    </Box>
  )
}
