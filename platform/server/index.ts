import { readFile } from 'node:fs/promises';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { createApp } from './app.js';
import { readConfig } from './config.js';
import { createBot, isBotPath, serveBotRedirect } from './bot.js';
import { createDemo, hostOf, readDemoConfig, serveDemoPage, type HistoryRow } from './demo.js';
import { createGames, readGamesHost } from './games.js';
import { readGames } from './gamesAdmin.js';
import { createVoice, isVoicePath, serveVoiceRedirect } from './voice.js';

/** Production: the route handlers, the built pages, and index.html for every other path; the demo and the games on their own hosts. */
const config = readConfig();
const app = createApp({ config, games: readGames() });
const clientDir = 'dist/client';
const indexHtml = await readFile(`${clientDir}/index.html`, 'utf8');

app.use('/assets/*', serveStatic({ root: clientDir, onFound: (_path, c) => c.header('cache-control', 'public, max-age=31536000, immutable') }));
app.use('*', serveStatic({ root: clientDir }));
app.get('*', (c) => c.html(indexHtml));

// demo.glyphh.ai: its own page and its own /api, nothing of the platform's (no sign-in, no session, no /api/v1).
const demoConfig = readDemoConfig();
const history = JSON.parse(await readFile('demo/history.json', 'utf8')) as HistoryRow[];
const demo = serveDemoPage(createDemo({ config: demoConfig, history, secureCookies: config.secureCookies }));
// demo.glyphh.ai/voice: the voice game's /api/voice and its own model; its page is served with the others'.
const voiceCalls = Number(process.env.DEMO_VOICE_DAILY_CALLS);
const voice = serveVoiceRedirect(
  createVoice({ config: { ...demoConfig, voiceDailyCalls: Number.isInteger(voiceCalls) && voiceCalls > 0 ? voiceCalls : 300 }, secureCookies: config.secureCookies }),
);
// demo.glyphh.ai/bot: a bot taught a made-up rule, its /api/bot and a model per take; its page is served with the others'.
const botCalls = Number(process.env.DEMO_BOT_DAILY_CALLS);
const bot = serveBotRedirect(
  createBot({ config: { ...demoConfig, botDailyCalls: Number.isInteger(botCalls) && botCalls > 0 ? botCalls : 6000 }, secureCookies: config.secureCookies }),
);
const onDemo = (req: Request) => {
  const path = new URL(req.url).pathname;
  return isVoicePath(path) ? voice.fetch(req) : isBotPath(path) ? bot.fetch(req) : demo.fetch(req);
};

// games.glyphh.ai: the games Glyphh makes, plain pages and nothing else.
const gamesHost = readGamesHost();
const games = createGames();
const onHost = (req: Request) => {
  const host = hostOf(req);
  return host === demoConfig.host ? onDemo(req) : host === gamesHost ? games.fetch(req) : app.fetch(req);
};

const port = Number(process.env.PORT ?? 3000);
serve({ fetch: onHost, port }, () =>
  console.log(`Glyphh platform on ${config.platformUrl}, the demo on https://${demoConfig.host}, the games on https://${gamesHost} (port ${port})`),
);
