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
  const ran: string[][] = []
  on('process.run', (_$, e) => {
    ran.push([...e.argv])
    if (e.argv[0] === '/bin/sh') files.set(String(e.argv[5]), String(e.init?.stdin))
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
      'Or ask Claude: "sign in to Glyphh".',
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

// Glyphh is Ada alone: the panel is the account's four sections, the only host called is the Glyphh server, and only
// for sign-in, /v1/me, /v1/installs, /v1/org, /v1/plans and /v1/billing.
const KEPT = /^\/v1\/(device\/(code|token)|me(\/identities(\/[^/]+)?)?|installs(\/[^/]+)?|sign-out|org(\/(members|invites)(\/[^/]+)?)?|plans|billing\/(checkout|portal|plan))$/
for (const surface of SURFACES) {
  test(`${surface}: the panel is Account, Org, Plan and Billing; anything else answers the usage; only kept endpoints are called`, async ($, on) => {
    const w = world(on, surface)
    w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
    await $.session.start({ cwd: '/proj', surface, isInteractive: true })
    const ui = await $.ui.mount(pane(surface))
    for (const id of ['account', 'org', 'plan', 'billing']) {
      expect(await ui.find({ key: `sec-${id}` })).toBeDefined()
      await ui.press({ key: `sec-${id}` })
    }
    await ui.press({ key: 'sec-account' })
    expect(await ui.find({ type: 'Input', key: 'me-name' })).toBeDefined()
    expect(await ui.find({ key: 'sec-apps' })).toBeUndefined()
    const run = async (args: string) =>
      (await $.command.run({ command: 'glyphh', args } as unknown as CommandRunInput)) as { text: string }
    for (const args of ['publish page.html', 'link', 'apps']) {
      expect((await run(args)).text).toBe('Usage: /glyphh [login | logout | account | org | plan | billing]')
    }
    expect(w.server.s.calls.length).toBeGreaterThan(0)
    expect(w.server.s.calls.filter(c => !KEPT.test(c.path)).map(c => c.path)).toEqual([])
    expect(w.ran.every(argv => ['hostname', '/usr/sbin/ioreg', '/bin/sh', '/bin/rm', 'osascript', 'reg', 'wmic', 'getmac'].includes(String(argv[0])))).toBe(true)
  })
}

test('/glyphh after another session signed in (install.json written mid-session) says who is signed in', async ($, on) => {
  const w = world(on, 'desktop')
  await $.session.start({ cwd: '/proj', surface: 'desktop', isInteractive: true })
  w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: w.server.TOKEN }))
  const r = (await $.command.run({ command: 'glyphh', args: '' } as unknown as CommandRunInput)) as { text: string }
  expect(r.text).toStartWith('Glyphh: signed in as chris@example.com')
  expect(w.server.s.calls.some(c => c.path === '/v1/device/code')).toBe(false)
})

for (const surface of SURFACES) {
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
