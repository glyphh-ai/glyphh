// Plan: the org's plan, what it uses of Ada Cloud this month (`cloud` on
// /v1/me: precedents held, reads, when the count starts again, reads past the
// month), the org's models by the Ada version they run with any deprecation
// (`cloud.ada`), and every plan by price with its cloud caps (/v1/plans).
// Members, installs and models are unlimited on every plan, so none is
// counted here.

import type { Json } from '../../../types'
import { adaLines } from '../ada'
import { cloudLimits, cloudOf, count, many, money, obj, planName, priceText, str } from '../shape'
import { kit, type Ctx } from '../ui'

/** The org's use of Ada Cloud: precedents held of the plan's, reads this
 *  month of the plan's (and those past it, metered at the plan's rate), and
 *  when the month's count starts again. No `cloud` yet: one line saying so. */
export function usageLines(me: Json | null, plan?: Json): string[] {
  const c = cloudOf(me)
  if (!Object.keys(c).length) return ['Ada Cloud usage: not available yet.']
  const held = obj(c.precedents)
  const reads = obj(c.requests)
  const models = typeof c.models === 'number' ? c.models : 0
  const rate = obj(plan?.cloud).overage_cents_per_10k
  const per = typeof rate === 'number' ? ` at ${money(rate)} per 10,000` : ''
  const over = typeof reads.over === 'number' && reads.over > 0 ? `; ${count(reads.over)} past it, metered${per}` : ''
  const of = (cap: Json) => `${count(cap.used ?? 0)}${cap.max == null ? ` (${many(cap.max)})` : ` of ${many(cap.max)}`}`
  return [
    `Precedents: ${of(held)}, in ${models} model${models === 1 ? '' : 's'}`,
    `Reads ${str(c.month, 'this month')}: ${of(reads)}${over}`,
    `The month's reads start again ${str(c.resets_at, 'next month')}.`,
  ]
}

export function Plan(ctx: Ctx) {
  const { me, lists } = ctx
  const { Box, Text } = ctx.ui
  const k = kit(ctx)
  const plans = lists.plans ?? []
  const name = str(cloudOf(me).plan ?? obj(me?.plan).name).toLowerCase()
  const current = plans.find(p => str(p.name).toLowerCase() === name) ?? obj(me?.plan)
  return (
    <Box flexDirection="column" gap="md">
      {k.Head(planName(me), 'Your organisation’s plan, what it uses of Ada Cloud this month, and the plans beside it.')}
      {k.Group(
        'usage',
        'This month',
        <Box flexDirection="column">
          {usageLines(me, current).map((line, i) => (
            <Text key={`use-${i}`}>{line}</Text>
          ))}
        </Box>,
      )}
      {k.Group(
        'ada',
        'Ada versions',
        <Box flexDirection="column">
          {adaLines(me).map((line, i) =>
            line.tone === 'dim' ? (
              <Text key={`ada-${i}`} dimColor>{line.text}</Text>
            ) : (
              <Text key={`ada-${i}`} color={line.tone}>{line.text}</Text>
            ),
          )}
        </Box>,
      )}
      {k.Group(
        'plans',
        'Plans',
        <Box flexDirection="column" gap="xs">
          {plans.length === 0 && k.Empty('plans-loading', 'Loading plans…')}
          {plans.map(p => {
            const mine = str(p.name).toLowerCase() === name
            return k.Row({
              key: `plan-${str(p.name)}`,
              primary: str(p.name),
              tone: mine ? 'claude' : undefined,
              chip: mine ? { text: 'Your plan', tone: 'claude' } : undefined,
              secondary: `${priceText(p)} · ${cloudLimits(p)}`,
            })
          })}
        </Box>,
        'Members, installs and models are unlimited on every plan.',
      )}
    </Box>
  )
}
