// The MCP server's Node side, run with `node --test mcp/test` (Node 22.18+ reads
// the .ts sources as they are): install.json kept 0600 and whole, read back as
// the mod reads it; the machine probe on this machine.
import assert from 'node:assert/strict'
import { mkdtemp, readdir, readFile, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'

import { hashMachine, rawMachineValue } from '../../hooks/glyphh/machine.ts'
import { installPath, machineProbe, readInstall, writeInstall } from '../src/install.ts'

test('install.json: written 0600 by rename, in a 0700 ~/.glyphh, read back', async () => {
  const home = await mkdtemp(join(tmpdir(), 'glyphh-'))
  const path = installPath(home)
  await writeInstall(path, { install_id: 'i1', token: 'tok' })
  assert.equal((await stat(path)).mode & 0o777, 0o600)
  assert.equal((await stat(join(home, '.glyphh'))).mode & 0o777, 0o700)
  assert.deepEqual(JSON.parse(await readFile(path, 'utf8')), { install_id: 'i1', token: 'tok' })
  await writeInstall(path, { install_id: 'i2', token: 'tok2' }) // replaced whole
  assert.deepEqual(await readInstall(path), { install_id: 'i2', token: 'tok2' })
  assert.deepEqual(await readdir(join(home, '.glyphh')), ['install.json']) // no temporary left
})

test('install.json: missing, broken or partial reads as signed out', async () => {
  const home = await mkdtemp(join(tmpdir(), 'glyphh-'))
  const path = installPath(home)
  assert.equal(await readInstall(path), undefined)
  await writeInstall(path, { install_id: 'i1', token: 'x' })
  await writeFile(path, '{"install_id":"i1"}')
  assert.equal(await readInstall(path), undefined)
  await writeFile(path, 'not json')
  assert.equal(await readInstall(path), undefined)
})

test('machine id over Node: this machine has a stable value; only its hash is sent', async () => {
  const home = await mkdtemp(join(tmpdir(), 'glyphh-'))
  const first = await rawMachineValue(machineProbe(home))
  const again = await rawMachineValue(machineProbe(home))
  assert.ok(first.value)
  assert.deepEqual(again, first)
  assert.match(await hashMachine(first.value), /^[0-9a-f]{64}$/)
})
