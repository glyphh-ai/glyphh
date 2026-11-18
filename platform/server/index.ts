import { readFile } from 'node:fs/promises';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { createApp } from './app.js';
import { readConfig } from './config.js';

/**
 * Production: the route handlers, the built pages, and index.html for every other path. One site on one host: the
 * demos (demo.glyphh.ai) and the games pages (games.glyphh.ai) were removed with Glyphh's products on 2026-11-18;
 * glyphh.ai serves the games pages itself.
 */
const config = readConfig();
const app = createApp({ config });
const clientDir = 'dist/client';
const indexHtml = await readFile(`${clientDir}/index.html`, 'utf8');

app.use('/assets/*', serveStatic({ root: clientDir, onFound: (_path, c) => c.header('cache-control', 'public, max-age=31536000, immutable') }));
app.use('*', serveStatic({ root: clientDir }));
app.get('*', (c) => c.html(indexHtml));

const port = Number(process.env.PORT ?? 3000);
serve({ fetch: app.fetch, port }, () => console.log(`Glyphh platform on ${config.platformUrl} (port ${port})`));
