// Ada, live: expense approvals. A small server that holds your API key and talks to Ada Cloud through the Glyphh
// SDK; the page (public/) never sees the key. Every answer on screen is Ada Cloud's.
//
//   GLYPHH_API_KEY=glyphh_ak_... npm start      then open http://localhost:4321

import { readFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Ada, ModelMissingError } from '@glyphh-ai/glyphh';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 4321);
const MODEL = process.env.DEMO_MODEL || 'launch-demo-expenses';

if (!process.env.GLYPHH_API_KEY) {
  console.error('Set GLYPHH_API_KEY to an Ada Cloud key (platform.glyphh.ai → API Keys), then run npm start again.');
  process.exit(1);
}

const ada = new Ada(); // reads GLYPHH_API_KEY
const HISTORY = JSON.parse(await readFile(path.join(HERE, 'history.json'), 'utf8'));

// What Ada is shown of an expense. Who filed it and when are for people; the decision rests on these.
const SPEC = {
  name: MODEL,
  layers: [{
    name: 'expense',
    segments: [{
      name: 'claim',
      roles: [
        { name: 'ref', key_part: true, similarity_weight: 0 },
        { name: 'department', similarity_weight: 0.3 },
        { name: 'category' },
        { name: 'amount', numeric_config: { min_value: 0, max_value: 3000, bin_width: 100 } },
        { name: 'receipt' },
        { name: 'policy' },
        { name: 'description', text_encoding: 'bag_of_words', similarity_weight: 0.4 },
      ],
    }],
  }],
  // Under 75% sure, Ada says so and a person decides.
  output: { ask_below: 0.75 },
};

const asData = (c) => ({
  expense: {
    claim: {
      ...(c.ref ? { ref: c.ref } : {}),
      department: String(c.department).toLowerCase(),
      category: String(c.category).toLowerCase(),
      amount: Number(c.amount),
      receipt: c.receipt ? 'yes' : 'no',
      policy: String(c.policy),
      description: String(c.description || ''),
    },
  },
});

let ledger = []; // the history, then what was decided in this session, each with Ada's id for it
let next = 2081;

async function loadHistory() {
  const { ids } = await ada.model(MODEL).recordMany(HISTORY.map((c) => ({ data: asData(c), outcome: c.outcome })));
  ledger = HISTORY.map((c, i) => ({ ...c, id: ids[i] }));
  next = 2081;
}

/** The model as the demo needs it: there, holding the history. Recording the same refs again replaces them. */
async function ready() {
  const names = (await ada.models()).map((m) => m.name);
  if (!names.includes(MODEL)) await ada.createModel(MODEL, SPEC);
  await loadHistory();
}

/** Back to the 40 past expenses and nothing else: the model made again, the history recorded into it. */
async function reset() {
  try {
    await ada.deleteModel(MODEL);
  } catch (e) {
    if (!(e instanceof ModelMissingError)) throw e;
  }
  await ada.createModel(MODEL, SPEC);
  await loadHistory();
}

const routes = {
  'GET /api/state': async () => ({ model: MODEL, ledger }),
  'POST /api/reset': async () => {
    await reset();
    return { model: MODEL, ledger };
  },
  'POST /api/decide': async ({ claim }) => {
    const started = performance.now();
    const d = await ada.decide(MODEL, asData(claim));
    const ms = Math.round(performance.now() - started);
    return {
      outcome: d.outcome,
      probabilities: d.probabilities,
      ask: d.ask,
      receipts: d.receipts.map((r) => ({ id: r.id, sim: r.sim, outcome: r.outcome })),
      ms,
    };
  },
  'POST /api/record': async ({ claim, outcome }) => {
    const ref = `E-${next}`;
    const decided = outcome === 'reject' ? 'reject' : 'approve';
    const { ids } = await ada.model(MODEL).recordMany([{ data: asData({ ...claim, ref }), outcome: decided }]);
    next += 1;
    const row = { ...claim, ref, outcome: decided, id: ids[0], date: new Date().toISOString().slice(0, 10), added: true };
    ledger.push(row);
    return row;
  },
};

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml' };

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const route = routes[`${req.method} ${url.pathname}`];
  if (route) {
    let body = {};
    if (req.method === 'POST') {
      let raw = '';
      for await (const chunk of req) raw += chunk;
      try { body = raw ? JSON.parse(raw) : {}; } catch { body = {}; }
    }
    try {
      const out = await route(body);
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify(out));
    } catch (e) {
      const status = e.status && e.status >= 400 ? e.status : 502;
      res.writeHead(status, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error: e.message || 'Ada Cloud did not answer.', code: e.code }));
      console.error(e.code || '', e.message);
    }
    return;
  }
  const file = path.join(HERE, 'public', url.pathname === '/' ? 'index.html' : path.normalize(url.pathname));
  if (!file.startsWith(path.join(HERE, 'public'))) {
    res.writeHead(404).end();
    return;
  }
  try {
    const content = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(content);
  } catch {
    res.writeHead(404).end('Not found');
  }
});

try {
  await ready();
} catch (e) {
  console.error(`Could not reach the model on Ada Cloud: ${e.code || ''} ${e.message}`);
  process.exit(1);
}
server.listen(PORT, () => console.log(`Ada, live — ${ledger.length} past expenses in ${MODEL}. Open http://localhost:${PORT}`));
