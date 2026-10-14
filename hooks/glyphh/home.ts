// ~/.glyphh: the files this machine keeps. Nothing here goes to the cloud.
import type { Host } from './host'

/** `~/.glyphh`, absolute; undefined where HOME is not known. */
export async function glyphhDir(gh: Host): Promise<string | undefined> {
  const home = await gh.env.home().catch(() => undefined)
  return home ? `${home.replace(/\/$/, '')}/.glyphh` : undefined
}

export async function glyphhPath(gh: Host, name: string): Promise<string | undefined> {
  const dir = await glyphhDir(gh)
  return dir ? `${dir}/${name}` : undefined
}

/** A JSON file's value, or undefined when it is missing or not JSON. */
export async function readJson<T>(path: string | undefined, gh: Host): Promise<T | undefined> {
  if (!path) return undefined
  try {
    const text = await gh.fs.read(path)
    return typeof text === 'string' ? (JSON.parse(text) as T) : undefined
  } catch {
    return undefined
  }
}

export async function writeJson(gh: Host, path: string, value: unknown): Promise<void> {
  await gh.fs.write(path, `${JSON.stringify(value, null, 2)}\n`)
}

/** A secret's file: written by a shell under umask 077 to a temporary name,
 *  then moved into place, so it is never readable by others, even briefly.
 *  The text goes on stdin, never on a command line. */
export async function writeSecret(gh: Host, path: string, value: unknown): Promise<void> {
  const dir = path.slice(0, path.lastIndexOf('/'))
  const script = 'umask 077 && mkdir -p "$1" && cat > "$2.tmp" && chmod 600 "$2.tmp" && mv -f "$2.tmp" "$2"'
  const r = await gh.process.run(['/bin/sh', '-c', script, 'sh', dir, path], {
    stdin: `${JSON.stringify(value, null, 2)}\n`,
  })
  if (r.exitCode !== 0) throw new Error(`could not write ${path}: ${r.stderr.trim().slice(0, 120)}`)
}

export async function removeFile(gh: Host, path: string): Promise<void> {
  const r = await gh.process.run(['/bin/rm', '-f', path])
  if (r.exitCode !== 0) throw new Error(`could not remove ${path}: ${r.stderr.trim().slice(0, 120)}`)
}
