// The Workspaces section: the name lives on the server (for the limit), the
// rest in ~/.glyphh/workspaces/<slug>.json. The server is asked first, so a
// workspace past the limit is never made.

import type { WorkspaceFile } from '../../types'
import { ApiError, api, listOf } from './api'
import { act, loadMe } from './account'
import { say, setList } from './state'
import { addEntry, deleteEntry, findEntry, patchEntry, renameEntry } from './wsfiles'
import { blankFile } from './wsmodel'
import type { Host } from './host'

const enc = encodeURIComponent

const reloadNames = async (gh: Host) => {
  await setList(gh, 'workspaces', listOf(await api(gh, 'GET', '/v1/workspaces'), 'workspaces'))
  await loadMe(gh).catch(() => undefined)
}

/** A name the server never had (a migrated layout) is not an error to drop. */
const unlessMissing = (err: unknown) => {
  if (!(err instanceof ApiError && err.status === 404)) throw err
}

export function createWorkspace(gh: Host, raw: string) {
  const name = raw.trim()
  if (!name) return say(gh, 'Give the workspace a name.', true)
  return act(gh, `Workspace "${name}" created.`, async () => {
    if (await findEntry(gh, name)) throw new Error(`A workspace "${name}" is already on this machine.`)
    await api(gh, 'POST', '/v1/workspaces', { name })
    try {
      await addEntry(gh, blankFile(name))
    } catch (err) {
      await api(gh, 'DELETE', `/v1/workspaces/${enc(name)}`).catch(() => undefined)
      throw err
    }
    await gh.state.selected.set(() => name)
    await reloadNames(gh)
  })
}

/** Registers a local-only workspace's name (subject to the limit). */
export const registerWorkspace = (gh: Host, name: string) =>
  act(gh, `"${name}" registered.`, async () => {
    await api(gh, 'POST', '/v1/workspaces', { name })
    await reloadNames(gh)
  })

export function renameWorkspace(gh: Host, from: string, raw: string) {
  const to = raw.trim()
  if (!to || to === from) return Promise.resolve()
  return act(gh, `Renamed to "${to}".`, async () => {
    if (await findEntry(gh, to)) throw new Error(`A workspace "${to}" is already on this machine.`)
    await api(gh, 'PATCH', `/v1/workspaces/${enc(from)}`, { name: to }).catch(unlessMissing)
    await renameEntry(gh, from, to)
    await gh.state.selected.set(() => to)
    await reloadNames(gh)
  })
}

export const deleteWorkspace = (gh: Host, name: string) =>
  act(gh, `Workspace "${name}" deleted.`, async () => {
    await api(gh, 'DELETE', `/v1/workspaces/${enc(name)}`).catch(unlessMissing)
    await deleteEntry(gh, name)
    await gh.state.selected.set(() => null)
    await reloadNames(gh)
  })

type Editable = 'model' | 'folder' | 'permission_mode' | 'effort'

/** A session setting kept in the workspace's file; blank clears it. */
export const setField = (gh: Host, name: string, field: Editable, raw: string) =>
  act(gh, `${name}: ${field.replace('_', ' ')} saved.`, async () => {
    const value = raw.trim() || null
    if (field === 'folder' && value && !value.startsWith('/')) throw new Error('The folder must be an absolute path.')
    await patchEntry(gh, name, (f): WorkspaceFile => ({ ...f, [field]: value }))
  })
