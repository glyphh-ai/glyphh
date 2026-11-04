// The Dip pane: the layouts, each a press away (/dip <name> does the same),
// and the editor a layout is written in (its folder, the grid of Claude and
// its panes, browser tabs, terminal tabs and the brief Claude reads while it
// is active), with one Save and one Cancel.
import type { RenderSurface } from 'claude-code'

import type { DipCellPane, DipDraft, DipView } from '../../types'
import { closeDraft, dip, draftFromNow, editDraft, FILLS, openDraft, PANES, removeLayout, saveDraft } from './dip'
import { assign, canMergeDown, canMergeRight, canSplit, type Cut, cuts, MAX_GRID, merge, peels, resizeGrid, splitCell } from './dipgrid'
import type { Host } from './host'
import { kit, type Ui } from './ui'

type DipCtx = { gh: Host; ui: Ui; surface: RenderSurface }

/** How tall one grid row is drawn. */
const ROW = 4
const SIZES = Array.from({ length: MAX_GRID }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }))

const fillLabel = (pane: DipCellPane) => FILLS.find(f => f.id === pane)?.label ?? 'Empty'

/** The layout's grid: each cell a press that selects it, then what fills it and how it merges. */
function GridEditor(ctx: DipCtx, d: DipDraft) {
  const { gh } = ctx
  const { Box, Text, Button, Select } = ctx.ui
  const k = kit(ctx)
  const { grid, cell } = d
  const pick = (next: Pick<DipDraft, 'grid' | 'cell'>) => editDraft(gh, x => ({ ...x, ...next }))
  const size = (cols: number, rows: number) => pick({ grid: resizeGrid(grid, cols, rows), cell: 0 })

  const draw = (cut: Cut, key: string): ReturnType<Ui['Box']> => {
    if ('cell' in cut) {
      const at = cut.cell
      const on = at === cell
      return (
        <Box key={key} height={cut.rows * ROW} flexGrow={1} borderStyle="round" borderColor={on ? 'claude' : undefined} borderDimColor={!on} alignItems="center" justifyContent="center">
          <Button key={`cell-${at}`} label={fillLabel(grid.cells[at]?.pane ?? '')} variant={on ? 'primary' : 'secondary'} onPress={() => pick({ grid, cell: at })} />
        </Box>
      )
    }
    return (
      <Box key={key} flexDirection={cut.across ? 'row' : 'column'} flexGrow={1}>
        {cut.parts.map((p, i) => (
          // A whole percentage (a Box refuses 33.33…%, and the pane with it); the growing takes up what it drops.
          <Box key={`${key}-${i}`} flexDirection="column" width={cut.across ? `${Math.floor(p.share * 100)}%` : undefined} flexGrow={cut.across ? 1 : undefined}>
            {draw(p.cut, `${key}-${i}c`)}
          </Box>
        ))}
      </Box>
    )
  }
  const shape = cuts(grid)

  const moves = [
    canMergeRight(grid, cell) && { key: 'merge-right', label: 'Merge →', onPress: () => pick(merge(grid, cell, true)) },
    canMergeDown(grid, cell) && { key: 'merge-down', label: 'Merge ↓', onPress: () => pick(merge(grid, cell, false)) },
    canSplit(grid, cell) && { key: 'split', label: 'Split', onPress: () => pick({ grid: splitCell(grid, cell), cell }) },
  ].filter(m => !!m)

  return (
    <Box key="grid" flexDirection="column" gap="xs">
      <Text size="footnote" dimColor>Layout: press a cell, then choose what fills it</Text>
      {peels(grid, PANES.map(p => p.id)) ? null : <Text size="footnote" color="warning">A dip can't build this shape: some tile has to reach an edge of the rest (a plain 2 × 2 has none). Merge cells to fix it.</Text>}
      <Box gap={1} alignItems="center">
        <Select key="dip-cols" label="Columns" value={String(grid.cols)} options={SIZES} onSelect={v => size(Number(v), grid.rows)} />
        <Select key="dip-rows" label="Rows" value={String(grid.rows)} options={SIZES} onSelect={v => size(grid.cols, Number(v))} />
        {moves.length ? k.Actions(moves) : null}
      </Box>
      {shape ? draw(shape, 'g') : null}
      <Box gap={1} flexWrap="wrap">
        {FILLS.map(f => (
          <Button
            key={`fill-${f.id || 'empty'}`}
            label={f.label}
            variant={grid.cells[cell]?.pane === f.id ? 'primary' : 'secondary'}
            onPress={() => pick({ grid: assign(grid, cell, f.id), cell })}
          />
        ))}
      </Box>
    </Box>
  )
}

function Editor(ctx: DipCtx, d: DipDraft) {
  const { gh } = ctx
  const { Box, Text, Input } = ctx.ui
  const k = kit(ctx)
  const field = (key: keyof Pick<DipDraft, 'name' | 'folder' | 'tabs' | 'terminals' | 'brief'>, label: string, placeholder: string, rows = 1) => (
    <Box key={`f-${key}`} flexDirection="column">
      <Text size="footnote" dimColor>{label}</Text>
      <Input
        key={`dip-${key}`}
        value={d[key]}
        placeholder={placeholder}
        rows={rows > 1 ? rows : undefined}
        submitLabel=""
        onInput={v => void editDraft(gh, x => ({ ...x, [key]: v }))}
        onSubmit={v => void editDraft(gh, x => ({ ...x, [key]: v }))}
      />
    </Box>
  )
  return k.Card(
    'editor',
    <Box flexDirection="column" gap="sm" paddingY="xs">
      <Text weight="semibold">{d.original ? `Edit ${d.original}` : 'New layout'}</Text>
      {field('name', 'Name', 'api')}
      {field('folder', "Claude's folder", '/Users/you/code/api')}
      {GridEditor(ctx, d)}
      {field('tabs', 'Browser tabs, one a line; * before the one in front', '* localhost:3000\ngithub.com/you/api/pulls', 4)}
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
