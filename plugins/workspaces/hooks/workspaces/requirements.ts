// What the layout page needs on this Mac: Google Chrome (it draws the pages)
// and Node.js 18 or newer (it runs the helper). Found at the session start.
import type { Requirements } from '../../types'

export type Probe = {
  exists(path: string): Promise<boolean>
  /** A command's output, or null when it could not run. */
  run(argv: readonly string[]): Promise<{ exitCode: number; stdout: string } | null>
}

const CHROME = 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

export async function findChrome(p: Probe, home: string | undefined): Promise<string | null> {
  for (const path of [`/${CHROME}`, ...(home ? [`${home.replace(/\/$/, '')}/${CHROME}`] : [])]) {
    if (await p.exists(path)) return path
  }
  return null
}

async function isNode18(p: Probe, node: string): Promise<boolean> {
  const r = await p.run([node, '--version'])
  const major = Number(/^v(\d+)\./.exec(r?.stdout.trim() ?? '')?.[1])
  return r?.exitCode === 0 && major >= 18
}

/** Node on the session's PATH, else the login shell's, else Homebrew's or /usr/local's. */
export async function findNode(p: Probe): Promise<string | null> {
  if (await isNode18(p, 'node')) return 'node'
  const shell = await p.run(['/bin/zsh', '-lc', 'command -v node'])
  const found = shell?.exitCode === 0 ? shell.stdout.trim().split('\n').pop()! : ''
  for (const node of [found, '/opt/homebrew/bin/node', '/usr/local/bin/node']) {
    if (node.startsWith('/') && (await isNode18(p, node))) return node
  }
  return null
}

/** What to install, said exactly; null when nothing is missing. */
export function missingText(r: Requirements | null): string | null {
  if (!r || (r.chrome && r.node)) return null
  const need = [
    ...(r.chrome ? [] : ['Google Chrome (https://www.google.com/chrome/)']),
    ...(r.node ? [] : ['Node.js 18 or newer (https://nodejs.org)']),
  ]
  return `The layout page needs ${need.join(' and ')}. Install ${need.length === 1 ? 'it' : 'them'}, then start a new session.`
}
