// A rrotor as the work panels' tests ask it: the Studio Mac at its own address, with one repository the crew worked
// in, its files, a turn's branch and the record of what that turn ran. It takes only the ticket Glyphh's fake gave.
import type { Changed, TermLine, Workspace } from '@/api/work';
import { http, HttpResponse } from '@/test/server';

export const machine = 'https://studio-mac.rrotor.test';
export const PLACE = 'rr-studio';

export const site = (given: Partial<Workspace> = {}): Workspace => ({ id: 'acme__site', name: 'acme/site', kind: 'repo', branch: 'main', branches: ['turn/2-dex', 'turn/1-juno'], ...given });

const TREE: Record<string, { name: string; kind: 'dir' | 'file'; size: number | null }[]> = {
  '': [
    { name: 'attachments', kind: 'dir', size: null },
    { name: 'src', kind: 'dir', size: null },
    { name: 'index.html', kind: 'file', size: 740 },
    { name: 'README.md', kind: 'file', size: 120 },
  ],
  src: [
    { name: 'site.css', kind: 'file', size: 90 },
    { name: 'timer.js', kind: 'file', size: 210 },
  ],
  attachments: [
    { name: 'brief.txt', kind: 'file', size: 38 },
    { name: 'sketch.png', kind: 'file', size: 2048 },
  ],
};

export const TEXT: Record<string, string> = {
  'index.html': '<!doctype html>\n<link rel="stylesheet" href="src/site.css">\n<h1>Launch</h1>\n<p id="left"></p>\n<script type="module" src="src/timer.js"></script>\n',
  'README.md': '# Site\n\nThe launch page.\n',
  'src/site.css': 'body { background: #000; color: #ccc; font: 16px system-ui; padding: 48px; }\nh1 { color: #fff; font-size: 56px; letter-spacing: -0.03em; }\n',
  'src/timer.js': 'export function format(ms) {\n  const s = Math.floor(ms / 1000)\n  return `${s}s`\n}\n',
  'attachments/brief.txt': 'Launch brief\nShip the page by Friday.\n',
};

export const changes = (): Changed[] => [
  {
    path: 'src/timer.js',
    status: 'modified',
    added: 2,
    removed: 1,
    binary: false,
    before: TEXT['src/timer.js']!,
    after: 'export function format(ms) {\n  const s = Math.floor(ms / 1000)\n  const m = Math.floor(s / 60)\n  return m ? `${m}m ${s % 60}s` : `${s}s`\n}\n',
  },
  { path: 'attachments/brief.txt', status: 'added', added: 2, removed: 0, binary: false, before: null, after: TEXT['attachments/brief.txt']! },
  { path: 'attachments/sketch.png', status: 'added', added: 0, removed: 0, binary: true, before: null, after: null },
];

export const record = (): TermLine[] => [
  { n: 0, at: '2026-11-22T10:00:00Z', kind: 'note', text: 'Dex starts turn 2 on turn/2-dex' },
  { n: 1, at: '2026-11-22T10:00:01Z', kind: 'cmd', text: 'git checkout -B turn/2-dex origin/main' },
  { n: 2, at: '2026-11-22T10:00:09Z', kind: 'cmd', text: 'npm test' },
  { n: 3, at: '2026-11-22T10:00:12Z', kind: 'out', text: '3 passed' },
];

export type MachineFake = ReturnType<typeof machineFake>;

/** The machine's handlers and what it was asked. `given` changes what it has. */
export function machineFake(given: { workspaces?: Workspace[]; lines?: TermLine[]; live?: boolean; base?: string } = {}) {
  const state = {
    seen: [] as string[],
    saved: [] as { path: string; text: string }[],
    workspaces: given.workspaces ?? [site()],
    lines: given.lines ?? record(),
    live: given.live ?? false,
    /** A refusal for the next save: its status and code. */
    refuse: null as { status: number; code: string; message: string } | null,
    /** Tickets refused once (the browser fetches a fresh one). */
    stale: 0,
    tickets: 0,
  };
  const refused = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status });
  const guard = (request: Request) => {
    if (state.stale > 0) {
      state.stale -= 1;
      return refused(401, 'E_UNAUTHORIZED', 'That ticket has ended.');
    }
    return request.headers.get('authorization') === `Bearer ticket-${PLACE}` ? null : refused(401, 'E_UNAUTHORIZED', 'No ticket.');
  };
  const q = (request: Request) => new URL(request.url).searchParams;
  const work = (path: string) => `${machine}/v1/work${path}`;
  const handlers = [
    http.post('*/api/v1/bots/places/:id/ticket', ({ params }) => {
      state.tickets += 1;
      return HttpResponse.json({ token: `ticket-${String(params.id)}`, expires_in: 600, url: machine });
    }),
    http.get(work(''), ({ request }) => guard(request) ?? (state.seen.push('workspaces'), HttpResponse.json({ workspaces: state.workspaces }))),
    http.get(work('/:ws/tree'), ({ request }) => {
      const under = q(request).get('under') ?? '';
      state.seen.push(`tree ${under}`);
      const entries = (TREE[under] ?? []).map((e) => ({ ...e, path: under ? `${under}/${e.name}` : e.name }));
      return guard(request) ?? HttpResponse.json({ under, entries, truncated: false });
    }),
    http.get(work('/:ws/file'), ({ request }) => {
      const path = q(request).get('path') ?? '';
      const no = guard(request);
      if (no) return no;
      state.seen.push(`${q(request).get('raw') ? 'raw' : 'file'} ${path}`);
      if (q(request).get('raw')) return new HttpResponse(new Uint8Array([137, 80, 78, 71]), { headers: { 'content-type': 'image/png' } });
      if (path.endsWith('.bin')) return HttpResponse.json({ path, size: 9, binary: true, text: null, truncated: false });
      if (path.endsWith('.log')) return HttpResponse.json({ path, size: 9_000_000, binary: false, text: null, truncated: true });
      const text = TEXT[path];
      if (text === undefined) return refused(404, 'E_NOT_FOUND', `There is no ${path}.`);
      return HttpResponse.json({ path, size: text.length, binary: false, text, truncated: false });
    }),
    http.put(work('/:ws/file'), async ({ request }) => {
      const no = guard(request);
      if (no) return no;
      if (state.refuse) return refused(state.refuse.status, state.refuse.code, state.refuse.message);
      const path = q(request).get('path') ?? '';
      const { text } = (await request.json()) as { text: string };
      state.saved.push({ path, text });
      return HttpResponse.json({ path, size: text.length });
    }),
    http.get(work('/:ws/diff'), ({ request }) => {
      const branch = q(request).get('branch');
      state.seen.push(`diff ${branch ?? ''}`);
      return guard(request) ?? HttpResponse.json({ base: given.base ?? 'main', branch, files: branch === 'turn/1-juno' ? [] : changes(), truncated: false });
    }),
    http.get(work('/:ws/terminal'), ({ request }) => {
      const after = Number(q(request).get('after') ?? '0');
      state.seen.push(`terminal ${after}`);
      return guard(request) ?? HttpResponse.json({ lines: state.lines.filter((l) => l.n >= after), next: state.lines.length, live: state.live });
    }),
  ];
  return { state, handlers };
}
