// ~/.glyphh/install.json from Node, kept as the mod keeps it (home.ts
// writeSecret): mode 0600 from the first byte, written to a temporary name
// and renamed into place, so no reader ever sees half a file.
import { execFile } from 'node:child_process'
import { chmod, mkdir, open, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'

import type { MachineProbe } from '../../hooks/glyphh/machine'
import type { Install } from './flow'

export const installPath = (home: string = homedir()) => join(home, '.glyphh', 'install.json')

export async function readInstall(path: string): Promise<Install | undefined> {
  try {
    const v = JSON.parse(await readFile(path, 'utf8')) as Partial<Install>
    return v.token && v.install_id ? { install_id: v.install_id, token: v.token } : undefined
  } catch {
    return undefined
  }
}

export async function writeInstall(path: string, install: Install): Promise<void> {
  await mkdir(dirname(path), { recursive: true, mode: 0o700 })
  const tmp = `${path}.${process.pid}.tmp`
  await rm(tmp, { force: true })
  const file = await open(tmp, 'wx', 0o600)
  try {
    await file.writeFile(`${JSON.stringify(install, null, 2)}\n`)
    await file.sync()
  } finally {
    await file.close()
  }
  await chmod(tmp, 0o600) // a umask cannot widen it, but be sure
  await rename(tmp, path)
}

/** The machine id's sources (hooks/glyphh/machine.ts), over Node. */
export function machineProbe(home: string = homedir()): MachineProbe {
  return {
    platform: process.platform,
    home,
    run: argv =>
      new Promise(done => {
        execFile(argv[0]!, argv.slice(1), { timeout: 5000, windowsHide: true }, (err, stdout) =>
          done({ exitCode: err ? Number((err as { code?: unknown }).code) || 1 : 0, stdout: String(stdout) }),
        )
      }),
    read: path => readFile(path, 'utf8').catch(() => undefined),
    write: async (path, text) => {
      await mkdir(dirname(path), { recursive: true, mode: 0o700 })
      await writeFile(path, text, { mode: 0o600 })
    },
  }
}
