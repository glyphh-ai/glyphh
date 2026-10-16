// Plan: the current plan, its limits and what is used (/v1/me), the license
// this machine holds, and every plan (/v1/plans).

import type { Json } from '../../../types'
import { limitText, limitsOf, obj, planName, priceText, str, usedOf } from '../shape'
import type { Ctx } from '../ui'

const LIMIT_KEYS: [string, string][] = [
  ['members', 'max_members'],
  ['installs', 'max_installs'],
]

export function planLimits(plan: Json): string {
  const limits = { ...plan, ...obj(plan.limits) }
  return LIMIT_KEYS.map(([label, key]) => `${label} ${limitText(limits[key])}`).join(' · ')
}

export async function Plan(ctx: Ctx) {
  const { gh, me, lists } = ctx
  const { Box, Text } = ctx.ui
  const limits = limitsOf(me)
  const used = usedOf(me)
  const lic = await gh.state.license.get()
  const plans = lists.plans ?? []
  return (
    <Box flexDirection="column" gap={1}>
      <Text bold>Plan: {planName(me)}</Text>
      <Box flexDirection="column">
        {LIMIT_KEYS.map(([label, key]) => (
          <Text key={`use-${label}`}>
            {label}: {str(used[label], '0')} of {limitText(limits[key] ?? limits[label])}
          </Text>
        ))}
        {used.seats !== undefined && <Text>seats: {str(used.seats)}</Text>}
      </Box>
      <Text dimColor>
        {lic
          ? `License: ${lic.ok ? 'valid' : `not valid (${lic.error ?? 'unknown'})`}${lic.expires_at ? `, until ${lic.expires_at}` : ''}`
          : 'License: none yet.'}
      </Text>
      <Box flexDirection="column">
        <Text bold>Plans</Text>
        {plans.length === 0 && <Text dimColor>Loading plans…</Text>}
        {plans.map(p => (
          <Text key={`plan-${str(p.name)}`}>
            {str(p.name)} · {priceText(p)} · {planLimits(p)}
          </Text>
        ))}
      </Box>
    </Box>
  )
}
