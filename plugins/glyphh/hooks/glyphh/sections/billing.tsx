// Billing (admin): checkout for Pro or Team, change plan once subscribed,
// Talk to us for Enterprise, and Stripe's portal for the card and invoices.
// Stripe's pages open in the browser pane. An Enterprise org's plan is set in
// its contract: it changes with Glyphh, not here.
import type { Json } from '../../../types'
import { changePlan, checkout, portal, talkToUs } from '../actions'
import { isAdmin, isSelfServe, isSubscribed, orgOf, planName, planOf, priceText, str } from '../shape'
import type { Ctx } from '../ui'

type Offer = { label: string; run: () => Promise<unknown> } | null

/** What a plan's row offers: Talk to us for Enterprise, Checkout for a paid
 *  plan before subscribing, switch once subscribed; nothing for the plan the
 *  org is on, or for Free before subscribing (it is Free already). */
function offer(ctx: Ctx, plan: Json, current: string, subscribed: boolean): Offer {
  const { gh, surface } = ctx
  const name = str(plan.name)
  if (name.toLowerCase() === current.toLowerCase()) return null
  if (!isSelfServe(plan)) return { label: 'Talk to us', run: () => talkToUs(gh, surface) }
  if (subscribed) return { label: 'switch', run: () => changePlan(gh, name, surface) }
  if (plan.price_cents === 0) return null
  return { label: 'checkout', run: () => checkout(gh, name, surface) }
}

function renewal(org: Json): string {
  if (org.plan_until) return ` · until ${str(org.plan_until)}`
  return org.renews_at ? ` · renews ${str(org.renews_at)}` : ''
}

export function Billing(ctx: Ctx) {
  const { gh, me, lists, surface } = ctx
  const { Box, Text, Button } = ctx.ui
  if (!isAdmin(me)) return <Text dimColor>Billing is the org admin's.</Text>
  const subscribed = isSubscribed(me)
  const org = orgOf(me)
  const current = planOf(me)
  const contract = !isSelfServe(current)
  const plans = lists.plans ?? []
  return (
    <Box flexDirection="column" gap={1}>
      <Text>
        {planName(me)}
        {org.billing_status && org.billing_status !== 'none' ? ` · ${str(org.billing_status)}` : ''}
        {renewal(org)}
      </Text>
      {contract ? (
        <Box gap={1}>
          <Text>Your plan is set in your contract. To change it, talk to us.</Text>
          <Button key="bill-talk" plain label="Talk to us" onPress={() => talkToUs(gh, surface)} />
        </Box>
      ) : (
        <Box flexDirection="column">
          <Text bold>{subscribed ? 'Change plan' : 'Subscribe'}</Text>
          {plans.map(p => {
            const name = str(p.name)
            const o = offer(ctx, p, str(current.name), subscribed)
            return (
              <Box key={`bill-row-${name}`} gap={1}>
                <Text>
                  {name} · {priceText(p)}
                  {name.toLowerCase() === str(current.name).toLowerCase() ? ' · your plan' : ''}
                </Text>
                {o && <Button key={`bill-plan-${name}`} plain label={o.label} onPress={o.run} />}
              </Box>
            )
          })}
        </Box>
      )}
      <Box>
        <Button key="bill-portal" label="Card and invoices" onPress={() => portal(gh, surface)} />
      </Box>
    </Box>
  )
}
