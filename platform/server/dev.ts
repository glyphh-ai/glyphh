import { createServer as createHttpServer } from 'node:http';
import { getRequestListener } from '@hono/node-server';
import { createServer as createVite } from 'vite';
import { createApp } from './app.js';
import { readConfig } from './config.js';
import { readGames } from './gamesAdmin.js';

/**
 * Development: one port. Vite serves the pages with hot reload; /auth and /api go to the route handlers,
 * exactly as they do in production.
 */
process.loadEnvFile?.('.env');
const config = readConfig();
const handle = getRequestListener(createApp({ config, games: readGames() }).fetch);
const vite = await createVite({ server: { middlewareMode: true }, appType: 'spa' });

const port = Number(process.env.PORT ?? new URL(config.platformUrl).port ?? 3000);
createHttpServer((req, res) => {
  if (req.url?.startsWith('/auth/') || req.url?.startsWith('/api/')) return void handle(req, res);
  vite.middlewares(req, res);
}).listen(port, () => console.log(`Glyphh platform (dev) on ${config.platformUrl}`));
