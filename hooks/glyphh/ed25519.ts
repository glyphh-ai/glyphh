// Ed25519 signature checks (RFC 8032), on BigInt and the environment's
// SHA-512. The hooks environment's crypto.subtle has `digest` alone (no
// importKey or verify), so the curve is done here; checking only, plus the
// signer the tests use to play the server.

const P = 2n ** 255n - 19n
const L = 2n ** 252n + 27742317777372353535851937790883648493n

type Point = [bigint, bigint, bigint, bigint] // extended X, Y, Z, T

const mod = (a: bigint, m = P): bigint => {
  const r = a % m
  return r >= 0n ? r : r + m
}

function pow(base: bigint, exp: bigint): bigint {
  let r = 1n
  let b = mod(base)
  let e = exp
  while (e > 0n) {
    if (e & 1n) r = (r * b) % P
    b = (b * b) % P
    e >>= 1n
  }
  return r
}

const inv = (a: bigint) => pow(a, P - 2n)
const D = mod(-121665n * inv(121666n))
const SQRT_M1 = pow(2n, (P - 1n) / 4n)
const ZERO: Point = [0n, 1n, 1n, 0n]

function add(p: Point, q: Point): Point {
  const a = mod((p[1] - p[0]) * (q[1] - q[0]))
  const b = mod((p[1] + p[0]) * (q[1] + q[0]))
  const c = mod(2n * p[3] * q[3] * D)
  const d = mod(2n * p[2] * q[2])
  const e = b - a
  const f = d - c
  const g = d + c
  const h = b + a
  return [mod(e * f), mod(g * h), mod(f * g), mod(e * h)]
}

function mul(scalar: bigint, point: Point): Point {
  let q = ZERO
  let p = point
  let s = scalar
  while (s > 0n) {
    if (s & 1n) q = add(q, p)
    p = add(p, p)
    s >>= 1n
  }
  return q
}

function recoverX(y: bigint, sign: bigint): bigint | undefined {
  const y2 = (y * y) % P
  const x2 = mod((y2 - 1n) * inv(D * y2 + 1n))
  if (x2 === 0n) return sign ? undefined : 0n
  let x = pow(x2, (P + 3n) / 8n)
  if (mod(x * x - x2) !== 0n) x = (x * SQRT_M1) % P
  if (mod(x * x - x2) !== 0n) return undefined
  return (x & 1n) === sign ? x : P - x
}

const le = (bytes: Uint8Array): bigint => {
  let n = 0n
  for (let i = bytes.length - 1; i >= 0; i--) n = (n << 8n) | BigInt(bytes[i]!)
  return n
}

function le32(n: bigint): Uint8Array {
  const out = new Uint8Array(32)
  for (let i = 0; i < 32; i++) out[i] = Number((n >> BigInt(8 * i)) & 0xffn)
  return out
}

function decode(bytes: Uint8Array): Point | undefined {
  if (bytes.length !== 32) return undefined
  const copy = bytes.slice()
  const sign = BigInt(copy[31]! >> 7)
  copy[31]! &= 0x7f
  const y = le(copy)
  if (y >= P) return undefined
  const x = recoverX(y, sign)
  return x === undefined ? undefined : [x, y, 1n, (x * y) % P]
}

function encode(p: Point): Uint8Array {
  const zi = inv(p[2])
  const x = (p[0] * zi) % P
  const out = le32((p[1] * zi) % P)
  out[31]! |= Number(x & 1n) << 7
  return out
}

const BY = mod(4n * inv(5n))
const BASE: Point = [recoverX(BY, 0n)!, BY, 1n, mod(recoverX(BY, 0n)! * BY)]

async function sha512(...parts: Uint8Array[]): Promise<Uint8Array> {
  const all = new Uint8Array(parts.reduce((n, p) => n + p.length, 0))
  let at = 0
  for (const p of parts) {
    all.set(p, at)
    at += p.length
  }
  return new Uint8Array(await crypto.subtle.digest('SHA-512', all))
}

const same = (a: Uint8Array, b: Uint8Array) => a.length === b.length && a.every((v, i) => v === b[i])

/** Whether `signature` (64 bytes) is `publicKey`'s (32 bytes) over `message`. */
export async function verify(publicKey: Uint8Array, message: Uint8Array, signature: Uint8Array): Promise<boolean> {
  if (signature.length !== 64) return false
  const a = decode(publicKey)
  const r = decode(signature.slice(0, 32))
  const s = le(signature.slice(32))
  if (!a || !r || s >= L) return false
  const k = mod(le(await sha512(signature.slice(0, 32), publicKey, message)), L)
  return same(encode(mul(s, BASE)), encode(add(r, mul(k, a))))
}

/** The public key and a signer for a 32-byte seed (the tests' fake server). */
export async function keyPair(seed: Uint8Array) {
  const h = await sha512(seed)
  const head = h.slice(0, 32)
  head[0]! &= 248
  head[31]! &= 127
  head[31]! |= 64
  const a = le(head)
  const publicKey = encode(mul(a, BASE))
  const sign = async (message: Uint8Array): Promise<Uint8Array> => {
    const r = mod(le(await sha512(h.slice(32), message)), L)
    const big = encode(mul(r, BASE))
    const k = mod(le(await sha512(big, publicKey, message)), L)
    const out = new Uint8Array(64)
    out.set(big)
    out.set(le32(mod(r + k * a, L)), 32)
    return out
  }
  return { publicKey, sign }
}
