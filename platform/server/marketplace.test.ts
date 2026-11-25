import { createApp } from './app.js';
import { createMarketplace, folderOf, frontMatter, MARKETPLACE_TTL_MS, type Marketplace } from './marketplace.js';
import { seal } from './seal.js';
import { testConfig } from './testing.js';

const TREE = 'https://api.github.com/repos/glyphh-ai/plugins/git/trees/HEAD?recursive=1';
const RAW = 'https://raw.githubusercontent.com/glyphh-ai/plugins/HEAD/';
const repo = 'https://github.com/glyphh-ai/plugins';

type Files = Record<string, string>;

/**
 * GitHub, faked: the repository's files by path, answered at the two addresses the platform reads. `tree` set to a
 * status answers that for the list of files; `down` fails every request. Every request is recorded: nothing here
 * reaches the network.
 */
function github(files: Files) {
  const seen: Array<{ url: string; headers: Headers }> = [];
  const state = { files, tree: 200 as number, down: false };
  const fetcher = (async (input: Request | string | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    seen.push({ url, headers: new Headers(init?.headers) });
    if (state.down) throw new TypeError('fetch failed');
    if (url === TREE) {
      if (state.tree !== 200) return Response.json({ message: 'Git Repository is empty.' }, { status: state.tree });
      const dirs = new Set<string>();
      for (const path of Object.keys(state.files)) path.split('/').slice(0, -1).forEach((_, i, parts) => dirs.add(parts.slice(0, i + 1).join('/')));
      return Response.json({
        sha: 'abc',
        truncated: false,
        tree: [...[...dirs].map((path) => ({ path, type: 'tree' })), ...Object.keys(state.files).map((path) => ({ path, type: 'blob' }))],
      });
    }
    if (url.startsWith(RAW)) {
      const path = decodeURIComponent(url.slice(RAW.length));
      return path in state.files ? new Response(state.files[path]) : new Response('404: Not Found', { status: 404 });
    }
    throw new Error(`An address the platform should not call: ${url}`);
  }) as typeof fetch;
  return { fetch: fetcher, seen, state };
}

const json = (value: unknown) => JSON.stringify(value);

/** The repository as it will be: one marketplace, one plugin with everything a plugin can hold. */
const stocked = (): Files => ({
  'README.md': '# Glyphh plugins',
  '.claude-plugin/marketplace.json': json({
    name: 'glyphh',
    owner: { name: 'Glyphh', email: 'support@glyphh.ai' },
    metadata: { description: 'Plugins for Claude from Glyphh.', version: '1.0.0' },
    plugins: [
      { name: 'resume-screener', source: './plugins/resume-screener', description: 'Screens résumés.', version: '1.2.0', author: { name: 'Glyphh' }, category: 'recruiting', keywords: ['hiring'] },
      { name: 'ticket-router', source: { source: 'github', repo: 'acme/ticket-router' }, description: 'Routes tickets.', author: { name: 'Acme' } },
    ],
  }),
  'plugins/resume-screener/.claude-plugin/plugin.json': json({
    name: 'resume-screener',
    version: '1.0.0',
    description: 'From the plugin’s own manifest.',
    author: { name: 'Glyphh Inc', url: 'https://glyphh.ai' },
    homepage: 'https://glyphh.ai',
    license: 'MIT',
    keywords: ['ada', 'hiring'],
    mcpServers: { glyphh: { type: 'http', url: 'https://api.glyphh.ai/mcp' } },
  }),
  'plugins/resume-screener/README.md': '# Resume screener\n\nReads each résumé.',
  'plugins/resume-screener/skills/screen-resume/SKILL.md': '---\nname: screen-resume\ndescription: >\n  Use when someone asks to screen\n  a résumé for a role.\nallowed-tools: Read\n---\n\n## Steps\n\n1. Read the résumé.\n',
  'plugins/resume-screener/skills/screen-resume/reference.md': 'Not a skill.',
  'plugins/resume-screener/skills/explain/SKILL.md': 'No front matter here.',
  'plugins/resume-screener/commands/screen.md': '---\ndescription: "Screen the résumés in a folder."\n---\nDo it.',
  'plugins/resume-screener/agents/screener.md': "---\nname: screener\ndescription: 'Works through a stack.'\n---\nYou are a screener.",
  'plugins/resume-screener/hooks/hooks.json': json({ hooks: { SessionStart: [{ hooks: [] }], PreToolUse: [] } }),
  'plugins/resume-screener/.mcp.json': json({ mcpServers: { glyphh: {}, files: { command: 'npx' } } }),
});

