import { Hono } from 'hono';
import { serveStatic } from '@hono/node-server/serve-static';

/**
 * games.glyphh.ai: the games Glyphh makes, a card each and a page per game, open to anyone. Plain pages
 * (games/public) and nothing else: no sign-in, no session, no /api, nothing of the platform's or the demos'.
 * The games themselves run on their own sites; these pages show them and link there.
 */

/** The host the games answer on (`GAMES_HOST`, default games.glyphh.ai). */
export function readGamesHost(env: NodeJS.ProcessEnv = process.env): string {
  return (env.GAMES_HOST?.trim() || 'games.glyphh.ai').toLowerCase();
}

/** The front page and each game's page (games/public); a game's address without its slash goes to the one with it. */
export function createGames(root = 'games/public') {
  const app = new Hono();
  app.get('/:game{[a-z0-9-]+}', (c) => c.redirect(`/${c.req.param('game')}/`, 308));
  app.use('*', serveStatic({ root }));
  app.notFound((c) => c.text('Not found', 404));
  return app;
}
