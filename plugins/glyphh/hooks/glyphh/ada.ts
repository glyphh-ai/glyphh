// Ada versions (contract 5), as the panel shows them: the org's models by the
// Ada version they run, which version is the latest stable, and any
// deprecation. Read from /v1/me's `cloud.ada`, the shape of the Ada host's
// GET /v1/ada: {latest_stable, contract, versions: [{name, status, beta, open,
// released, deprecated, ends, changes_answers, models, ...}]}.
import type { Json } from '../../types'
import { cloudOf, count, obj, str } from './shape'

/** The contract (glyphh-ai/glyphh contract/contract.json) this plugin speaks.
 *  A server that speaks a newer one is said plainly, never read half-known. */
export const ADA_CONTRACT = 5

/** /v1/me's `cloud.ada`, or {} while the server has none. */
export const adaOf = (me: Json | null): Json => obj(cloudOf(me).ada)

/** The server speaks a newer contract than this plugin: the line that says
 *  so and how to update, else undefined. */
export function tooNew(contract: unknown): string | undefined {
  const n = typeof contract === 'string' ? Number(contract) : contract
  if (typeof n !== 'number' || !Number.isInteger(n) || n <= ADA_CONTRACT) return undefined
  return `Ada Cloud speaks contract ${n}; this plugin speaks contract ${ADA_CONTRACT}. Update it: /plugin update glyphh@glyphh, then reload.`
}

const models = (n: unknown) => {
  const k = typeof n === 'number' ? n : 0
  return `${count(k)} model${k === 1 ? '' : 's'}`
}

function statusText(v: Json, latest: string): string {
  const name = str(v.name)
  switch (str(v.status)) {
    case 'stable':
      return name === latest ? 'Stable, the default' : 'Stable'
    case 'beta':
      return v.open === false ? 'Beta, closed to new models' : 'Beta, opt in by name'
    case 'deprecated':
      return `Deprecated, ends ${str(v.ends, 'soon')}`
    case 'retired':
      return 'Retired'
    default:
      return str(v.status, 'unknown')
  }
}

export type AdaLine = { text: string; tone?: 'error' | 'warning' | 'dim' }

/** The panel's Ada lines: a heading with the latest stable, a line per version
 *  the org can see (a retired one only while models are still listed on it),
 *  and, for each deprecated version with models, what happens and what to do. */
export function adaLines(me: Json | null): AdaLine[] {
  const ada = adaOf(me)
  if (!Object.keys(ada).length) return [{ text: 'Ada versions: not available yet.', tone: 'dim' }]
  const newer = tooNew(ada.contract)
  if (newer) return [{ text: newer, tone: 'error' }]
  const latest = str(ada.latest_stable)
  const versions = (Array.isArray(ada.versions) ? ada.versions : []).map(obj)
  const out: AdaLine[] = [{ text: `Ada versions: the latest stable is ${latest || 'not known'}.` }]
  for (const v of versions) {
    if (str(v.status) === 'retired' && !v.models) continue
    out.push({ text: `${str(v.name)} · ${statusText(v, latest)} · ${models(v.models)}` })
  }
  for (const v of versions) {
    if (str(v.status) !== 'deprecated' || !v.models) continue
    out.push({
      text:
        `${models(v.models)} on ${str(v.name)}: it answers until ${str(v.ends, 'its end')}, then they move to ${latest} ` +
        `by themselves. Upgrade sooner: ask Claude to backtest ${latest} and upgrade.`,
      tone: 'warning',
    })
  }
  return out
}