describe('the marketplace, read from GitHub', () => {
  it('reads the list and each plugin’s files, in one call for the paths and one per file, with a User-Agent and no token', async () => {
    const hub = github(stocked());
    const market = await createMarketplace({ fetch: hub.fetch, now: () => Date.UTC(2026, 10, 24, 9) }).load();

    expect(market).toMatchObject({
      name: 'glyphh',
      owner: 'Glyphh',
      description: 'Plugins for Claude from Glyphh.',
      version: '1.0.0',
      repo: 'glyphh-ai/plugins',
      url: repo,
      fetched_at: '2026-11-24T09:00:00.000Z',
      stale: false,
    });
    const [plugin, other] = market.plugins;
    // The marketplace's own words for a plugin win; the plugin's manifest fills in what it leaves out.
    expect(plugin).toMatchObject({
      name: 'resume-screener',
      description: 'Screens résumés.',
      version: '1.2.0',
      author: { name: 'Glyphh', url: null },
      category: 'recruiting',
      keywords: ['hiring', 'ada'],
      license: 'MIT',
      homepage: 'https://glyphh.ai',
      url: `${repo}/tree/HEAD/plugins/resume-screener`,
      external: false,
      readme: '# Resume screener\n\nReads each résumé.',
      hooks: ['SessionStart', 'PreToolUse'],
    });
    expect(plugin!.skills).toEqual([
      // No front matter: the folder's name, and the whole file as its body.
      { name: 'explain', description: '', url: `${repo}/blob/HEAD/plugins/resume-screener/skills/explain/SKILL.md`, body: 'No front matter here.' },
      {
        name: 'screen-resume',
        description: 'Use when someone asks to screen a résumé for a role.',
        url: `${repo}/blob/HEAD/plugins/resume-screener/skills/screen-resume/SKILL.md`,
        body: '## Steps\n\n1. Read the résumé.',
      },
    ]);
    expect(plugin!.commands).toEqual([{ name: 'screen', description: 'Screen the résumés in a folder.', url: `${repo}/blob/HEAD/plugins/resume-screener/commands/screen.md` }]);
    expect(plugin!.agents).toEqual([{ name: 'screener', description: 'Works through a stack.', url: `${repo}/blob/HEAD/plugins/resume-screener/agents/screener.md` }]);
    // The plugin's manifest and .mcp.json together, each server once.
    expect(plugin!.connectors).toEqual([
      { name: 'glyphh', description: '', url: `${repo}/blob/HEAD/plugins/resume-screener/.claude-plugin/plugin.json` },
      { name: 'files', description: '', url: `${repo}/blob/HEAD/plugins/resume-screener/.mcp.json` },
    ]);

    // A plugin kept in another repository: what the list says of it, and where it is.
    expect(other).toMatchObject({ name: 'ticket-router', description: 'Routes tickets.', author: { name: 'Acme', url: null }, external: true, url: 'https://github.com/acme/ticket-router' });
    expect(other).toMatchObject({ readme: null, skills: [], commands: [], agents: [], hooks: [], connectors: [] });

    expect(hub.seen.filter((r) => r.url === TREE)).toHaveLength(1);
    expect(hub.seen.map((r) => r.url).filter((url) => url.startsWith(RAW)).sort()).toEqual(
      ['.claude-plugin/marketplace.json', ...Object.keys(stocked()).filter((path) => path.startsWith('plugins/') && !path.endsWith('reference.md'))].map((path) => `${RAW}${path}`).sort(),
    );
    for (const request of hub.seen) {
      expect(request.headers.get('user-agent')).toMatch(/glyphh-platform/);
      expect(request.headers.get('authorization')).toBeNull();
    }
  });

  it.each([409, 404])('is empty, not an error, while the repository is empty (GitHub answers %s)', async (status) => {
    const hub = github({});
    hub.state.tree = status;
    const market = await createMarketplace({ fetch: hub.fetch }).load();
    expect(market).toMatchObject({ name: 'plugins', owner: null, plugins: [], stale: false });
    expect(hub.seen).toHaveLength(1);
  });

  it('is empty for a repository with files and no plugin yet', async () => {
    const market = await createMarketplace({ fetch: github({ 'README.md': '# Soon', LICENSE: 'MIT' }).fetch }).load();
    expect(market.plugins).toEqual([]);
  });

  it('finds the plugins by their own manifests when there is no list', async () => {
    const files = stocked();
    delete files['.claude-plugin/marketplace.json'];
    const market = await createMarketplace({ fetch: github(files).fetch }).load();
    expect(market.name).toBe('plugins');
    expect(market.plugins.map((p) => [p.name, p.description, p.version, p.author?.name])).toEqual([['resume-screener', 'From the plugin’s own manifest.', '1.0.0', 'Glyphh Inc']]);
  });

  it('shows a plugin whose files are missing or broken from what is left', async () => {
    const hub = github({
      '.claude-plugin/marketplace.json': json({
        plugins: [
          { name: 'bare', source: './plugins/bare' },
          { name: 'broken', source: './plugins/broken', description: 'Still listed.' },
          { source: './plugins/unnamed' },
          { name: 'outside', source: '../elsewhere' },
          { name: 'by-url', source: { source: 'url', url: 'https://gitlab.com/acme/tool.git' } },
          'not a plugin',
          { description: 'No name and nowhere to find one.', source: { source: 'npm', package: 'x' } },
        ],
      }),
      'plugins/broken/.claude-plugin/plugin.json': '{ not json',
      'plugins/broken/hooks/hooks.json': '[]',
      'plugins/broken/.mcp.json': json({ direct: { command: 'x' } }),
      'plugins/unnamed/skills/one/SKILL.md': '---\nname: one\n---\n',
    });
    const market = await createMarketplace({ fetch: hub.fetch }).load();
    expect(market.plugins.map((p) => p.name)).toEqual(['bare', 'broken', 'unnamed', 'outside', 'by-url']);
    const [bare, broken, unnamed, outside, byUrl] = market.plugins;
    expect(bare).toMatchObject({ description: '', version: null, author: null, keywords: [], readme: null, skills: [], connectors: [], external: false });
    expect(broken).toMatchObject({ description: 'Still listed.', hooks: [], connectors: [{ name: 'direct' }] });
    expect(unnamed!.skills).toEqual([{ name: 'one', description: '', url: `${repo}/blob/HEAD/plugins/unnamed/skills/one/SKILL.md`, body: '' }]);
    // A path out of the repository is not followed: it is shown as kept elsewhere.
    expect(outside).toMatchObject({ external: true, url: repo });
    expect(byUrl).toMatchObject({ external: true, url: 'https://gitlab.com/acme/tool' });
  });

  it('keeps its answer ten minutes, then reads again', async () => {
    const hub = github(stocked());
    let clock = 1_000;
    const market = createMarketplace({ fetch: hub.fetch, now: () => clock });
    const first = await market.load();
    const calls = hub.seen.length;
    clock += MARKETPLACE_TTL_MS - 1;
    expect(await market.load()).toBe(first);
    expect(hub.seen).toHaveLength(calls);

    hub.state.files = { ...stocked(), 'plugins/resume-screener/README.md': '# New words' };
    clock += 1;
    expect((await market.load()).plugins[0]!.readme).toBe('# New words');
    expect(hub.seen.length).toBeGreaterThan(calls);
  });

  it('reads once for many pages asking at the same time', async () => {
    const hub = github(stocked());
    const market = createMarketplace({ fetch: hub.fetch });
    const [a, b, c] = await Promise.all([market.load(), market.load(), market.load()]);
    expect(a).toBe(b);
    expect(b).toBe(c);
    expect(hub.seen.filter((r) => r.url === TREE)).toHaveLength(1);
  });

  it('serves the last answer, marked stale, when GitHub cannot be read, and leaves GitHub alone for a minute', async () => {
    const hub = github(stocked());
    let clock = 1_000;
    const market = createMarketplace({ fetch: hub.fetch, now: () => clock });
    const fresh = await market.load();

    clock += MARKETPLACE_TTL_MS;
    hub.state.down = true;
    const stale = await market.load();
    expect(stale).toEqual({ ...fresh, stale: true });
    const calls = hub.seen.length;
    clock += 30_000;
    expect((await market.load()).stale).toBe(true);
    expect(hub.seen).toHaveLength(calls);

    // A rate limit is a failure too; once GitHub answers again, so does the marketplace.
    hub.state.down = false;
    hub.state.tree = 403;
    clock += 60_000;
    expect((await market.load()).stale).toBe(true);
    hub.state.tree = 200;
    clock += 60_000;
    expect((await market.load()).stale).toBe(false);
  });

  it('fails when GitHub cannot be read and nothing is kept, then answers once it can', async () => {
    const hub = github(stocked());
    hub.state.down = true;
    let clock = 1_000;
    const market = createMarketplace({ fetch: hub.fetch, now: () => clock });
    await expect(market.load()).rejects.toThrow('GitHub could not be reached.');
    hub.state.down = false;
    // Within the minute it is not asked again.
    await expect(market.load()).rejects.toThrow('GitHub could not be reached.');
    clock += 60_000;
    expect((await market.load()).plugins).toHaveLength(2);
  });

  it('fails rather than show an empty marketplace when the list is there and cannot be read', async () => {
    const hub = github(stocked());
    const fetcher = ((input: Request | string | URL, init?: RequestInit) =>
      String(input).endsWith('marketplace.json') ? Promise.resolve(new Response('busy', { status: 503 })) : hub.fetch(input, init)) as typeof fetch;
    await expect(createMarketplace({ fetch: fetcher }).load()).rejects.toThrow(/could not be read/);
  });
});

