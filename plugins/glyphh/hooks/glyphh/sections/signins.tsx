// Sign-ins: the providers linked, "Add <provider>" for the others, Remove
// while more than one is linked, and Refresh once linking finished.
import { PROVIDERS, addIdentity, linkedProviders, providerLabel, refreshIdentities, removeIdentity } from '../identities'
import { kit, type Ctx } from '../ui'

export function SignIns(ctx: Ctx) {
  const { gh, me, surface } = ctx
  const { Box } = ctx.ui
  const k = kit(ctx)
  const linked = linkedProviders(me)
  const missing = PROVIDERS.filter(p => !linked.includes(p.id))
  return k.Group(
    'signins',
    'Sign-ins',
    <Box flexDirection="column" gap="xs">
      {linked.length === 0 && k.Empty('idp-none', 'None listed.')}
      {linked.map(p =>
        k.Row({
          key: `idp-row-${p}`,
          primary: providerLabel(p),
          secondary: 'Linked',
          actions: linked.length > 1 ? [{ key: `idp-remove-${p}`, label: 'Remove', onPress: () => removeIdentity(gh, p) }] : [],
        }),
      )}
      <Box gap={1}>
        {k.Buttons(missing.map(p => ({ key: `idp-add-${p.id}`, label: `Add ${p.label}`, onPress: () => addIdentity(gh, p.id, surface) })))}
        {k.Actions([{ key: 'idp-refresh', label: 'Refresh', onPress: () => refreshIdentities(gh) }])}
      </Box>
    </Box>,
  )
}
