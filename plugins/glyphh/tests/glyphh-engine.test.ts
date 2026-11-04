// Through the engine: the /glyphh command and the panel on both surfaces,
// the fake server answering $.http.fetch, files kept in memory.
import type { CommandRunInput, On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'

import { HOME } from './fake-host'
import { fakeServer } from './fake-server'

const SURFACES = ['terminal', 'desktop'] as const

// rrotor's parts of the panel shown (GLYPHH_RROTOR=1) unless a test says shelved, as the plugin ships.
function world(on: On, surface: 'terminal' | 'desktop', rrotor = true) {
  const server = fakeServer()
  const files = new Map<string, string>()
  const opened: string[] = []
  const shown = rrotor ? { GLYPHH_RROTOR: '1' } : {}
  mock.env(on, surface === 'terminal' ? { HOME, TERM_PROGRAM: 'ghostty', ...shown } : { HOME, ...shown })
  mock.store(on)
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  on('tool.register', (_$, e) => ({ value: { tool: `mcp__glyphh__${e.name}` } }))
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
  const ran: string[][] = []
  on('process.run', (_$, e) => {
    ran.push([...e.argv])
    if (e.argv[0] === '/bin/sh') files.set(String(e.argv[5]), String(e.init?.stdin))
    if (String(e.argv[1]).endsWith('/skills/rrotor/scripts/rrotor.sh') && e.argv[2] === 'update') {
      // The rrotor skill's script: the pinned release pulled and run, the link kept.
      const from = server.s.rrotor.version
      server.s.rrotor.version = '0.3.0'
      const out = JSON.stringify({ ok: true, from, to: '0.3.0', link: server.s.rrotor.link })
      return { value: { exitCode: 0, stdout: `${out}\n`, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    }
    return { value: { exitCode: 0, stdout: 'testmac', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.surface', () => ({ value: surface }))
  on('mcp.call', (_$, e) => (opened.push(String(e.args?.url)), { value: { content: [], isError: false } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  return { server, files, opened, ran }
}

const pane = (surface: (typeof SURFACES)[number]) => ({
  plugin: 'glyphh',
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
    await ui.press({ key: 'sec-plan' })
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
})

// rrotor shelved (his ruling, 2026-11-02; hooks/glyphh/shelved.ts): without GLYPHH_RROTOR=1 the panel is the account's
// and Ada's alone, and /glyphh publish, link and apps are not commands.
for (const surface of SURFACES) {
  test(`${surface}: rrotor shelved: no Apps tab, no rrotor row, and publish, link and apps answer the usage`, async ($, on) => {
    const w = world(on, surface, false)
    w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
    w.files.set(`${HOME}/.glyphh/rrotor/token`, 'rt-local-1\n')
    await $.session.start({ cwd: '/proj', surface, isInteractive: true })
    const ui = await $.ui.mount(pane(surface))
    await ui.press({ key: 'sec-account' })
    expect(await ui.find({ type: 'Input', key: 'me-name' })).toBeDefined()
    expect(await ui.find({ key: 'sec-plan' })).toBeDefined()
    expect(await ui.find({ key: 'sec-apps' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: 'rrotor-link' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /rrotor/ })).toBeUndefined()
    const run = async (args: string) =>
      (await $.command.run({ command: 'glyphh', args } as unknown as CommandRunInput)) as { text: string }
    for (const args of ['publish page.html', 'link', 'apps']) {
      expect((await run(args)).text).toBe('Usage: /glyphh [login | logout | account | org | plan | billing]')
    }
    expect(w.server.s.tokens).toEqual([])
    expect(w.server.s.calls.some(c => c.path.startsWith('/v1/apps') || c.path === '/v1/runtime/local')).toBe(false)
  })
}

test('/glyphh after the sign-in card signed in (install.json written mid-session) says who is signed in', async ($, on) => {
  const w = world(on, 'desktop')
  await $.session.start({ cwd: '/proj', surface: 'desktop', isInteractive: true })
  w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
  const r = (await $.command.run({ command: 'glyphh', args: '' } as unknown as CommandRunInput)) as { text: string }
  expect(r.text).toStartWith('Glyphh: signed in as chris@example.com')
  expect(w.server.s.calls.some(c => c.path === '/v1/device/code')).toBe(false)
})

for (const surface of SURFACES) {
  test(`${surface}: Apps lists the published ones as cards with a type chip and Open; the type filter cycles; a reviewer sees the drafts and acts; search narrows`, async ($, on) => {
    const w = world(on, surface)
    w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
    await $.session.start({ cwd: '/proj', surface, isInteractive: true })
    const ui = await $.ui.mount(pane(surface))
    await ui.press({ key: 'sec-apps' })
    expect(await ui.find({ type: 'Text', text: 'App 1' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Page' })).toBeDefined() // the type chip
    expect(await ui.find({ type: 'Text', text: 'Dashboard' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /acme-prod · v1/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Everyone · Published by Chris · 2026-11-01/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /sre · Published by Chris/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '1–3 of 3' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'app-next' })).toBeUndefined()
    await ui.press({ key: 'app-open-a1' })
    expect(w.opened).toEqual(surface === 'desktop' ? ['https://rrotor.acme.test/apps/app-1/'] : [])
    expect(await ui.find({ type: 'Button', key: 'app-retire-a1' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'app-approve-a1' })).toBeUndefined()

    // The type filter: one button, cycling.
    expect((await ui.find({ type: 'Button', key: 'app-type' }))?.props.label).toBe('All types')
    await ui.press({ key: 'app-type' })
    expect((await ui.find({ type: 'Button', key: 'app-type' }))?.props.label).toBe('Pages')
    expect(await ui.find({ type: 'Text', text: 'App 1' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'App 2' })).toBeUndefined()
    for (const label of ['Dashboards', 'Docs', 'Diagrams', 'Decks', 'Designs']) {
      await ui.press({ key: 'app-type' })
      expect((await ui.find({ type: 'Button', key: 'app-type' }))?.props.label).toBe(label)
    }
    expect(await ui.find({ type: 'Text', text: 'No designs here.' })).toBeDefined()
    await ui.press({ key: 'app-type' })
    expect((await ui.find({ type: 'Button', key: 'app-type' }))?.props.label).toBe('All types')
    expect(await ui.find({ type: 'Text', text: 'App 2' })).toBeDefined()

    await ui.press({ key: 'app-view-draft' })
    expect(await ui.find({ type: 'Text', text: 'App 4' })).toBeDefined()
    await ui.press({ key: 'app-reject-a4' })
    expect(await ui.find({ type: 'Input', key: 'app-reason-a4' })).toBeDefined()
    await ui.input({ key: 'app-reason-a4', text: 'Numbers are wrong.' })
    expect(w.server.s.apps.find(a => a.id === 'a4')?.reason).toBe('Numbers are wrong.')
    expect(await ui.find({ type: 'Text', text: 'Rejected, with the reason.' })).toBeDefined()
    await ui.press({ key: 'app-view-rejected' })
    expect(await ui.find({ type: 'Text', text: /Rejected: Numbers are wrong\./ })).toBeDefined()
    await ui.press({ key: 'app-approve-a5' })
    expect(w.server.s.apps.find(a => a.id === 'a5')?.state).toBe('approved')

    await ui.press({ key: 'app-view-approved' })
    await ui.input({ key: 'app-search', text: 'app-5' })
    expect(await ui.find({ type: 'Text', text: 'App 5' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'App 1' })).toBeUndefined()
    await ui.input({ key: 'app-search', text: 'zzz' })
    expect(await ui.find({ type: 'Text', text: 'Nothing matches "zzz".' })).toBeDefined()

    w.server.s.reviewer = false
    await ui.press({ key: 'sec-apps' })
    expect(await ui.find({ type: 'Button', key: 'app-view-draft' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: 'app-retire-a2' })).toBeUndefined()
  })

  test(`${surface}: Account shows this machine's rrotor and links it to Glyphh`, async ($, on) => {
    const w = world(on, surface)
    w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
    await $.session.start({ cwd: '/proj', surface, isInteractive: true })
    const ui = await $.ui.mount(pane(surface))
    await ui.press({ key: 'sec-account' })
    expect(await ui.find({ type: 'Text', text: 'No rrotor on this machine: ask Claude to "install rrotor".' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'rrotor-link' })).toBeUndefined()

    w.files.set(`${HOME}/.glyphh/rrotor/token`, 'rt-local-1\n')
    await ui.press({ key: 'sec-account' })
    expect(await ui.find({ type: 'Text', text: 'Not linked (rrotor 0.2.0)' })).toBeDefined()
    expect((await ui.find({ type: 'Button', key: 'rrotor-link' }))?.props.label).toBe('link')
    await ui.press({ key: 'rrotor-link' })
    expect(await ui.find({ type: 'Text', text: /Linked to Glyphh as rt-local-1/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Linked as rt-local-1 (rrotor 0.2.0)' })).toBeDefined()
    expect((await ui.find({ type: 'Button', key: 'rrotor-link' }))?.props.label).toBe('link again')
    expect(w.server.s.tokens).toEqual([{ runtime_id: 'rt-local-1', token: 'rtok-1' }])

    // 0.2.0 is behind the release this plugin pins: the row says so and offers update, which runs the skill's script.
    expect(await ui.find({ type: 'Text', text: 'Update to 0.3.0' })).toBeDefined()
    expect((await ui.find({ type: 'Button', key: 'rrotor-update' }))?.props.label).toBe('update')
    await ui.press({ key: 'rrotor-update' })
    expect(w.ran.some(argv => argv[0] === 'sh' && String(argv[1]).endsWith('/skills/rrotor/scripts/rrotor.sh') && argv[2] === 'update')).toBe(true)
    expect(await ui.find({ type: 'Text', text: 'rrotor updated from 0.2.0 to 0.3.0. Claude Code loads its tools again at /mcp or its next start.' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Linked as rt-local-1 (rrotor 0.3.0)' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'rrotor-update' })).toBeUndefined()
  })

  test(`${surface}: Plan shows the cloud use and the plans' caps; Billing offers checkout, Talk to us and no seats`, async ($, on) => {
    const w = world(on, surface)
    w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
    await $.session.start({ cwd: '/proj', surface, isInteractive: true })
    const ui = await $.ui.mount(pane(surface))
    await ui.press({ key: 'sec-plan' })
    expect(await ui.find({ type: 'Text', text: /Precedents: 432 of 1,000, in 2 models/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Reads 2026-10: 1,234 of 5,000/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /start again 2026-11-01/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Team' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^\$299\/month · 1,000,000 precedents · 5,000,000 reads a month · then \$1 per 10,000$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Enterprise' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^By contract/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /seat/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /[Ll]icen[cs]e|machine|runtime|[Hh]osting|self-hosted/ })).toBeUndefined()

    await ui.press({ key: 'sec-billing' })
    expect((await ui.find({ type: 'Button', key: 'bill-plan-Pro' }))?.props.label).toBe('checkout')
    expect((await ui.find({ type: 'Button', key: 'bill-plan-Enterprise' }))?.props.label).toBe('Talk to us')
    expect(await ui.find({ type: 'Button', key: 'bill-plan-Free' })).toBeUndefined() // the plan it is on
    expect(await ui.find({ type: 'Input', key: 'bill-seats' })).toBeUndefined()
    await ui.press({ key: 'bill-plan-Pro' })
    expect(w.server.s.calls.at(-1)).toMatchObject({ path: '/v1/billing/checkout', body: { plan: 'Pro' } })

    w.server.s.billingStatus = 'active'
    w.server.s.plan = 'Pro'
    await ui.press({ key: 'sec-billing' })
    expect((await ui.find({ type: 'Button', key: 'bill-plan-Team' }))?.props.label).toBe('switch')
    expect((await ui.find({ type: 'Button', key: 'bill-plan-Free' }))?.props.label).toBe('switch')
    expect(await ui.find({ type: 'Button', key: 'bill-plan-Pro' })).toBeUndefined()

    w.server.s.plan = 'Enterprise'
    await ui.press({ key: 'sec-billing' })
    expect(await ui.find({ type: 'Text', text: /set in your contract/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'bill-talk' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'bill-plan-Team' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: 'bill-portal' })).toBeDefined()
  })
}

// /dip through the engine: the Dip pane's editor writes a layout, its Dip button calls the app's tools.
const dipPane = (surface: (typeof SURFACES)[number]) => ({ ...pane(surface), requestId: 'glyphh-dip', props: { ...pane(surface).props, title: 'Dip' } })

for (const surface of SURFACES) {
  test(`${surface}: the Dip pane writes a layout and dips into it`, async ($, on) => {
    world(on, surface)
    const called: string[] = []
    on('tool.call', (_$, e) => (called.push(`${e.tool} ${JSON.stringify(e)}`), { result: '{}' }))
    on('session.cwd', () => ({ value: '/proj' }))
    await $.session.start({ cwd: '/proj', surface, isInteractive: true })
    const ui = await $.ui.mount(dipPane(surface))
    expect(await ui.find({ type: 'Text', text: 'No layouts yet.' })).toBeDefined()
    await ui.press({ key: 'new' })
    await ui.input({ key: 'dip-name', text: 'api', kind: 'change' })
    await ui.input({ key: 'dip-tabs', text: '* localhost:3000', kind: 'change' })
    // Claude | Browser, then a second row: Terminal under the browser, Claude merged down the left.
    await ui.select({ key: 'dip-rows', value: '2' })
    await ui.press({ key: 'cell-3' })
    await ui.press({ key: 'fill-terminal' })
    await ui.press({ key: 'cell-0' })
    await ui.press({ key: 'merge-down' })
    await ui.press({ key: 'save' })
    expect(await ui.find({ type: 'Text', text: 'Saved api: /dip api' })).toBeDefined()
    await ui.press({ key: 'dip-api' })
    expect(called.some(c => c.startsWith('mcp__Claude_Browser__preview_start') && c.includes('https://localhost:3000'))).toBe(true)
    expect(called.some(c => c.startsWith('mcp__ccd_view__show_pane') && c.includes('"terminal"'))).toBe(true)
    expect(await ui.find({ type: 'Text', text: 'active' })).toBeDefined()
    const said = (await $.command.run({ command: 'dip', args: 'nope' } as unknown as CommandRunInput)) as { text: string }
    expect(said.text).toBe('No layout "nope". Layouts: api.')
  })
}
