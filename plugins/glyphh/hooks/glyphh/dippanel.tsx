// The Dip pane: the layouts, each a press away (/dip <name> does the same),
// and the editor a layout is written in (its folder, browser tabs, panes,
// terminal tabs and the brief Claude reads while it is active).
import type { RenderSurface } from 'claude-code'

import type { DipDraft, DipView } from '../../types'
import { closeDraft, dip, draftFromNow, editDraft, openDraft, PANES, removeLayout, saveDraft } from './dip'
import type { Host } from './host'
import { kit, type Ui } from './ui'

type DipCtx = { gh: Host; ui: Ui; surface: RenderSurface }

function Editor(ctx: DipCtx, d: DipDraft) {
  const { gh } = ctx
  const { Box, Text, Input, Button } = ctx.ui
  const k = kit(ctx)
  const field = (key: keyof Pick<DipDraft, 'name' | 'folder' | 'tabs' | 'terminals' | 'brief'>, label: string, placeholder: string, rows = 1) => (
    <Box key={`f-${key}`} flexDirection="column">
      <Text size="footnote" dimColor>{label}</Text>
      <Input
        key={`dip-${key}`}
        value={d[key]}
        placeholder={placeholder}
        rows={rows > 1 ? rows : undefined}
        submitLabel="save"
        onInput={v => void editDraft(gh, x => ({ ...x, [key]: v }))}
        onSubmit={v => void editDraft(gh, x => ({ ...x, [key]: v })).then(() => saveDraft(gh))}
      />
    </Box>
  )
  return k.Card(
    'editor',
    <Box flexDirection="column" gap="sm" paddingY="xs">
      <Text weight="semibold">{d.original ? `Edit ${d.original}` : 'New layout'}</Text>
      {field('name', 'Name', 'api')}
      {field('folder', "Claude's folder", '/Users/you/code/api')}
      {field('tabs', 'Browser tabs, one a line; * before the one in front', '* localhost:3000\ngithub.com/you/api/pulls', 4)}
      <Box flexDirection="column">
        <Text size="footnote" dimColor>Panes</Text>
        <Box gap={1} flexWrap="wrap">
          {PANES.map(p => {
            const on = d.panes.includes(p.id)
            return (
              <Button key={`pane-${p.id}`} plain label={p.label} onPress={() => editDraft(gh, x => ({ ...x, panes: on ? x.panes.filter(q => q !== p.id) : [...x.panes, p.id] }))}>
                <Text weight={on ? 'semibold' : 'regular'} color={on ? 'claude' : undefined} dimColor={!on}>{on ? `● ${p.label}` : `○ ${p.label}`}</Text>
              </Button>
            )
          })}
        </Box>
      </Box>
      {field('terminals', 'Terminal tabs, one a line: title | folder | command', 'dev | ~/code/api | npm run dev', 3)}
      {field('brief', 'Brief for Claude while this is active', 'The API service; tests with make test; deploys from main.', 3)}
      {k.Buttons([
        { key: 'save', label: 'Save', primary: true, onPress: () => saveDraft(gh) },
        { key: 'cancel', label: 'Cancel', onPress: () => closeDraft(gh) },
      ])}
    </Box>,
  )
}

export function DipPanel(ctx: DipCtx, view: DipView) {
  const { gh } = ctx
  const { Box } = ctx.ui
  const k = kit(ctx)
  const rows = view.layouts.map(l => {
    const bits = [l.folder ? l.folder.replace(/^\/Users\/[^/]+/, '~') : '', l.tabs.length ? `${l.tabs.length} tab${l.tabs.length > 1 ? 's' : ''}` : '', l.terminals.length ? `${l.terminals.length} terminal${l.terminals.length > 1 ? 's' : ''}` : '']
    return k.Row({
      key: `l-${l.name}`,
      primary: l.name,
      tone: l.name === view.active ? 'claude' : undefined,
      chip: l.name === view.active ? { text: 'active', tone: 'claude' } : undefined,
      secondary: bits.filter(Boolean).join(' · ') || 'empty',
      actions: [
        { key: `dip-${l.name}`, label: 'Dip', primary: true, onPress: () => dip(gh, l.name) },
        { key: `edit-${l.name}`, label: 'Edit', onPress: () => openDraft(gh, l.name) },
        { key: `rm-${l.name}`, label: 'Remove', onPress: () => removeLayout(gh, l.name) },
      ],
    })
  })
  return (
    <Box flexDirection="column" gap="md" paddingX={1} paddingY="xs">
      {k.Head('Dip', 'Workspaces: a folder, browser tabs, panes and terminals. /dip <name> bounces to one.')}
      {view.note && k.Note('note', view.note.text, view.note.isError ? 'error' : 'success')}
      {view.draft
        ? Editor(ctx, view.draft)
        : k.Group('layouts', 'Layouts', rows.length ? rows : k.Empty('none', 'No layouts yet.'))}
      {view.draft
        ? null
        : k.Buttons([
            { key: 'new', label: 'New layout', primary: true, onPress: () => openDraft(gh, null) },
            { key: 'now', label: 'From this workspace', onPress: () => draftFromNow(gh) },
          ])}
    </Box>
  )
}
