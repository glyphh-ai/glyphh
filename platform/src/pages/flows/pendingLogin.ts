/**
 * The platform signs in to the server like any other client, so its own log-in passes through the same
 * /authorize and /allow pages a third-party client would. When the person has just chosen a provider on
 * /login, those two steps are the platform's own and are taken for them, so they pick a provider once.
 * The note lives for this tab and these few minutes only.
 */
const key = 'glyphh.login';
const maxAgeMs = 10 * 60 * 1000;

type Pending = { provider: string; at: number };

export function rememberLogin(provider: string) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ provider, at: Date.now() } satisfies Pending));
  } catch {
    // Without storage the person picks the provider again on /authorize; nothing breaks.
  }
}

export function pendingLogin(): string | null {
  try {
    const pending = JSON.parse(sessionStorage.getItem(key) ?? 'null') as Pending | null;
    if (!pending || Date.now() - pending.at > maxAgeMs) return null;
    return pending.provider;
  } catch {
    return null;
  }
}

export function forgetLogin() {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // Nothing to forget.
  }
}
