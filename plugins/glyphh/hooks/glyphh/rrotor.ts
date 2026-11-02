// The local rrotor (the rrotor skill installs it on 127.0.0.1:7777 with a
// local token in ~/.glyphh/rrotor/token): one call, publishing a file as an
// app. Refusals come back in rrotor's own words, as the server's do.
import { ApiError } from './api'
import { glyphhPath } from './home'
import type { Host } from './host'

export const RROTOR_URL = 'http://127.0.0.1:7777'

/** The local token the rrotor skill kept; none means rrotor was never installed here. */
export async function rrotorToken(gh: Host): Promise<string | undefined> {
  const path = await glyphhPath(gh, 'rrotor/token')
  if (!path) return undefined
  return (await gh.fs.read(path).catch(() => '')).trim() || undefined
}

/** What `POST /v1/apps` takes: the app's files (text, or `{base64}` for a PDF
 *  or an image) and what the catalogue shows; `type` one of page, dashboard,
 *  doc, diagram, deck, design (absent: the entry's own). */
export type AppPublish = {
  name: string
  title: string
  description: string
  type?: string
  roles: string[]
  files: Record<string, string | { base64: string }>
  entry: string
}

/** What rrotor answers: the version made, its type, whether it is served already, and where. */
export type AppPublished = { program: string; version: number; type?: string; state?: string; active?: boolean; url?: string }

export async function publishApp(gh: Host, body: AppPublish): Promise<AppPublished> {
  const token = await rrotorToken(gh)
  if (!token) throw new ApiError('E_NO_RROTOR', 'No rrotor on this machine: ask Claude to "install rrotor" first (the rrotor skill).', 0)
  let r
  try {
    r = await gh.http.fetch(`${RROTOR_URL}/v1/apps`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError('E_NETWORK', `rrotor is not answering at ${RROTOR_URL}: start it ("start rrotor", the rrotor skill).`, 0)
  }
  let parsed: unknown
  try {
    parsed = r.text.trim() ? JSON.parse(r.text) : {}
  } catch {
    throw new ApiError('E_BAD_REPLY', `rrotor's answer to POST /v1/apps is not JSON.`, r.status)
  }
  if (!r.ok) {
    const err = (parsed as { error?: { code?: unknown; message?: unknown } }).error
    const code = String(err?.code ?? `E_HTTP_${r.status}`)
    throw new ApiError(code, String(err?.message ?? `rrotor refused the publish (HTTP ${r.status}).`), r.status)
  }
  return parsed as AppPublished
}
