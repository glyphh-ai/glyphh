// /dip's reading of what was typed: a workspace by its number in the list,
// its name, or the start of its name.
import type { Entry } from '../../types'

export function findWorkspace(all: Entry[], want: string): Entry | undefined {
  const n = Number(want)
  if (Number.isInteger(n) && n >= 1) return all[n - 1]
  const w = want.toLowerCase()
  return all.find(e => e.file.name.toLowerCase() === w) ?? all.find(e => e.file.name.toLowerCase().startsWith(w))
}

export const listText = (all: Entry[]) => all.map((e, i) => `${i + 1} ${e.file.name}`).join(' · ')