describe('a markdown file’s front matter', () => {
  it('reads plain, quoted and folded values, and gives the text after it', () => {
    expect(frontMatter('---\nname: a\ndescription: "Said: so"\nwhen: |\n  one\n  two\n---\n\nBody\n')).toEqual({
      fields: { name: 'a', description: 'Said: so', when: 'one\ntwo' },
      body: 'Body\n',
    });
  });

  it('gives the whole file when there is none, or it never closes', () => {
    expect(frontMatter('Just words')).toEqual({ fields: {}, body: 'Just words' });
    expect(frontMatter('---\nname: a\nno end')).toEqual({ fields: {}, body: '---\nname: a\nno end' });
    expect(frontMatter('﻿---\r\nname: a\r\n---\r\nBody').fields).toEqual({ name: 'a' });
  });
});

describe('a plugin’s folder', () => {
  it.each([
    ['./plugins/x', null, 'plugins/x'],
    ['./plugins/x/', null, 'plugins/x'],
    ['x', './plugins', 'plugins/x'],
    ['x', null, 'x'],
    ['./', null, ''],
    ['../x', null, null],
    ['./a/../../x', null, null],
    ['/etc', null, null],
    ['https://github.com/a/b', null, null],
    [{ source: 'github', repo: 'a/b' }, null, null],
    [undefined, null, null],
  ])('%j under %j is %j', (source, root, folder) => expect(folderOf(source, root)).toBe(folder));
});

