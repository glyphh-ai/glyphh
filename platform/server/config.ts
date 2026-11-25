export type Config = {
  /** The Glyphh server: the API and the authorization server. */
  serverUrl: string;
  /** Ada Cloud's API, a second host of the server (`GLYPHH_ADA_URL`, https://ada.glyphh.ai): called with the same sign-in. */
  adaUrl: string;
  /** This app's own address; OAuth returns to {platformUrl}/auth/callback. */
  platformUrl: string;
  clientId: string;
  clientSecret: string;
  /** The name the platform registered under, so its own consent pages can be recognised. */
  clientName: string;
  /** 32 bytes that seal the session cookie. */
  sessionKey: Buffer;
  /** Cookies are Secure whenever the platform is served over https. */
  secureCookies: boolean;
};

export class ConfigError extends Error {}

function required(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name]?.trim();
  if (!value) throw new ConfigError(`${name} is not set. See .env.example.`);
  return value;
}

export function readConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const sessionKey = Buffer.from(required(env, 'SESSION_SECRET'), 'base64');
  if (sessionKey.length < 32) throw new ConfigError('SESSION_SECRET must be at least 32 bytes, base64 encoded.');
  const platformUrl = required(env, 'PLATFORM_URL').replace(/\/$/, '');
  return {
    serverUrl: required(env, 'GLYPHH_SERVER_URL').replace(/\/$/, ''),
    adaUrl: (env.GLYPHH_ADA_URL?.trim() || 'https://ada.glyphh.ai').replace(/\/$/, ''),
    platformUrl,
    clientId: required(env, 'PLATFORM_CLIENT_ID'),
    clientSecret: required(env, 'PLATFORM_CLIENT_SECRET'),
    clientName: env.PLATFORM_CLIENT_NAME?.trim() || 'Glyphh',
    sessionKey: sessionKey.subarray(0, 32),
    secureCookies: platformUrl.startsWith('https://'),
  };
}
