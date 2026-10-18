import { ConfigError, readConfig } from './config.js';

const env = {
  GLYPHH_SERVER_URL: 'https://api.glyphh.ai/',
  PLATFORM_URL: 'https://platform.glyphh.ai/',
  PLATFORM_CLIENT_ID: 'id',
  PLATFORM_CLIENT_SECRET: 'secret',
  SESSION_SECRET: Buffer.alloc(32, 9).toString('base64'),
};

describe('readConfig', () => {
  it('reads the settings, trimming trailing slashes', () => {
    const config = readConfig(env);
    expect(config.serverUrl).toBe('https://api.glyphh.ai');
    expect(config.platformUrl).toBe('https://platform.glyphh.ai');
    expect(config.secureCookies).toBe(true);
    expect(config.clientName).toBe('Glyphh');
    expect(config.sessionKey).toHaveLength(32);
  });

  it('uses plain cookies on http, for local development', () => {
    expect(readConfig({ ...env, PLATFORM_URL: 'http://localhost:3000' }).secureCookies).toBe(false);
  });

  it('names a missing setting', () => {
    expect(() => readConfig({ ...env, PLATFORM_CLIENT_ID: '' })).toThrow(new ConfigError('PLATFORM_CLIENT_ID is not set. See .env.example.'));
  });

  it('refuses a short session secret', () => {
    expect(() => readConfig({ ...env, SESSION_SECRET: Buffer.alloc(16).toString('base64') })).toThrow(/at least 32 bytes/);
  });
});
