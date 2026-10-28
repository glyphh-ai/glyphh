import { readFile } from 'node:fs/promises';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { createApp } from './app.js';
import { readConfig } from './config.js';
import { createDemo, hostOf, readDemoConfig, serveDemoPage, type HistoryRow } from './demo.js';

/** Production: the route handlers, the built pages, and index.html for every other path; the demo on its own host. */
const config = readConfig();
const app = createApp({ config });
const clientDir = 'dist/client';
const indexHtml = await readFile(`${clientDir}/index.html`, 'utf8');

app.use('/assets/*', serveStatic({ root: clientDir, onFound: (_path, c) => c.header('cache-control', 'public, max-age=31536000, immutable') }));
app.use('*', serveStatic({ root: clientDir }));
app.get('*', (c) => c.html(indexHtml));

// demo.glyphh.ai: its own page and its own /api, nothing of the platform's (no sign-in, no session, no /api/v1).
const demoConfig = readDemoConfig();
const history = JSON.parse(await readFile('demo/history.json', 'utf8')) as HistoryRow[];
const demo = serveDemoPage(createDemo({ config: demoConfig, history, secureCookies: config.secureCookies }));

const port = Number(process.env.PORT ?? 3000);
serve({ fetch: (req) => (hostOf(req) === demoConfig.host ? demo.fetch(req) : app.fetch(req)), port }, () =>
  console.log(`Glyphh platform on ${config.platformUrl}, the demo on https://${demoConfig.host} (port ${port})`),
);
