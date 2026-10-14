// The plugin's MCP server (stdio): glyphh_sign_in shows the sign-in card,
// an MCP App at ui://glyphh/sign-in/3; the card polls glyphh_sign_in_status.
// Built to dist/server.mjs by build.sh; .mcp.json at the plugin root starts it.
import { execFile } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir, hostname } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { z } from 'zod'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { serveHttp } from './http'

import { SignIn, cardText, type Card, type Deps } from './flow'
import { machineId } from '../../hooks/glyphh/machine'
import { installPath, machineProbe, readInstall, writeInstall } from './install'

// A new address whenever the card changes: hosts keep a card's HTML by its address.
export const CARD_URI = 'ui://glyphh/sign-in/6'
const MIME = 'text/html;profile=mcp-app'
const MCP = join(dirname(fileURLToPath(import.meta.url)), '..')
const ROOT = process.env.CLAUDE_PLUGIN_ROOT || join(MCP, '..')

function cardHtml(): string {
  const lib = readFileSync(join(MCP, 'card', 'mcp-app.js'), 'utf8').replaceAll('</script', '<\\/script')
  return readFileSync(join(MCP, 'card', 'sign-in.html'), 'utf8').replace('__APP_JS__', () => lib)
}

function modVersion(): string {
  try {
    return String(JSON.parse(readFileSync(join(ROOT, '.claude-plugin', 'plugin.json'), 'utf8')).version ?? '0.0.0')
  } catch {
    return '0.0.0'
  }
}

async function http(method: string, url: string, body?: unknown, bearer?: string) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (bearer) headers.Authorization = `Bearer ${bearer}`
  const r = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  return { status: r.status, text: await r.text() }
}

function deps(): Deps {
  const path = installPath()
  return {
    server: (process.env.GLYPHH_SERVER_URL?.trim() || 'http://localhost:8080').replace(/\/+$/, ''),
    http,
    now: () => Date.now(),
    install: () => readInstall(path),
    keep: install => writeInstall(path, install),
    machineId: () => machineId(machineProbe()),
    device: {
      name: hostname().split('.')[0] || 'Claude',
      surface: process.env.CLAUDE_CODE_ENTRYPOINT === 'claude-desktop' ? 'desktop' : 'cli',
      mod_version: modVersion(),
    },
  }
}

const failure = (err: unknown) => ({
  isError: true,
  content: [{ type: 'text' as const, text: err instanceof Error ? err.message : String(err) }],
})

function signInTool(server: McpServer, flow: SignIn) {
  const description =
    'Sign this machine in to Glyphh: shows a sign-in card with a code and a Sign in button, or says who is signed in already.'
  const config = { title: 'Sign in to Glyphh', description, inputSchema: {}, _meta: { ui: { resourceUri: CARD_URI } } }
  server.registerTool('glyphh_sign_in', config, async () => {
    try {
      const card: Card = await flow.start()
      return { content: [{ type: 'text' as const, text: cardText(card) }], structuredContent: card }
    } catch (err) {
      return failure(err)
    }
  })
}

/** Asks the mod to open `url` in Claude's browser pane (it watches
 *  ~/.glyphh/open-request.json); with no mod to take it, the system browser. */
async function openInClaude(url: string) {
  const file = join(homedir(), '.glyphh', 'open-request.json')
  mkdirSync(dirname(file), { recursive: true })
  writeFileSync(file, JSON.stringify({ url, at: Date.now() }))
  await new Promise(r => setTimeout(r, 2500))
  if (!existsSync(file)) return
  rmSync(file, { force: true })
  execFile(process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'explorer' : 'xdg-open', [url], () => undefined)
}

function openTool(server: McpServer) {
  // The card's Sign in button: the host may not open links (or not localhost
  // ones), so this machine opens the approval page in its own browser. Only
  // the Glyphh server's own sign-in page, never an arbitrary address.
  const base = (process.env.GLYPHH_SERVER_URL || 'http://localhost:8080').replace(/\/$/, '')
  const _meta = { ui: { resourceUri: CARD_URI, visibility: ['app'] } }
  const inputSchema = { url: z.string() }
  server.registerTool('glyphh_sign_in_open', { title: 'Open the Glyphh sign-in page', description: 'Opens the sign-in page in this machine\'s browser. Called by the card.', inputSchema, _meta }, async ({ url }) => {
    const ok = url.startsWith(`${base}/v1/device?code=`)
    if (ok) await openInClaude(url)
    return { content: [{ type: 'text' as const, text: ok ? 'opened' : 'refused' }], structuredContent: { opened: ok } }
  })
}

function statusTool(server: McpServer, flow: SignIn) {
  const description = "The sign-in card's poll: whether the pending Glyphh sign-in was approved. Called by the card."
  // App-only: the card calls it; hosts that honour visibility keep it from the model.
  const _meta = { ui: { resourceUri: CARD_URI, visibility: ['app'] } }
  server.registerTool('glyphh_sign_in_status', { title: 'Glyphh sign-in status', description, inputSchema: {}, _meta }, async () => {
    const s = await flow.status()
    return { content: [{ type: 'text' as const, text: JSON.stringify(s) }], structuredContent: s }
  })
}

export function makeServer(flow: SignIn): McpServer {
  const server = new McpServer({ name: 'glyphh', version: modVersion() })
  // Hosts keep a tool's card address from when they connected, so the older
  // addresses serve the current card too.
  for (const uri of [CARD_URI, 'ui://glyphh/sign-in/1', 'ui://glyphh/sign-in/2', 'ui://glyphh/sign-in/3', 'ui://glyphh/sign-in/4', 'ui://glyphh/sign-in/5']) {
    server.registerResource(`sign-in ${uri}`, uri, { title: 'Glyphh sign-in', mimeType: MIME }, async () => ({
      contents: [{ uri, mimeType: MIME, text: cardHtml() }],
    }))
  }
  signInTool(server, flow)
  statusTool(server, flow)
  openTool(server)
  return server
}

const httpPort = Number(process.env.GLYPHH_MCP_HTTP_PORT || 0)
if (httpPort) {
  const flow = new SignIn(deps())
  serveHttp(httpPort, () => makeServer(flow))
} else {
  await makeServer(new SignIn(deps())).connect(new StdioServerTransport())
}
