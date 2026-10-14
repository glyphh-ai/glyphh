// ~/.glyphh/workspaces/<slug>.json: read, written, migrated, and mirrored
// into the session's layouts so /dip, /stream and the grid draw from them.

import type { Layout, WorkspaceFile } from '../../types'
import { glyphhPath, readJson, removeFile, writeJson } from './home'
import { fileFromLayout, layoutFromFile, slugOf } from './wsmodel'
import type { Host } from './host'

const ORDER_KEY = 'workspaceOrder'

export type Entry = { slug: string; file: WorkspaceFile }

/** Every workspace file, in the kept order (new ones last); undefined when
 *  the folder cannot be read at all (no HOME, a sandbox). */
export async function readAll(gh: Host): Promise<Entry[] | undefined> {
  const dir = await glyphhPath(gh, 'workspaces')
  if (!dir) return undefined
  if (!(await gh.fs.exists(dir).catch(() => false))) return []
  const names = (await gh.fs.list(dir).catch(() => [])).filter(e => e.kind === 'file' && e.name.endsWith('.json'))
  const entries: Entry[] = []
  for (const { name } of names) {
    const file = await readJson<WorkspaceFile>(`${dir}/${name}`, gh)
    if (file && typeof file.name === 'string') entries.push({ slug: name.slice(0, -5), file })
  }
  const order = ((await gh.store.get(ORDER_KEY).catch(() => undefined)) ?? []) as string[]
  const rank = (slug: string) => (order.includes(slug) ? order.indexOf(slug) : order.length)
  return entries.sort((a, b) => rank(a.slug) - rank(b.slug) || a.slug.localeCompare(b.slug))
}

export async function writeEntry(gh: Host, slug: string, file: WorkspaceFile) {
  const path = await glyphhPath(gh, `workspaces/${slug}.json`)
  if (!path) throw new Error('HOME is not set: nowhere to keep workspaces')
  await writeJson(gh, path, file)
}

async function setOrder(gh: Host, slugs: string[]) {
  await gh.store.set(ORDER_KEY, slugs).catch(() => undefined)
}

/** The session's layouts from the files (what the grid and /dip use). */
export async function syncLayouts(gh: Host, entries: Entry[]) {
  if (entries.length === 0) return
  const all = entries.map(e => layoutFromFile(e.file))
  await gh.state.layouts.set(() => all)
  const now = await gh.state.active.get()
  if (!all.some(l => l.name === now)) await gh.state.active.set(() => all[0]!.name)
}

/** First run (no workspaces folder yet): the built-in layouts and their
 *  saved sizes become files. A folder emptied on purpose stays empty. */
export async function migrateAndLoad(gh: Host): Promise<Entry[] | undefined> {
  const dir = await glyphhPath(gh, 'workspaces')
  const isFresh = dir !== undefined && !(await gh.fs.exists(dir).catch(() => true))
  let entries = await readAll(gh)
  if (entries === undefined) return undefined
  if (isFresh) {
    const current = await gh.state.layouts.get()
    entries = current.map(l => ({ slug: slugOf(l.name), file: fileFromLayout(l) }))
    for (const e of entries) await writeEntry(gh, e.slug, e.file)
    await setOrder(gh, entries.map(e => e.slug))
  }
  await syncLayouts(gh, entries)
  return entries
}

export async function findEntry(gh: Host, name: string): Promise<Entry | undefined> {
  return (await readAll(gh))?.find(e => e.file.name === name)
}

/** One workspace's file changed by `fn`, the layouts following. */
export async function patchEntry(gh: Host, name: string, fn: (f: WorkspaceFile) => WorkspaceFile) {
  const entry = await findEntry(gh, name)
  if (!entry) throw new Error(`No workspace file for "${name}"`)
  await writeEntry(gh, entry.slug, fn(entry.file))
  await syncLayouts(gh, (await readAll(gh)) ?? [])
}

const same = (a: number[], b: number[]) => a.length === b.length && a.every((v, i) => Math.abs(v - (b[i] ?? 0)) < 1e-9)

/** Dragged sizes kept in each workspace's file whose sizes changed (quietly:
 *  where ~/.glyphh cannot be written, the store still holds them). */
export async function saveSizes(gh: Host, all: Layout[]) {
  for (const entry of (await readAll(gh).catch(() => undefined)) ?? []) {
    const l = all.find(x => x.name === entry.file.name)
    if (!l || (same(l.colWidths, entry.file.col_widths) && same(l.rowHeights, entry.file.row_heights))) continue
    await writeEntry(gh, entry.slug, { ...entry.file, col_widths: [...l.colWidths], row_heights: [...l.rowHeights] }).catch(() => undefined)
  }
}

export async function addEntry(gh: Host, file: WorkspaceFile) {
  const taken = new Set(((await readAll(gh)) ?? []).map(e => e.slug))
  let slug = slugOf(file.name)
  for (let i = 2; taken.has(slug); i++) slug = `${slugOf(file.name)}-${i}`
  await writeEntry(gh, slug, file)
  const order = ((await gh.store.get(ORDER_KEY).catch(() => undefined)) ?? [...taken]) as string[]
  await setOrder(gh, [...order.filter(s => s !== slug), slug])
  await syncLayouts(gh, (await readAll(gh)) ?? [])
}

export async function renameEntry(gh: Host, from: string, to: string) {
  const entry = await findEntry(gh, from)
  if (!entry) return
  const path = await glyphhPath(gh, `workspaces/${entry.slug}.json`)
  if (path) await removeFile(gh, path)
  const order = ((await gh.store.get(ORDER_KEY).catch(() => undefined)) ?? []) as string[]
  const slug = slugOf(to)
  await writeEntry(gh, slug, { ...entry.file, name: to })
  await setOrder(gh, order.map(s => (s === entry.slug ? slug : s)))
  await syncLayouts(gh, (await readAll(gh)) ?? [])
  if ((await gh.state.active.get()) === from) await gh.state.active.set(() => to)
  if ((await gh.state.previous.get()) === from) await gh.state.previous.set(() => to)
}

export async function deleteEntry(gh: Host, name: string) {
  const entry = await findEntry(gh, name)
  if (!entry) return
  const path = await glyphhPath(gh, `workspaces/${entry.slug}.json`)
  if (path) await removeFile(gh, path)
  const rest = (await readAll(gh)) ?? []
  await syncLayouts(gh, rest)
  if (rest.length === 0) await gh.state.layouts.set(() => [])
}
