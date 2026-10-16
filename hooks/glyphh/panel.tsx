// The Glyphh panel: section tabs, the last word (what an action did, or why
// not), and the open section. Signed out, every section is the sign-in.
import type { AuthState, GlyphhNote, GlyphhSection } from '../../types'
import { openSection } from './actions'
import { Account } from './sections/account'
import { Billing } from './sections/billing'
import { Org } from './sections/org'
import { Plan } from './sections/plan'
import { SignIn } from './sections/signin'
import { str, userOf } from './shape'
import { SECTIONS } from './state'
import { linkOrText, type Ctx } from './ui'

async function sectionBody(ctx: Ctx, a: AuthState, open: GlyphhSection) {
  if (a.status !== 'in') return SignIn(ctx, a)
  switch (open) {
    case 'account': return Account(ctx, a)
    case 'org': return Org(ctx)
    case 'plan': return Plan(ctx)
    case 'billing': return Billing(ctx)
  }
}

export async function Panel(ctx: Ctx, a: AuthState, open: GlyphhSection, said: GlyphhNote | null) {
  const { gh } = ctx
  const { Box, Text, Button } = ctx.ui
  const who = a.status === 'in' ? `Signed in${ctx.me ? ` as ${str(userOf(ctx.me).email)}` : ''}` : 'Signed out'
  const body = await sectionBody(ctx, a, open)
  return (
    <Box flexDirection="column" gap={1}>
      <Box gap={1}>
        {SECTIONS.map(s => (
          <Button
            key={`sec-${s.id}`}
            label={s.label}
            variant={s.id === open ? 'primary' : 'secondary'}
            onPress={() => openSection(gh, s.id)}
          />
        ))}
        <Text dimColor>{who}</Text>
      </Box>
      {said && (
        <Box gap={1}>
          <Text color={said.isError ? 'error' : 'success'}>{said.text}</Text>
          {said.link && linkOrText(ctx.ui, 'note-link', said.link)}
        </Box>
      )}
      {body}
    </Box>
  )
}
