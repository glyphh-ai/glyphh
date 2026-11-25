import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';

/**
 * Seals a value into an opaque string with AES-256-GCM: encrypted and authenticated,
 * so a cookie's contents can be neither read nor changed in the browser.
 * The `purpose` is bound in, so a value sealed for one cookie never opens as another.
 */
export function seal(value: unknown, key: Buffer, purpose: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(Buffer.from(purpose));
  const body = Buffer.concat([cipher.update(JSON.stringify(value), 'utf8'), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), body]).toString('base64url');
}

/** Opens a sealed value; anything tampered with, or sealed for another purpose, gives null. */
export function unseal<T>(sealed: string | undefined, key: Buffer, purpose: string): T | null {
  if (!sealed) return null;
  try {
    const raw = Buffer.from(sealed, 'base64url');
    if (raw.length < 29) return null;
    const decipher = createDecipheriv('aes-256-gcm', key, raw.subarray(0, 12));
    decipher.setAAD(Buffer.from(purpose));
    decipher.setAuthTag(raw.subarray(12, 28));
    const body = Buffer.concat([decipher.update(raw.subarray(28)), decipher.final()]);
    return JSON.parse(body.toString('utf8')) as T;
  } catch {
    return null;
  }
}

export function randomToken(bytes = 32): string {
  return randomBytes(bytes).toString('base64url');
}

/** PKCE: a verifier and its S256 challenge. */
export function pkce(): { verifier: string; challenge: string } {
  const verifier = randomToken(48);
  const challenge = createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}
