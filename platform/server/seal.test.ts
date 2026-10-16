import { pkce, seal, unseal } from './seal.js';
import { createHash } from 'node:crypto';

const key = Buffer.alloc(32, 1);

describe('seal', () => {
  it('opens what it sealed', () => {
    expect(unseal(seal({ a: 1 }, key, 'p'), key, 'p')).toEqual({ a: 1 });
  });

  it('never shows the value in the sealed text', () => {
    expect(seal({ token: 'secret-token' }, key, 'p')).not.toContain('secret');
  });

  it('refuses another key, another purpose, tampering and junk', () => {
    const sealed = seal({ a: 1 }, key, 'p');
    expect(unseal(sealed, Buffer.alloc(32, 2), 'p')).toBeNull();
    expect(unseal(sealed, key, 'q')).toBeNull();
    expect(unseal(`${sealed.slice(0, -2)}AA`, key, 'p')).toBeNull();
    expect(unseal('short', key, 'p')).toBeNull();
    expect(unseal(undefined, key, 'p')).toBeNull();
  });
});

describe('pkce', () => {
  it('gives an S256 challenge of its verifier', () => {
    const { verifier, challenge } = pkce();
    expect(verifier).toMatch(/^[A-Za-z0-9_-]{43,128}$/);
    expect(challenge).toBe(createHash('sha256').update(verifier).digest('base64url'));
  });
});
