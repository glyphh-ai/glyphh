import { readFile } from 'node:fs/promises';
import { describe, expect, it } from 'vitest';
import { createGames, readGamesHost } from './games.js';

describe('readGamesHost', () => {
  it('defaults to games.glyphh.ai', () => {
    expect(readGamesHost({})).toBe('games.glyphh.ai');
  });

  it('reads GAMES_HOST, lower case', () => {
    expect(readGamesHost({ GAMES_HOST: ' Games.Example.com ' })).toBe('games.example.com');
  });
});

describe('the pages', () => {
  const get = (path: string) => createGames().request(`https://games.test${path}`);

  it.each([
    ['/', 'text/html'],
    ['/games.css', 'text/css'],
    ['/games.js', 'text/javascript'],
    ['/home.js', 'text/javascript'],
    ['/glyphh-logo-text-white.png', 'image/png'],
    ['/free-fall-frank/', 'text/html'],
    ['/free-fall-frank/frank.css', 'text/css'],
    ['/free-fall-frank/frank.js', 'text/javascript'],
  ])('serves %s', async (path, type) => {
    const res = await get(path);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain(type);
  });

  it('sends /free-fall-frank to /free-fall-frank/', async () => {
    const res = await get('/free-fall-frank');
    expect(res.status).toBe(308);
    expect(res.headers.get('location')).toBe('/free-fall-frank/');
  });

  it('links every live game card to a page it serves, with its picture', async () => {
    const { GAMES } = (await import('../games/public/games.js')) as { GAMES: { href?: string; art?: string; soon?: boolean }[] };
    const live = GAMES.filter((g) => !g.soon);
    expect(live.length).toBeGreaterThan(0);
    for (const g of live) {
      expect((await get(g.href!)).status).toBe(200);
      expect((await get(g.art!)).status).toBe(200);
    }
  });

  it('serves every picture and script a page of its own names', async () => {
    for (const page of ['index.html', 'free-fall-frank/index.html']) {
      const html = await readFile(`games/public/${page}`, 'utf8');
      const own = [...html.matchAll(/(?:src|href|poster)="(\/[^"#]+)"/g)].map((m) => m[1]!);
      expect(own.length).toBeGreaterThan(3);
      for (const path of own) expect([path, (await get(path)).status]).toEqual([path, 200]);
    }
  });

  it.each(['/login', '/auth/session', '/api/v1/session', '/api/state', '/../server/games.ts', '/no-such-game/'])('has nothing at %s', async (path) => {
    const res = await get(path);
    const end = res.status === 308 ? await get(res.headers.get('location')!) : res;
    expect(end.status).toBe(404);
  });
});

describe('Free Fall Frank’s page', () => {
  const html = () => readFile('games/public/free-fall-frank/index.html', 'utf8');

  it('sends Advertise to support@glyphh.ai', async () => {
    expect(await html()).toContain('href="mailto:support@glyphh.ai?subject=Advertise%20in%20Free%20Fall%20Frank"');
  });

  it('gives the connector’s address and links to the game with its source', async () => {
    const page = await html();
    expect(page).toContain('https://freefallfrank.com/mcp');
    expect(page).toContain('href="https://freefallfrank.com/?src=games"');
  });

  it('plays the game’s own videos', async () => {
    const page = await html();
    for (const video of ['ad.mp4', 'ad2.mp4', 'ad3.mp4']) expect(page).toContain(`src="https://freefallfrank.com/${video}"`);
  });
});
