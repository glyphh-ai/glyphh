// The same MCP server over Streamable HTTP, for a remote Claude connector in
// development (ngrok in front): GLYPHH_MCP_HTTP_PORT turns it on. Stateless:
// each request gets a fresh transport; the sign-in flow is shared so the
// card's polls see the code its first call started.
import { createServer, type IncomingMessage } from 'node:http'
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js'

async function body(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  for await (const c of req) chunks.push(c as Buffer)
  const text = Buffer.concat(chunks).toString('utf8')
  return text ? JSON.parse(text) : undefined
}

export function serveHttp(port: number, make: () => McpServer) {
  createServer(async (req, res) => {
    if (!req.url?.startsWith('/mcp')) return void res.writeHead(404).end()
    const server = make()
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined })
    res.on('close', () => void transport.close().then(() => server.close()))
    try {
      await server.connect(transport)
      await transport.handleRequest(req, res, req.method === 'POST' ? await body(req) : undefined)
    } catch {
      if (!res.headersSent) res.writeHead(500).end()
    }
  }).listen(port, '127.0.0.1', () => console.error(`glyphh MCP on http://127.0.0.1:${port}/mcp`))
}
