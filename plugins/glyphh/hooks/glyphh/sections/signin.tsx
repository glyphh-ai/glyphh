// Sign in: the code, the link, waiting; every section shows this signed out.
import type { RenderSurface } from 'claude-code'

import type { AuthState } from '../../../types'
import { describe } from '../api'
import { startSignIn, stopPolling } from '../device'
import { openUrl } from '../open'
import { say } from '../state'
import { kit, linkOrText, type Ctx } from '../ui'
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
  const { Box, Text } = ctx.ui
  const k = kit(ctx)
  if (a.status === 'pending') {
    return (
      <Box flexDirection="column" gap="md">
        {k.Head('Sign in to Glyphh', 'Enter this code on the sign-in page, then approve it there.')}
        <Text size="title" weight="semibold" color="claude" mono>{a.user_code}</Text>
        <Box flexDirection="column" gap="xs">
          {linkOrText(ctx.ui, 'signin-link', a.verification_uri_complete, a.verification_uri)}
          <Text size="footnote" dimColor>
            {a.opened ? 'The page is open in the browser pane.' : 'Open the link in your browser.'} Waiting for approval…
          </Text>
        </Box>
        {k.Buttons([
          ...(surface === 'desktop'
            ? [{ key: 'signin-open', label: 'Open page', primary: true, onPress: () => void openUrl(gh, a.verification_uri_complete, surface) }]
            : []),
          {
            key: 'signin-copy',
            label: 'Copy link',
            onPress: async () => {
              const copied = await gh.copy(a.verification_uri_complete, surface)
              await say(gh, copied ? 'Link copied.' : 'Copy the link above.')
            },
          },
          { key: 'signin-cancel', label: 'Cancel', onPress: () => cancel(gh) },
        ])}
      </Box>
    )
  }
  return (
    <Box flexDirection="column" gap="md">
      {k.Head('Sign in to Glyphh', 'With Google or GitHub, to see your account, your organisation, your plan and the apps published to it.')}
      {a.status === 'out' && a.error ? k.Note('signin-error', a.error, 'error') : null}
      {k.Buttons([{ key: 'signin', label: 'Sign in', primary: true, onPress: () => beginSignIn(gh, surface) }])}
    </Box>
  )
}
