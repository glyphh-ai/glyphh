// The Glyphh panel: the section tabs with who is signed in, the last word
// (what an action did, or why not), and the open section. Signed out, every
// section is the sign-in.
import type { AuthState, GlyphhNote, GlyphhSection } from '../../types'
import { openSection } from './actions'
import { Account } from './sections/account'
import { Apps } from './sections/apps'
import { Billing } from './sections/billing'
import { Org } from './sections/org'
import { Plan } from './sections/plan'
import { SignIn } from './sections/signin'
import { isAdmin, str, userOf } from './shape'
import { sectionFor, sectionsFor } from './state'
import { kit, linkOrText, type Ctx } from './ui'

async function sectionBody(ctx: Ctx, a: AuthState, open: GlyphhSection) {
  if (a.status !== 'in') return SignIn(ctx, a)
  switch (open) {
    case 'account': return Account(ctx, a)
    case 'org': return Org(ctx)
    case 'plan': return Plan(ctx)
    case 'billing': return Billing(ctx)
    case 'apps': return Apps(ctx)
  }
}

export async function Panel(ctx: Ctx, a: AuthState, asked: GlyphhSection, said: GlyphhNote | null) {
  const { gh } = ctx
  const { Box, Text } = ctx.ui
  const k = kit(ctx)
  const who = a.status === 'in' ? `Signed in${ctx.me ? ` as ${str(userOf(ctx.me).email)}` : ''}` : 'Signed out'
  // The admin runs the account, the org, the plan and billing; a member has Apps alone. Signed out, or before
  // /v1/me has answered who this is, every tab is drawn (the first section opened loads the account).
  const admin = a.status !== 'in' || ctx.me === null || isAdmin(ctx.me)
  const open = sectionFor(admin, asked)
  const body = await sectionBody(ctx, a, open)
  return (
    <Box flexDirection="column" gap="md" paddingX={1} paddingY="xs">
      <Box justifyContent="space-between" alignItems="center" gap={1}>
        {k.Tabs(sectionsFor(admin).map(s => ({ key: `sec-${s.id}`, label: s.label, active: s.id === open, onPress: () => openSection(gh, s.id) })))}
        <Text size="footnote" dimColor wrap="truncate-start">{who}</Text>
      </Box>
      {said && k.Note('note', said.text, said.isError ? 'error' : 'success', said.link ? linkOrText(ctx.ui, 'note-link', said.link) : null)}
      {body}
    </Box>
  )
}