describe('GET /api/marketplace', () => {
  const cookie = `__Host-glyphh_session=${seal({ accessToken: 'access-1', refreshToken: 'refresh-1', expiresAt: 9_000_000 }, testConfig.sessionKey, 'glyphh.session')}`;
  const app = (hub: ReturnType<typeof github>) => createApp({ config: testConfig, fetch: hub.fetch, now: () => 1_000_000 });
  const get = (hub: ReturnType<typeof github>, headers: Record<string, string> = { cookie }) => app(hub).request(`${testConfig.platformUrl}/api/marketplace`, { headers });

  it('is for signed-in pages', async () => {
    const hub = github(stocked());
    const res = await get(hub, {});
    expect(res.status).toBe(401);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe('E_SIGNED_OUT');
    expect(hub.seen).toHaveLength(0);
  });

  it('answers the marketplace, and sends nothing of the person’s to GitHub', async () => {
    const hub = github(stocked());
    const res = await get(hub);
    expect(res.status).toBe(200);
    expect(res.headers.get('cache-control')).toBe('no-store');
    const market = (await res.json()) as Marketplace;
    expect(market.name).toBe('glyphh');
    expect(market.plugins.map((p) => p.name)).toEqual(['resume-screener', 'ticket-router']);
    for (const request of hub.seen) {
      expect(request.headers.get('authorization')).toBeNull();
      expect(request.headers.get('cookie')).toBeNull();
    }
  });

  it('answers an empty marketplace while the repository is empty', async () => {
    const hub = github({});
    hub.state.tree = 409;
    const res = await get(hub);
    expect(res.status).toBe(200);
    expect(((await res.json()) as Marketplace).plugins).toEqual([]);
  });

  it('answers 502 when GitHub cannot be read and nothing is kept', async () => {
    const hub = github(stocked());
    hub.state.down = true;
    const res = await get(hub);
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({ error: { code: 'E_MARKETPLACE', message: 'The marketplace could not be loaded from GitHub.' } });
  });
});
