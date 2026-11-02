// Billing (admin): checkout for Pro or Team, change plan once subscribed,
// Talk to us for Enterprise, and Stripe's portal for the card and invoices.
// Stripe's pages open in the browser pane. An Enterprise org's plan is set in
// its contract: it changes with Glyphh, not here.
import type { Json } from '../../../types'
import { changePlan, checkout, portal, talkToUs } from '../actions'
import { isAdmin, isSelfServe, isSubscribed, orgOf, planName, planOf, priceText, str } from '../shape'
import { day, kit, type Ctx } from '../ui'

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
  if (org.plan_until) return `Until ${day(org.plan_until)}`
  return org.renews_at ? `Renews ${day(org.renews_at)}` : ''
}

export function Billing(ctx: Ctx) {
  const { gh, me, lists, surface } = ctx
  const { Box } = ctx.ui
  const k = kit(ctx)
  if (!isAdmin(me)) {
    return (
      <Box flexDirection="column" gap="md">
        {k.Head('Billing', 'Billing is the organisation admin’s.')}
      </Box>
    )
  }
  const subscribed = isSubscribed(me)
  const org = orgOf(me)
  const current = planOf(me)
  const contract = !isSelfServe(current)
  const plans = lists.plans ?? []
  const status = org.billing_status && org.billing_status !== 'none' ? str(org.billing_status) : ''
  const standing = [status, renewal(org)].filter(Boolean).join(' · ')
  return (
    <Box flexDirection="column" gap="md">
      {k.Head('Billing', 'Your organisation’s subscription, its card and its invoices.')}
      {k.Field('bill-plan', 'Plan', planName(me), 'claude')}
      {standing ? k.Field('bill-standing', 'Standing', standing) : null}
      {contract
        ? k.Group(
            'contract',
            'Your plan',
            k.Row({
              key: 'bill-contract',
              primary: 'Your plan is set in your contract.',
              secondary: 'To change it, talk to us.',
              actions: [{ key: 'bill-talk', label: 'Talk to us', onPress: () => talkToUs(gh, surface) }],
            }),
          )
        : k.Group(
            'subscribe',
            subscribed ? 'Change plan' : 'Subscribe',
            <Box flexDirection="column" gap="xs">
              {plans.map(p => {
                const name = str(p.name)
                const mine = name.toLowerCase() === str(current.name).toLowerCase()
                const o = offer(ctx, p, str(current.name), subscribed)
                return k.Row({
                  key: `bill-row-${name}`,
                  primary: name,
                  tone: mine ? 'claude' : undefined,
                  chip: mine ? { text: 'Your plan', tone: 'claude' } : undefined,
                  secondary: priceText(p),
                  actions: o ? [{ key: `bill-plan-${name}`, label: o.label, onPress: o.run }] : [],
                })
              })}
            </Box>,
          )}
      {k.Buttons([{ key: 'bill-portal', label: 'Card and invoices', onPress: () => portal(gh, surface) }])}
    </Box>
  )
}
