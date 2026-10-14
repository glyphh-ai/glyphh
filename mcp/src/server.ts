// The plugin's MCP server (stdio): glyphh_sign_in shows the sign-in card,
// an MCP App at ui://glyphh/sign-in/1; the card polls glyphh_sign_in_status.
// Built to dist/server.mjs by build.sh; .mcp.json at the plugin root starts it.
import { readFileSync } from 'node:fs'
import { hostname } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'

import { SignIn, cardText, type Card, type Deps } from './flow'
import { machineId } from '../../hooks/glyphh/machine'
import { installPath, machineProbe, readInstall, writeInstall } from './install'

// A new address whenever the card changes: hosts keep a card's HTML by its address.
export const CARD_URI = 'ui://glyphh/sign-in/1'
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
  server.registerResource('sign-in', CARD_URI, { title: 'Glyphh sign-in', mimeType: MIME }, async () => ({
    contents: [{ uri: CARD_URI, mimeType: MIME, text: cardHtml() }],
  }))
  signInTool(server, flow)
  statusTool(server, flow)
  return server
}

await makeServer(new SignIn(deps())).connect(new StdioServerTransport())
