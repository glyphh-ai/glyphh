/**
 * The Marketplace's data: what is in the public repository github.com/glyphh-ai/plugins, read here (never by the
 * browser) and kept in memory. One call to GitHub's API lists every path; each file read after that comes from
 * raw.githubusercontent.com. No token: the repository is public. The platform only shows it; a plugin is installed
 * in Claude.
 */

export const MARKETPLACE_REPO = 'glyphh-ai/plugins';
const REPO_URL = `https://github.com/${MARKETPLACE_REPO}`;
const TREE_URL = `https://api.github.com/repos/${MARKETPLACE_REPO}/git/trees/HEAD?recursive=1`;
const RAW_URL = `https://raw.githubusercontent.com/${MARKETPLACE_REPO}/HEAD`;
const USER_AGENT = 'glyphh-platform (+https://platform.glyphh.ai)';

/** How long an answer is served before the repository is read again. */
export const MARKETPLACE_TTL_MS = 10 * 60 * 1000;
/** How long GitHub is left alone after it could not be read. */
const RETRY_MS = 60 * 1000;
/** The most of one file that is kept, in characters: a README or a skill's body. */
const MAX_TEXT = 60_000;
/** The most skills, commands or agents read for one plugin. */
const MAX_ITEMS = 60;

export type MarketItem = { name: string; description: string; url: string };
export type MarketSkill = MarketItem & { body: string };
export type MarketPlugin = {
  name: string;
  description: string;
  version: string | null;
  author: { name: string; url: string | null } | null;
  category: string | null;
  keywords: string[];
  license: string | null;
  homepage: string | null;
  /** The plugin's folder in the repository, or its own repository when it lives elsewhere. */
  url: string;
  /** It lives in another repository: shown from marketplace.json alone. */
  external: boolean;
  readme: string | null;
  skills: MarketSkill[];
  commands: MarketItem[];
  agents: MarketItem[];
  /** The events its hooks run on. */
  hooks: string[];
  /** Its MCP servers, by name. */
  connectors: MarketItem[];
};
export type Marketplace = {
  /** The marketplace's name, as `/plugin install <plugin>@<name>` takes it. */
  name: string;
  owner: string | null;
  description: string | null;
  version: string | null;
  repo: string;
  url: string;
  plugins: MarketPlugin[];
  fetched_at: string;
  /** GitHub could not be read just now: this is the last answer kept. */
  stale: boolean;
};

export class MarketplaceError extends Error {}

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json => typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value.trim() : null);
const words = (value: unknown): string[] => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string' && v.trim() !== '').map((v) => v.trim()) : []);
const clip = (value: string) => (value.length > MAX_TEXT ? `${value.slice(0, MAX_TEXT)}\n\n…` : value);

function parseJson(raw: string | null): Json | null {
  if (raw === null) return null;
  try {
    const value: unknown = JSON.parse(raw);
    return isObject(value) ? value : null;
  } catch {
    return null;
  }
}

/**
 * A markdown file's front matter (the `key: value` lines between the first two `---`) and the text after it. Reads
 * plain, quoted and folded (`>`, `|`) values; anything else in the YAML is left alone.
 */
export function frontMatter(raw: string): { fields: Record<string, string>; body: string } {
  const source = raw.replace(/^﻿/, '').replace(/\r\n/g, '\n');
  const fields: Record<string, string> = {};
  if (!source.startsWith('---\n')) return { fields, body: source };
  const end = source.indexOf('\n---', 3);
  if (end < 0) return { fields, body: source };
  const lines = source.slice(4, end).split('\n');
  for (let i = 0; i < lines.length; i++) {
    const found = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(lines[i]!);
    if (!found) continue;
    let value = found[2]!.trim();
    if (/^[>|][+-]?$/.test(value) || value === '') {
      const folded: string[] = [];
      while (i + 1 < lines.length && (/^\s+\S/.test(lines[i + 1]!) || lines[i + 1]!.trim() === '')) folded.push(lines[++i]!.trim());
      value = folded.join(value.startsWith('|') ? '\n' : ' ').trim();
    } else if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.length > 1 ? value.slice(1, -1) : '';
    }
    fields[found[1]!.toLowerCase()] = value;
  }
  const rest = source.slice(end + 4);
  return { fields, body: rest.replace(/^[^\n]*\n?/, '').replace(/^\n+/, '') };
}

/** A plugin's folder from its `source` in marketplace.json: a relative path inside the repository, or null. */
export function folderOf(source: unknown, root: string | null): string | null {
  if (typeof source !== 'string') return null;
  let path = source.trim();
  if (/^[a-z][a-z0-9+.-]*:/i.test(path) || path.startsWith('/')) return null;
  if (!path.startsWith('./') && root) path = `${root.replace(/\/+$/, '')}/${path}`;
  const parts = path.split('/').filter((part) => part !== '' && part !== '.');
  if (parts.includes('..')) return null;
  return parts.join('/');
}

