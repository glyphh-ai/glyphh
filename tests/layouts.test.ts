import type { CommandRunInput } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const SURFACES = ['terminal', 'desktop'] as const

const pane = (surface: (typeof SURFACES)[number]) => ({
  plugin: 'workspaces',
  surface,
  component: 'Pane' as const,
  requestId: 'workspaces',
  props: {
    title: 'Workspaces',
    isFocused: true,
    bodyColumns: 101,
    placement: 'dock' as const,
    scroll: { offset: 0, bodyRows: 28 },
    view: {},
  },
  viewport: { columns: 101, rows: 30 },
})

for (const surface of SURFACES) {
  test(`${surface}: draws the active layout with its tabs, file and divider`, async ($, on) => {
    on('session.cwd', () => ({ value: '/proj' }))
    on('fs.read', () => ({ value: 'first line\nsecond line' }))
    const ui = await $.ui.mount(pane(surface))
    await ui.press({ key: 'tab-1' }) // Browse + file

    expect(await ui.findAll({ type: 'Button', key: 'tab-0' })).toHaveLength(1)
    expect(await ui.findAll({ type: 'Button', key: 'tab-1' })).toHaveLength(1)
    expect(await ui.find({ type: 'Code' })).toBeDefined()
    expect(await ui.find({ type: 'Client', key: 'vdiv-0' })).toBeDefined()
  })

  test(`${surface}: a tab switches the layout`, async ($, on) => {
    on('session.cwd', () => ({ value: '/proj' }))
    on('fs.read', () => ({ value: '{}' }))
    const ui = await $.ui.mount(pane(surface))

    await ui.press({ key: 'tab-2' })

    // "Two browsers" is 2×2: a row divider down each column.
    expect(await ui.find({ type: 'Client', key: 'hdiv-0-0' })).toBeDefined()
    expect(await ui.find({ type: 'Client', key: 'hdiv-1-0' })).toBeDefined()
  })

  test(`${surface}: dragging a divider moves the column split`, async ($, on) => {
    on('session.cwd', () => ({ value: '/proj' }))
    on('fs.read', () => ({ value: 'x' }))
    let saved: unknown
    on('store.set', (_$, e) => {
      saved = e.value
      return { value: undefined }
    })
    const ui = await $.ui.mount(pane(surface))
    await ui.press({ key: 'tab-1' }) // Browse + file: 0.6 | 0.4

    await ui.pointer({ type: 'down', x: 0, y: 3, button: 'left', in: 'vdiv-0' })
    await ui.pointer({ type: 'move', x: 10, y: 3, button: 'left', in: 'vdiv-0' })
    await ui.pointer({ type: 'up', x: 10, y: 3, button: 'left', in: 'vdiv-0' })

    // Released, the layout is saved: 10 cells of a 101-column body moves
    // the split 0.6 → ~0.699, the pair still summing to 1.
    const widths = (saved as { name: string; colWidths: number[] }[]).find(l => l.name === 'Browse + file')!.colWidths
    expect(Math.abs(widths[0]! - (0.6 + 10 / 101))).toBeLessThan(1e-9)
    expect(Math.abs(widths[0]! + widths[1]! - 1)).toBeLessThan(1e-9)
  })
}

test('terminal: a browser cell is a picture under an input layer', async ($, on) => {
  on('env.get', (_$, e) => ({ value: e.name === 'TERM_PROGRAM' ? 'ghostty' : undefined }))
  on('session.cwd', () => ({ value: '/proj' }))
  on('fs.read', () => ({ value: 'x' }))
  const ui = await $.ui.mount(pane('terminal'))

  const id = 'Browse + file:0,0'
  await ui.press({ key: 'tab-1' })
  expect(await ui.find({ type: 'Image', key: `img-${id}` })).toBeDefined()
  expect(await ui.find({ type: 'Client', key: `in-${id}` })).toBeDefined()
})

for (const surface of SURFACES) {
  test(`${surface}: IDE opens a file from the browser and saves an edit`, async ($, on) => {
    on('session.cwd', () => ({ value: '/proj' }))
    on('fs.list', () => ({
      value: [
        { name: 'README.md', kind: 'file' as const, size: 5, mtimeMs: 0, isLink: false },
        { name: 'hooks', kind: 'dir' as const, size: 0, mtimeMs: 0, isLink: false },
      ],
    }))
    on('fs.read', () => ({ value: 'hello' }))
    const writes: { path: string; text: string }[] = []
    on('fs.write', (_$, e) => {
      writes.push({ path: e.path, text: e.text })
      return { value: undefined }
    })
    on('ui.toast', () => ({ value: undefined }))
    on('process.run', () => ({
      value: {
        exitCode: 0,
        stdout: 'diff --git a/x.ts b/x.ts\nindex 1..2 100644\n--- a/x.ts\n+++ b/x.ts\n@@ -1,1 +1,1 @@\n-old\n+new\n',
        stderr: '',
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    }))
    const ui = await $.ui.mount(pane(surface))

    await ui.press({ key: 'tab-3' })
    expect(await ui.find({ type: 'Button', key: 't-/proj/hooks' })).toBeDefined()
    await ui.press({ key: 't-/proj/README.md' })

    const editor = 'ed-/proj/README.md'
    expect(await ui.find({ type: 'Client', key: editor })).toBeDefined()
    await ui.pointer({ type: 'down', x: 2, y: 0, button: 'left', in: editor })
    await ui.key({ key: 'end', in: editor })
    await ui.key({ key: '!', in: editor })
    await ui.key({ key: 's', ctrl: true, in: editor })

    expect(writes).toEqual([{ path: '/proj/README.md', text: 'hello!' }])
    expect(await ui.find({ type: 'Text', text: 'x.ts' })).toBeDefined() // the real diff's file
  })
}

test('/dip jumps by number and name, and back bounces between the two', async ($, on) => {
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.spawn', async function* () {
    return { value: { code: 0, signal: null } }
  })
  const dip = async (args: string) =>
    (await $.command.run({ command: 'dip', args } as unknown as CommandRunInput)) as { text?: string }

  expect((await dip('1')).text).toBe('→ Comms')
  expect((await dip('IDE')).text).toBe('→ IDE')
  expect((await dip('back')).text).toBe('→ Comms')
  expect((await dip('back')).text).toBe('→ IDE')
  expect((await dip('nope')).text).toStartWith('No layout "nope"')
})

test('terminal without pictures: a browser cell offers Ghostty instead', async ($, on) => {
  on('env.get', (_$, e) => ({ value: e.name === 'TERM_PROGRAM' ? 'Apple_Terminal' : undefined }))
  on('session.cwd', () => ({ value: '/proj' }))
  const ran: string[][] = []
  on('process.run', (_$, e) => {
    ran.push([...e.argv])
    return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.toast', () => ({ value: undefined }))
  const ui = await $.ui.mount(pane('terminal'))

  const id = 'Comms:0,0'
  expect(await ui.find({ type: 'Image', key: `img-${id}` })).toBeUndefined()
  await ui.press({ key: `ghostty-${id}` })
  expect(ran[0]?.slice(0, 3)).toEqual(['open', '-na', 'Ghostty'])
})
