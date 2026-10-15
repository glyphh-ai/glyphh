export type Call = [string, Record<string, unknown>]
export function keyCalls(cmd: { key: string; ctrl?: boolean; shift?: boolean; meta?: boolean; alt?: boolean }): Call[]
export function addressOf(text: string): string
export function mouseCall(cmd: { action: 'down' | 'up' | 'move'; x?: unknown; y?: unknown; button?: string; clicks?: number; mods?: number }): Call
export function nulFramer(onMessage: (msg: unknown) => void): (chunk: string) => void
