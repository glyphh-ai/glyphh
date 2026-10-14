// Through the engine: the /glyphh command and the panel on both surfaces,
// the fake server answering $.http.fetch, files kept in memory.
import type { CommandRunInput, On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'

import { HOME } from './fake-host'
import { fakeServer } from './fake-server'

const SURFACES = ['terminal', 'desktop'] as const

function world(on: On, surface: 'terminal' | 'desktop') {
  const server = fakeServer()
  const files = new Map<string, string>()
  const opened: string[] = []
  mock.env(on, surface === 'terminal' ? { HOME, TERM_PROGRAM: 'ghostty' } : { HOME })
  mock.store(on)
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  on('tool.register', (_$, e) => ({ value: { tool: `mcp__workspaces__${e.name}` } }))
  on('ui.toast', () => ({ value: undefined }))
  mock.clock(on, { now: Date.parse('2026-10-13T12:00:00Z') })
  on('http.fetch', async (_$, e) => ({ value: await server.fetch(e.url, e.init) }))
  on('fs.read', (_$, e) => {
    const t = files.get(e.path)
    if (t === undefined) throw new Error('ENOENT')
    return { value: t }
  })
  on('fs.write', (_$, e) => (files.set(e.path, e.text), { value: undefined }))
  on('fs.exists', (_$, e) => ({ value: [...files.keys()].some(k => k === e.path || k.startsWith(`${e.path}/`)) }))
  on('fs.list', (_$, e) => ({
    value: [...files.keys()]
      .filter(k => k.startsWith(`${e.path}/`))
      .map(k => ({ name: k.slice(String(e.path).length + 1), kind: 'file' as const, size: 1, mtimeMs: 0, isLink: false })),
  }))
  on('process.run', (_$, e) => {
    if (e.argv[0] === '/bin/sh') files.set(String(e.argv[5]), String(e.init?.stdin))
    return { value: { exitCode: 0, stdout: 'testmac', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.surface', () => ({ value: surface }))
  on('mcp.call', (_$, e) => (opened.push(String(e.args?.url)), { value: { content: [], isError: false } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  return { server, files, opened }
}

const pane = (surface: (typeof SURFACES)[number]) => ({
  plugin: 'workspaces',
  surface,
  component: 'Pane' as const,
  requestId: 'glyphh',
  props: { title: 'Glyphh', isFocused: true, bodyColumns: 100, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 28 }, view: {} },
  viewport: { columns: 100, rows: 30 },
})

for (const surface of SURFACES) {
  test(`${surface}: signed out, every section is the sign-in; pressing it shows the code`, async ($, on) => {
    const w = world(on, surface)
    const ui = await $.ui.mount(pane(surface))
    expect(await ui.find({ type: 'Button', key: 'signin' })).toBeDefined()
    await ui.press({ key: 'sec-workspaces' })
    expect(await ui.find({ type: 'Button', key: 'signin' })).toBeDefined()

    await ui.press({ key: 'signin' })
    expect(await ui.find({ type: 'Text', text: 'ABCD-EFGH' })).toBeDefined()
    expect(await ui.find({ type: 'Link' })).toBeDefined()
    expect(w.opened).toEqual(surface === 'desktop' ? ['https://glyphh.test/v1/device?code=ABCD-EFGH'] : [])
    await ui.press({ key: 'signin-cancel' })
    expect(await ui.find({ type: 'Button', key: 'signin' })).toBeDefined()
  })
}

test('/glyphh signin prints the code and link; signed in, the panel shows the account', async ($, on) => {
  const w = world(on, 'terminal')
  const run = async (args: string) =>
    (await $.command.run({ command: 'glyphh', args } as unknown as CommandRunInput)) as { text: string }
  expect((await run('nonsense')).text).toStartWith('Usage: /glyphh')
  // Signed out, plain /glyphh goes straight to sign-in: the code and link in the panel and the reply.
  expect((await run('')).text).toBe(
    'Enter code ABCD-EFGH at https://glyphh.test/v1/device?code=ABCD-EFGH. Waiting for approval…\n' +
      'Or ask Claude: "sign in to Glyphh" for a sign-in card in the chat.',
  )
  expect((await run('signin')).text).toBe('Enter code ABCD-EFGH at https://glyphh.test/v1/device?code=ABCD-EFGH. Waiting for approval…')

  // Approved elsewhere: install.json appears; a new session start reads it.
  w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(pane('terminal'))
  await ui.press({ key: 'sec-account' })
  expect(await ui.find({ type: 'Input', key: 'me-name' })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'inst-revoke-i2' })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'idp-add-github' })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'idp-add-google' })).toBeUndefined()
  expect(await ui.find({ type: 'Button', key: 'idp-remove-google' })).toBeUndefined() // the only one
  await ui.press({ key: 'idp-add-github' })
  expect(await ui.find({ type: 'Text', text: /Finish in the browser, then press Refresh/ })).toBeDefined()
  expect((await ui.find({ type: 'Link' }))?.props.href).toBe('https://accounts.github.test/auth?link=1')
  await ui.input({ key: 'me-name', text: 'Christopher' })
  expect(w.server.s.name).toBe('Christopher')
  await ui.press({ key: 'sec-workspaces' })
  await ui.input({ key: 'ws-new', text: 'Research' })
  expect(w.server.s.workspaces).toContain('Research')
  await ui.input({ key: 'ws-new', text: 'Third' })
  expect(await ui.find({ type: 'Text', text: /\(2 of 2 workspaces used\)/ })).toBeDefined()
})

test('/glyphh after the sign-in card signed in (install.json written mid-session) says who is signed in', async ($, on) => {
  const w = world(on, 'desktop')
  await $.session.start({ cwd: '/proj', surface: 'desktop', isInteractive: true })
  w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
  const r = (await $.command.run({ command: 'glyphh', args: '' } as unknown as CommandRunInput)) as { text: string }
  expect(r.text).toStartWith('Glyphh: signed in as chris@example.com')
  expect(w.server.s.calls.some(c => c.path === '/v1/device/code')).toBe(false)
})

test('a divider dragged in the grid is saved to the workspace file', async ($, on) => {
  const w = world(on, 'terminal')
  on('session.cwd', () => ({ value: '/proj' }))
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  const file = `${HOME}/.glyphh/workspaces/browse-file.json`
  expect(JSON.parse(w.files.get(file)!).col_widths).toEqual([0.6, 0.4])
  const ui = await $.ui.mount({ ...pane('terminal'), requestId: 'workspaces', props: { ...pane('terminal').props, title: 'Workspaces', bodyColumns: 101 }, viewport: { columns: 101, rows: 30 } })
  await ui.press({ key: 'tab-1' })
  await ui.pointer({ type: 'down', x: 0, y: 3, button: 'left', in: 'vdiv-0' })
  await ui.pointer({ type: 'move', x: 10, y: 3, button: 'left', in: 'vdiv-0' })
  await ui.pointer({ type: 'up', x: 10, y: 3, button: 'left', in: 'vdiv-0' })
  const widths = JSON.parse(w.files.get(file)!).col_widths as number[]
  expect(Math.abs(widths[0]! - (0.6 + 10 / 101))).toBeLessThan(1e-9)
})
