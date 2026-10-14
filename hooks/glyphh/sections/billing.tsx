// Billing (admin): checkout or change plan, seats, and Stripe's portal for
// the card and invoices. Stripe's pages open in the browser pane.
import { changePlan, changeSeats, checkout, portal } from '../actions'
import { isAdmin, isSubscribed, orgOf, planName, priceText, str, usedOf } from '../shape'
import type { Ctx } from '../ui'

export function Billing(ctx: Ctx) {
  const { gh, me, lists, surface } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  if (!isAdmin(me)) return <Text dimColor>Billing is the org admin's.</Text>
  const subscribed = isSubscribed(me)
  const org = orgOf(me)
  const seats = Number(org.seats ?? usedOf(me).seats ?? 1) || 1
  const plans = lists.plans ?? []
  return (
    <Box flexDirection="column" gap={1}>
      <Text>
        {planName(me)} · {seats} seat{seats === 1 ? '' : 's'}
        {org.billing_status ? ` · ${str(org.billing_status)}` : ''}
      </Text>
      <Box flexDirection="column">
        <Text bold>{subscribed ? 'Change plan' : 'Subscribe'}</Text>
        {plans.map(p => {
          const name = str(p.name)
          return (
            <Box key={`bill-row-${name}`} gap={1}>
              <Text>{name} · {priceText(p)}</Text>
              <Button
                key={`bill-plan-${name}`}
                plain
                label={subscribed ? 'switch' : 'checkout'}
                onPress={() => (subscribed ? changePlan(gh, name, surface) : checkout(gh, name, seats, surface))}
              />
            </Box>
          )
        })}
      </Box>
      {subscribed && <Input key="bill-seats" label="Seats " value={String(seats)} submitLabel="set" onSubmit={v => changeSeats(gh, v)} />}
      <Box>
        <Button key="bill-portal" label="Card and invoices" onPress={() => portal(gh, surface)} />
      </Box>
    </Box>
  )
}