/** Where a plugin that lives elsewhere is: its own repository, as its `source` object or its other fields say. */
function elsewhere(source: unknown, entry: Json): string {
  const web = (value: unknown) => {
    const url = text(value)?.replace(/\.git$/, '');
    return url && /^https:\/\//.test(url) ? url : null;
  };
  if (isObject(source)) {
    const repo = text(source.repo);
    if (repo && /^[\w.-]+\/[\w.-]+$/.test(repo)) return `https://github.com/${repo}`;
    const url = web(source.url);
    if (url) return url;
  }
  return web(source) ?? web(entry.repository) ?? web(entry.homepage) ?? REPO_URL;
}

const tree = (path: string) => `${REPO_URL}/tree/HEAD/${path.split('/').map(encodeURIComponent).join('/')}`;
const blob = (path: string) => `${REPO_URL}/blob/HEAD/${path.split('/').map(encodeURIComponent).join('/')}`;

function author(value: unknown): MarketPlugin['author'] {
  if (typeof value === 'string' && value.trim()) return { name: value.trim(), url: null };
  if (!isObject(value)) return null;
  const name = text(value.name);
  const url = text(value.url);
  return name ? { name, url: url && /^https?:\/\//.test(url) ? url : null } : null;
}

/** The names of the MCP servers `.mcp.json` declares: `{mcpServers: {name: …}}`, or the names themselves. */
function serverNames(value: unknown): string[] {
  if (!isObject(value)) return [];
  return Object.keys(isObject(value.mcpServers) ? value.mcpServers : value);
}

type Deps = { fetch?: typeof fetch; now?: () => number };

export function createMarketplace({ fetch: fetcher = fetch, now = Date.now }: Deps = {}) {
  let kept: { value: Marketplace; at: number } | null = null;
  let reading: Promise<Marketplace> | null = null;
  let failed: { error: MarketplaceError; at: number } | null = null;

  const headers = { 'user-agent': USER_AGENT };

  /** Every file path in the repository; none when it is empty (GitHub answers 409) or not there yet (404). */
  async function paths(): Promise<Set<string>> {
    const answer = await fetcher(TREE_URL, { headers: { ...headers, accept: 'application/vnd.github+json' } });
    if (answer.status === 409 || answer.status === 404) return new Set();
    if (!answer.ok) throw new MarketplaceError(`GitHub answered ${answer.status} for the repository's files.`);
    const body = (await answer.json()) as { tree?: Array<{ path?: unknown; type?: unknown }> };
    return new Set((body.tree ?? []).filter((entry) => entry.type === 'blob' && typeof entry.path === 'string').map((entry) => entry.path as string));
  }

  /** One file's text; null when it is not there or could not be read (the plugin is shown without it). */
  async function file(path: string): Promise<string | null> {
    try {
      const answer = await fetcher(`${RAW_URL}/${path.split('/').map(encodeURIComponent).join('/')}`, { headers });
      return answer.ok ? await answer.text() : null;
    } catch {
      return null;
    }
  }

  async function plugin(entry: Json, files: Set<string>, root: string | null): Promise<MarketPlugin | null> {
    const folder = folderOf(entry.source, root);
    const has = (path: string) => files.has(path);
    const at = (path: string) => (folder ? `${folder}/${path}` : path);
    const manifest = folder !== null && has(at('.claude-plugin/plugin.json')) ? parseJson(await file(at('.claude-plugin/plugin.json'))) : null;
    const name = text(entry.name) ?? text(manifest?.name) ?? folder?.split('/').at(-1) ?? null;
    if (!name) return null;

    const base: MarketPlugin = {
      name,
      description: text(entry.description) ?? text(manifest?.description) ?? '',
      version: text(entry.version) ?? text(manifest?.version),
      author: author(entry.author) ?? author(manifest?.author),
      category: text(entry.category) ?? text(manifest?.category),
      keywords: [...new Set([...words(entry.keywords), ...words(entry.tags), ...words(manifest?.keywords)])],
      license: text(entry.license) ?? text(manifest?.license),
      homepage: text(entry.homepage) ?? text(manifest?.homepage),
      url: folder === null ? elsewhere(entry.source, entry) : folder ? tree(folder) : REPO_URL,
      external: folder === null,
      readme: null,
      skills: [],
      commands: [],
      agents: [],
      hooks: [],
      connectors: [],
    };
    if (folder === null) return base;

    const under = (dir: string, match: RegExp) =>
      [...files]
        .filter((path) => path.startsWith(`${at(dir)}/`) && match.test(path.slice(at(dir).length + 1)))
        .sort()
        .slice(0, MAX_ITEMS);
    const described = async (path: string, fallback: string): Promise<MarketSkill> => {
      const { fields, body } = frontMatter((await file(path)) ?? '');
      return { name: fields.name || fallback, description: fields.description ?? '', url: blob(path), body: clip(body.trim()) };
    };
    const brief = ({ name: n, description, url }: MarketSkill): MarketItem => ({ name: n, description, url });
    const stem = (path: string) => path.split('/').at(-1)!.replace(/\.md$/i, '');

    const [readme, skills, commands, agents, hooksFile, mcpFile] = await Promise.all([
      has(at('README.md')) ? file(at('README.md')) : null,
      Promise.all(under('skills', /^[^/]+\/SKILL\.md$/).map((path) => described(path, path.split('/').at(-2)!))),
      Promise.all(under('commands', /^[^/]+\.md$/i).map((path) => described(path, stem(path)))),
      Promise.all(under('agents', /^[^/]+\.md$/i).map((path) => described(path, stem(path)))),
      has(at('hooks/hooks.json')) ? file(at('hooks/hooks.json')) : null,
      has(at('.mcp.json')) ? file(at('.mcp.json')) : null,
    ]);

    // The events are under `hooks` in hooks/hooks.json, or in the plugin's own manifest.
    const eventsOf = (value: unknown) => (isObject(value) ? (isObject(value.hooks) ? value.hooks : value) : null);
    const hookEvents = eventsOf(parseJson(hooksFile)) ?? eventsOf(manifest?.hooks) ?? {};
    const declared = manifest?.mcpServers;
    const servers = new Map<string, string>();
    for (const server of isObject(declared) ? Object.keys(declared) : []) servers.set(server, blob(at('.claude-plugin/plugin.json')));
    for (const server of serverNames(parseJson(mcpFile))) if (!servers.has(server)) servers.set(server, blob(at('.mcp.json')));

    return {
      ...base,
      readme: readme === null ? null : clip(readme),
      skills,
      commands: commands.map(brief),
      agents: agents.map(brief),
      hooks: Object.keys(hookEvents),
      connectors: [...servers].map(([server, url]) => ({ name: server, description: '', url })),
    };
  }

  async function read(): Promise<Marketplace> {
    const files = await paths();
    const listed = files.has('.claude-plugin/marketplace.json');
    const raw = listed ? await file('.claude-plugin/marketplace.json') : null;
    if (listed && raw === null) throw new MarketplaceError('The marketplace’s list could not be read from GitHub.');
    const manifest = parseJson(raw) ?? {};
    const metadata = isObject(manifest.metadata) ? manifest.metadata : {};
    const root = text(metadata.pluginRoot);

    // What marketplace.json lists; without one, every folder that holds a plugin's own manifest.
    const entries: Json[] = Array.isArray(manifest.plugins)
      ? manifest.plugins.filter(isObject)
      : [...files]
          .filter((path) => path.endsWith('/.claude-plugin/plugin.json'))
          .sort()
          .map((path) => ({ source: `./${path.slice(0, -'/.claude-plugin/plugin.json'.length)}` }));

    const plugins = (await Promise.all(entries.map((entry) => plugin(entry, files, root)))).filter((p): p is MarketPlugin => p !== null);
    return {
      name: text(manifest.name) ?? 'plugins',
      owner: author(manifest.owner)?.name ?? null,
      description: text(metadata.description) ?? text(manifest.description),
      version: text(metadata.version) ?? text(manifest.version),
      repo: MARKETPLACE_REPO,
      url: REPO_URL,
      plugins,
      fetched_at: new Date(now()).toISOString(),
      stale: false,
    };
  }

  /**
   * The marketplace: the answer kept while it is fresh, else read again (one read at a time). When GitHub cannot be
   * read, the last answer kept, marked stale; with none kept, the error.
   */
  async function load(): Promise<Marketplace> {
    if (kept && now() - kept.at < MARKETPLACE_TTL_MS) return kept.value;
    // After a failure GitHub is left alone for a minute, however many pages ask.
    if (failed && now() - failed.at < RETRY_MS) return lastKept(failed.error);
    reading ??= read()
      .then((value) => {
        kept = { value, at: now() };
        failed = null;
        return value;
      })
      .finally(() => {
        reading = null;
      });
    try {
      return await reading;
    } catch (error) {
      failed = { error: error instanceof MarketplaceError ? error : new MarketplaceError('GitHub could not be reached.'), at: now() };
      return lastKept(failed.error);
    }
  }

  function lastKept(error: MarketplaceError): Marketplace {
    if (kept) return { ...kept.value, stale: true };
    throw error;
  }

  return { load };
}

export type MarketplaceReader = ReturnType<typeof createMarketplace>;
