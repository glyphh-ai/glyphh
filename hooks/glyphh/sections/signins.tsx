// Sign-ins: the providers linked, "Add <provider>" for the others, Remove
// while more than one is linked, and Refresh once linking finished.
import { PROVIDERS, addIdentity, linkedProviders, providerLabel, refreshIdentities, removeIdentity } from '../identities'
import type { Ctx } from '../ui'

export function SignIns(ctx: Ctx) {
  const { gh, me, surface } = ctx
  const { Box, Text, Button } = ctx.ui
  const linked = linkedProviders(me)
  const missing = PROVIDERS.filter(p => !linked.includes(p.id))
  return (
    <Box flexDirection="column">
      <Text bold>Sign-ins</Text>
      {linked.length === 0 && <Text dimColor>None listed.</Text>}
      {linked.map(p => (
        <Box key={`idp-row-${p}`} gap={1}>
          <Text>{providerLabel(p)}</Text>
          {linked.length > 1 && <Button key={`idp-remove-${p}`} plain label="Remove" onPress={() => removeIdentity(gh, p)} />}
        </Box>
      ))}
      <Box gap={1}>
        {missing.map(p => (
          <Button key={`idp-add-${p.id}`} label={`Add ${p.label}`} onPress={() => addIdentity(gh, p.id, surface)} />
        ))}
        <Button key="idp-refresh" plain label="Refresh" onPress={() => refreshIdentities(gh)} />
      </Box>
    </Box>
  )
}
