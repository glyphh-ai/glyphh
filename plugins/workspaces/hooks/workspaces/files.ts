// ~/.glyphh: one file per workspace in workspaces/<slug>.json, kept in the
// order the store remembers (new ones last), and the favourites they show in
// favorites.json. The mod reads them (and writes the first run's and an
// earlier version's); the layout page's editor writes the rest
// (helper/viewer.mjs). Works on a Disk, closures over `$` from ./hooks.tsx.
import type { Entry, Favorite, WorkspaceFile } from '../../types'
import { DEFAULT_FAVORITES, DEFAULT_WORKSPACES } from './defaults.ts'
import { normalise, slugOf, type TabToFavorite } from './model.ts'

export type Disk = {
  home(): Promise<string | undefined>
  read(path: string): Promise<string>
  write(path: string, text: string): Promise<void>
  exists(path: string): Promise<boolean>
  /** The names of the files in a folder. */
  list(dir: string): Promise<string[]>
  /** Moves a file into place in one step. */
  rename(from: string, to: string): Promise<void>
  order: { get(): Promise<string[]>; set(slugs: string[]): Promise<void> }
}

export type Library = { entries: Entry[]; favorites: Favorite[] }

async function rootOf(disk: Disk): Promise<string> {
  const home = await disk.home()
  if (!home) throw new Error('HOME is not set: there is nowhere to keep workspaces.')
  return `${home.replace(/\/$/, '')}/.glyphh`
}

const dirOf = async (disk: Disk) => `${await rootOf(disk)}/workspaces`
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`

async function readJson(disk: Disk, path: string): Promise<unknown> {
  try {
    return JSON.parse(await disk.read(path))
  } catch {
    return undefined
  }
}

/** A text written whole or not at all: to a temporary name, then moved. */
async function writeAtomic(disk: Disk, path: string, text: string): Promise<void> {
  await disk.write(`${path}.tmp`, text)
  await disk.rename(`${path}.tmp`, path)
}

/** The favourites file's list; null when there is no file yet. */
async function readFavorites(disk: Disk): Promise<Favorite[] | null> {
  const path = `${await rootOf(disk)}/favorites.json`
  if (!(await disk.exists(path))) return null
  const raw = (await readJson(disk, path)) as { favorites?: unknown } | undefined
  const list = Array.isArray(raw?.favorites) ? raw.favorites : []
  const seen = new Set<string>()
  return list.flatMap((f: unknown) => {
    const { id, name, url, keep_in_panel } = (f ?? {}) as Record<string, unknown>
    if (typeof id !== 'string' || typeof name !== 'string' || typeof url !== 'string' || seen.has(id)) return []
    seen.add(id)
    return [{ id, name, url, keep_in_panel: keep_in_panel === true }]
  })
}

async function writeFavorites(disk: Disk, favorites: Favorite[]): Promise<void> {
  await writeAtomic(disk, `${await rootOf(disk)}/favorites.json`, json({ favorites }))
}

/** An id for a new favourite: from its name, unlike any other, never changed. */
export function freeId(name: string, favorites: Favorite[]): string {
  const base = slugOf(name) === 'workspace' ? 'page' : slugOf(name)
  let id = base
  for (let i = 2; favorites.some(f => f.id === id); i++) id = `${base}-${i}`
  return id
}

async function writeEntry(disk: Disk, slug: string, file: WorkspaceFile): Promise<void> {
  await writeAtomic(disk, `${await dirOf(disk)}/${slug}.json`, json(file))
}

/** Everything in ~/.glyphh, read. A first run (no workspaces folder) writes
 *  the built-in workspaces and favourites; a folder emptied on purpose stays
 *  empty. An earlier version's pages become favourites (one per address)
 *  and its files are written again, pointing at them. */
export async function load(disk: Disk): Promise<Library> {
  const dir = await dirOf(disk)
  const isFresh = !(await disk.exists(dir))
  if (isFresh) {
    for (const file of DEFAULT_WORKSPACES) await writeEntry(disk, slugOf(file.name), file)
    await disk.order.set(DEFAULT_WORKSPACES.map(f => slugOf(f.name)))
  }
  const kept = await readFavorites(disk)
  const favorites = kept ?? (isFresh ? [...DEFAULT_FAVORITES] : [])
  let added = kept === null
  const toFavorite: TabToFavorite = tab => {
    const same = favorites.find(f => f.url === tab.url)
    if (same) return same.id
    const id = freeId(tab.name, favorites)
    favorites.push({ id, name: tab.name, url: tab.url, keep_in_panel: false })
    added = true
    return id
  }
  const entries: Entry[] = []
  for (const name of (await disk.list(dir)).filter(n => n.endsWith('.json')).sort()) {
    const read = normalise(await readJson(disk, `${dir}/${name}`), toFavorite)
    if (!read) continue
    const slug = name.slice(0, -'.json'.length)
    if (read.isLegacy) await writeEntry(disk, slug, read.file)
    entries.push({ slug, file: read.file })
  }
  if (added) await writeFavorites(disk, favorites)
  const order = await disk.order.get()
  const rank = (slug: string) => (order.includes(slug) ? order.indexOf(slug) : order.length)
  return { entries: entries.sort((a, b) => rank(a.slug) - rank(b.slug)), favorites }
}

/** One workspace's file changed by `fn`, under the same slug. */
export async function patchWorkspace(disk: Disk, name: string, fn: (f: WorkspaceFile) => WorkspaceFile): Promise<void> {
  const entry = (await load(disk)).entries.find(e => e.file.name === name)
  if (!entry) throw new Error(`There is no workspace "${name}".`)
  await writeEntry(disk, entry.slug, fn(entry.file))
}
