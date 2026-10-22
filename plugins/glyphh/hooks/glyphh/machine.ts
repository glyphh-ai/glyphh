// This machine's stable id, sent with every device-flow sign-in so the server
// keys installs by machine: the hardware id (macOS IOPlatformUUID, Linux
// machine-id, Windows MachineGuid / csproduct UUID), else the primary network
// interface's MAC, else a random id kept once in ~/.glyphh/machine.json.
// Only sha256("glyphh:" + value) leaves the machine, never the value itself.
// Shared: the mod hands it a probe over its Host, the MCP server one over Node.

export type MachineProbe = {
  /** `darwin`, `linux`, `win32`; unknown: every source is tried in turn. */
  platform?: string
  home?: string
  run(argv: readonly string[]): Promise<{ exitCode: number; stdout: string } | undefined>
  read(path: string): Promise<string | undefined>
  write(path: string, text: string): Promise<void>
}

export type MachineSource = 'hardware' | 'mac' | 'saved'

const ZERO_MAC = /^(00[:-]){5}00$/

const ok = async (p: MachineProbe, argv: readonly string[]) => {
  const r = await p.run(argv).catch(() => undefined)
  return r && r.exitCode === 0 ? r.stdout : undefined
}

async function macos(p: MachineProbe) {
  const out = await ok(p, ['/usr/sbin/ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'])
  return out?.match(/"IOPlatformUUID"\s*=\s*"([^"]+)"/)?.[1]
}

async function linux(p: MachineProbe) {
  for (const path of ['/etc/machine-id', '/var/lib/dbus/machine-id']) {
    const id = (await p.read(path).catch(() => undefined))?.trim()
    if (id) return id
  }
  return undefined
}

async function windows(p: MachineProbe) {
  const reg = await ok(p, ['reg', 'query', 'HKLM\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'])
  const guid = reg?.match(/MachineGuid\s+REG_SZ\s+(\S+)/)?.[1]
  if (guid) return guid
  const wmic = await ok(p, ['wmic', 'csproduct', 'get', 'uuid'])
  return wmic?.split(/\r?\n/).map(l => l.trim()).find(l => /^[0-9A-F-]{32,36}$/i.test(l) && !/^[F-]+$/i.test(l))
}

/** The hardware id for the platform (all of them in turn when it is unknown). */
export async function hardwareId(p: MachineProbe): Promise<string | undefined> {
  const by: Record<string, (p: MachineProbe) => Promise<string | undefined>> = { darwin: macos, linux, win32: windows }
  const order = p.platform && by[p.platform] ? [by[p.platform]!] : [macos, linux, windows]
  for (const source of order) {
    const id = (await source(p).catch(() => undefined))?.trim()
    if (id) return id
  }
  return undefined
}

// The default route's interface, then its address (macOS, Linux); Windows' getmac.
const PRIMARY_MAC = [
  'i=$(route -n get default 2>/dev/null | awk \'/interface:/{print $2; exit}\')',
  '[ -n "$i" ] || i=$(ip route show default 2>/dev/null | awk \'{for(k=1;k<NF;k++) if($k=="dev"){print $(k+1); exit}}\')',
  '[ -n "$i" ] || exit 1',
  'cat "/sys/class/net/$i/address" 2>/dev/null || ifconfig "$i" 2>/dev/null | awk \'/ether /{print $2; exit}\'',
].join('\n')

/** The primary network interface's MAC address, lower case. */
export async function primaryMac(p: MachineProbe): Promise<string | undefined> {
  const out = p.platform === 'win32' ? await ok(p, ['getmac', '/fo', 'csv', '/nh']) : await ok(p, ['/bin/sh', '-c', PRIMARY_MAC])
  const mac = out?.match(/([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}/)?.[0]?.toLowerCase().replaceAll('-', ':')
  return mac && !ZERO_MAC.test(mac) ? mac : undefined
}

/** A random id, made once and kept in ~/.glyphh/machine.json. */
export async function savedId(p: MachineProbe): Promise<string> {
  const path = p.home ? `${p.home.replace(/\/$/, '')}/.glyphh/machine.json` : undefined
  if (path) {
    try {
      const kept = JSON.parse((await p.read(path)) ?? '') as { id?: unknown }
      if (typeof kept.id === 'string' && kept.id) return kept.id
    } catch {
      // missing or not JSON: make one
    }
  }
  const id = crypto.randomUUID()
  if (path) await p.write(path, `${JSON.stringify({ id }, null, 2)}\n`).catch(() => undefined)
  return id
}

export async function rawMachineValue(p: MachineProbe): Promise<{ source: MachineSource; value: string }> {
  const hw = await hardwareId(p)
  if (hw) return { source: 'hardware', value: hw }
  const mac = await primaryMac(p).catch(() => undefined)
  if (mac) return { source: 'mac', value: mac }
  return { source: 'saved', value: await savedId(p) }
}

/** sha256("glyphh:" + value), hex: 64 characters. */
export async function hashMachine(value: string): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`glyphh:${value}`)))
  return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
}

let cached: Promise<string> | undefined

/** The id sent as `machine_id`, worked out once per process. */
export function machineId(p: MachineProbe): Promise<string> {
  cached ??= rawMachineValue(p).then(r => hashMachine(r.value))
  cached.catch(() => (cached = undefined))
  return cached
}

export function forgetMachineId() {
  cached = undefined
}
