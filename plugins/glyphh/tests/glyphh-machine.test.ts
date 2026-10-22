// The machine id: each platform's source, the MAC and saved-id fallbacks, the
// hashing, and the id the mod's device flow sends.
import { expect, test } from 'claude-code/testing'

import { startSignIn, stopPolling } from '../hooks/glyphh/device'
import { forgetMachineId, hashMachine, machineId, rawMachineValue, type MachineProbe } from '../hooks/glyphh/machine'
import { HOME, fakeHost } from './fake-host'

type Out = Record<string, string>

/** A probe whose commands answer by their first word, whose files are a map. */
function probe(platform: string | undefined, out: Out, files: Out = {}) {
  const ran: string[] = []
  const p: MachineProbe = {
    platform,
    home: HOME,
    run: async argv => {
      ran.push(argv[0]!)
      const stdout = out[argv[0]!]
      return stdout === undefined ? { exitCode: 1, stdout: '' } : { exitCode: 0, stdout }
    },
    read: async path => files[path],
    write: async (path, text) => void (files[path] = text),
  }
  return { p, ran, files }
}

const IOREG = '+-o Mac  <class IOPlatformExpertDevice>\n    "IOPlatformUUID" = "11111111-2222-3333-4444-555555555555"\n'

test('machine id: the hardware id on macOS, Linux and Windows', async () => {
  expect(await rawMachineValue(probe('darwin', { '/usr/sbin/ioreg': IOREG }).p)).toEqual({
    source: 'hardware',
    value: '11111111-2222-3333-4444-555555555555',
  })
  expect(await rawMachineValue(probe('linux', {}, { '/etc/machine-id': 'abc123\n' }).p)).toEqual({ source: 'hardware', value: 'abc123' })
  expect((await rawMachineValue(probe('linux', {}, { '/var/lib/dbus/machine-id': 'dbus9' }).p)).value).toBe('dbus9')
  const reg = '\r\nHKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography\r\n    MachineGuid    REG_SZ    9f0e-guid-77\r\n'
  expect((await rawMachineValue(probe('win32', { reg }).p)).value).toBe('9f0e-guid-77')
  const wmic = 'UUID\r\n4C4C4544-0042-3510-8051-B7C04F4E3732\r\n'
  expect((await rawMachineValue(probe('win32', { wmic }).p)).value).toBe('4C4C4544-0042-3510-8051-B7C04F4E3732')
  // An unknown platform tries each source in turn.
  const any = probe(undefined, {}, { '/etc/machine-id': 'linuxid' })
  expect((await rawMachineValue(any.p)).value).toBe('linuxid')
  expect(any.ran[0]).toBe('/usr/sbin/ioreg')
})

test('machine id: no hardware id falls back to the primary MAC, then a saved random id', async () => {
  expect(await rawMachineValue(probe('darwin', { '/bin/sh': 'A4:83:E7:01:02:03\n' }).p)).toEqual({ source: 'mac', value: 'a4:83:e7:01:02:03' })
  expect((await rawMachineValue(probe('win32', { getmac: '"A4-83-E7-0A-0B-0C","\\Device\\Tcpip_{X}"\r\n' }).p)).value).toBe(
    'a4:83:e7:0a:0b:0c',
  )
  const zero = probe('linux', { '/bin/sh': '00:00:00:00:00:00\n' })
  const first = await rawMachineValue(zero.p)
  expect(first.source).toBe('saved')
  expect(JSON.parse(zero.files[`${HOME}/.glyphh/machine.json`]!)).toEqual({ id: first.value })
  expect(await rawMachineValue(zero.p)).toEqual(first) // kept once, read back after
  expect((await rawMachineValue(probe('linux', {}, { [`${HOME}/.glyphh/machine.json`]: '{"id":"kept-1"}' }).p)).value).toBe('kept-1')
})

test('machine id: only sha256("glyphh:" + value) is sent, worked out once', async () => {
  expect(await hashMachine('abc')).toBe('0e69ccaf482bc56110573c20262432b67da826932e3273d9a8f69676f9fa58b0')
  forgetMachineId()
  const once = probe('darwin', { '/usr/sbin/ioreg': IOREG })
  const id = await machineId(once.p)
  expect(id).toMatch(/^[0-9a-f]{64}$/)
  expect(id).toBe(await hashMachine('11111111-2222-3333-4444-555555555555'))
  expect(await machineId(once.p)).toBe(id)
  expect(once.ran.length).toBe(1)
  forgetMachineId()
})

test('machine id: the mod sends it with its device-code request', async () => {
  forgetMachineId()
  const w = fakeHost()
  await startSignIn(w.gh)
  stopPolling()
  // fake-host's ioreg answers MACHINE_UUID; sha256("glyphh:" + it):
  expect(w.s.calls[0]?.body.machine_id).toBe('532f8379e3a901c5fa3fd2536171ca31e9a3d51e7d849d2bc2270e66796e643c')
  forgetMachineId()
})
