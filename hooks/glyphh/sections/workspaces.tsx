// Workspaces: list, create (the server first: refused past the limit), and
// for the one picked, rename, model, folder, permission mode, effort, delete.

import type { WorkspaceFile } from '../../../types'
import { limitText, limitsOf, str, usedOf } from '../shape'
import type { Ctx } from '../ui'
import { createWorkspace, deleteWorkspace, registerWorkspace, renameWorkspace, setField } from '../wsactions'
import { readAll } from '../wsfiles'
import { EFFORTS, PERMISSION_MODES } from '../wsmodel'

const options = (values: readonly string[]) => [{ value: '', label: '(session default)' }, ...values.map(value => ({ value }))]

function Editor(ctx: Ctx, file: WorkspaceFile) {
  const { gh } = ctx
  const { Box, Button, Input, Select } = ctx.ui
  const name = file.name
  return (
    <Box flexDirection="column" borderStyle="single" paddingX={1}>
      <Input key="ws-rename" label="Name " value={name} submitLabel="rename" onSubmit={v => renameWorkspace(gh, name, v)} />
      <Input key="ws-model" label="Model " value={file.model ?? ''} placeholder="session default" onSubmit={v => setField(gh, name, 'model', v)} />
      <Input key="ws-folder" label="Folder " value={file.folder ?? ''} placeholder="/absolute/path" onSubmit={v => setField(gh, name, 'folder', v)} />
      <Select
        key="ws-permission"
        label="Permission mode "
        options={options(PERMISSION_MODES)}
        value={file.permission_mode ?? ''}
        onSelect={v => setField(gh, name, 'permission_mode', v)}
      />
      <Select key="ws-effort" label="Effort " options={options(EFFORTS)} value={file.effort ?? ''} onSelect={v => setField(gh, name, 'effort', v)} />
      <Box>
        <Button key="ws-delete" label="Delete workspace" onPress={() => deleteWorkspace(gh, name)} />
      </Box>
    </Box>
  )
}

export async function Workspaces(ctx: Ctx) {
  const { gh, me, lists } = ctx
  const { Box, Text, Button, Input } = ctx.ui
  const entries = (await readAll(gh)) ?? []
  const onServer = new Set((lists.workspaces ?? []).map(w => str(w.name ?? w)))
  const pick = await gh.state.selected.get()
  const current = entries.find(e => e.file.name === pick)
  const max = limitsOf(me).max_workspaces ?? limitsOf(me).workspaces
  return (
    <Box flexDirection="column" gap={1}>
      <Text>
        {str(usedOf(me).workspaces, String(onServer.size))} of {limitText(max)} workspaces
      </Text>
      <Box flexDirection="column">
        {entries.length === 0 && <Text dimColor>No workspaces on this machine.</Text>}
        {entries.map(({ slug, file }) => (
          <Box key={`ws-row-${slug}`} gap={1}>
            <Button key={`ws-pick-${slug}`} plain label={`${file.name === pick ? '›' : ' '} ${file.name}`} onPress={() => gh.state.selected.set(() => file.name)} />
            {!onServer.has(file.name) && <Text dimColor>local only</Text>}
            {!onServer.has(file.name) && (
              <Button key={`ws-register-${slug}`} plain label="register" onPress={() => registerWorkspace(gh, file.name)} />
            )}
          </Box>
        ))}
      </Box>
      {current && Editor(ctx, current.file)}
      <Input key="ws-new" label="New workspace " placeholder="name" submitLabel="create" onSubmit={v => createWorkspace(gh, v)} />
    </Box>
  )
}
