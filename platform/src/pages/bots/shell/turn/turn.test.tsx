import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import type { BotRun } from '@/api/bots';
import { botsFake, inbox, waiting } from '@/test/bots';
import { crewFake } from '@/test/projects';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server } from '@/test/server';
import { answerOf, fallbackSummary, fileKind, fileSize, filesOf, imagesOf, isJson, linkBadge, linkWhere, plainWords, wordsOf } from './answer';
import { framed, MAX_HEIGHT, PROTOCOL, serve, toolResult } from './bridge';

const v1 = (path: string) => `*/v1${path}`;
const done = (given: Partial<BotRun> = {}) => waiting({ id: 'r-done', status: 'done', question: null, finished_at: '2026-11-20T09:01:00Z', ...given });

function on(runs: BotRun[]) {
  const fake = botsFake({ bots: [inbox()], runs });
  server.use(...fake.handlers, ...crewFake({ botRuns: () => fake.state.runs, projects: [] }).handlers);
  renderApp('/bots/inbox-helper');
  return screen.findByRole('article', { name: /^Inbox helper:/ });
}

/** Several runs in one chat, as their turns: the list is newest first, the chat oldest first. */
async function turns(runs: [BotRun, BotRun]): Promise<[HTMLElement, HTMLElement]> {
  const fake = botsFake({ bots: [inbox()], runs });
  server.use(...fake.handlers, ...crewFake({ botRuns: () => fake.state.runs, projects: [] }).handlers);
  renderApp('/bots/inbox-helper');
  await waitFor(() => expect(screen.getAllByRole('article', { name: /^Inbox helper:/ })).toHaveLength(runs.length));
  const [first, second] = screen.getAllByRole('article', { name: /^Inbox helper:/ });
  return [first!, second!];
}

/** Chris's run: "Hi there" typed to a bot that ranks pull requests. It answers; nothing ran. */
const greeted = () =>
  done({
    input: 'Hi there',
    output: 'Hi. I rank the pull requests waiting on you each morning. Ask me **what needs my review today?**',
    steps: [],
    hint: '',
    summary: '',
  } as Partial<BotRun>);

/** A turn that used three things: one of an app, one of Ada's, one that failed. */
const worked = () =>
  done({
    input: 'What needs my review today?',
    output: 'Two pull requests need you today.',
    steps: [
      { tool: 'github-search-issues-and-pull-requests', title: 'Searched issues and pull requests', app: 'GitHub', ok: true },
      { tool: 'decide', title: 'Decided urgency for 4 items', app: '', ok: true },
      { tool: 'slack-send-message', title: 'Sent a message', app: 'Slack', ok: false },
    ],
    data: { 'github-search-issues-and-pull-requests': { ret: { items: [{ id: 1, title: 'Fix the login' }] } } },
  });

const PNG = 'https://cdn.example.com/chart.png';
const rich = () =>
  done({
    input: 'Morning',
    output: '## Plan\n\n| Part | Status |\n| --- | --- |\n| Hero | done |\n\n- [x] Hero\n- [ ] Timer\n\n```js\nconst left = 1\n```\n\nSee [the brief](https://example.com/brief).',
    data: {
      shot: { image_url: PNG, content: [{ type: 'image', data: 'AAAA', mimeType: 'image/png' }] },
      mail: { ret: { attachments: [{ filename: 'brief.pdf', size: 2048, webViewLink: 'https://drive.google.com/file/d/1' }, { name: 'notes.txt', mimeType: 'text/plain' }] } },
    },
    links: [{ url: 'https://github.com/acme/app/pull/7', title: 'Fix the login', kind: 'Pull request' }],
    summary: '',
  });

describe('a bot’s turn is clean', () => {
  it('answers a greeting in its own words: no fold when it used nothing, no note about what it takes, no "$0.00"', async () => {
    const skipped = done({ id: 'r-free', status: 'skipped', output: '', steps: [], summary: 'It did not run: it has run 200 times today.', input_tokens: 0, output_tokens: 0, cost_micros: 0 });
    const [free, turn] = await turns([greeted(), skipped]);
    expect(within(turn).getByText(/I rank the pull requests waiting on you each morning/)).toBeInTheDocument();
    expect(within(turn).queryByRole('button', { name: /^Ran / })).toBeNull();
    expect(within(turn).queryByRole('note')).toBeNull();
    expect(within(turn).queryByRole('table', { name: 'Decisions' })).toBeNull();
    expect(turn.querySelector('.err')).toBeNull();
    expect(turn.textContent).toMatch(/tokens · \$/);
    expect(within(free).getByText('It did not run: it has run 200 times today.')).toBeInTheDocument();
    expect(free.textContent).not.toMatch(/token|\$0/);
  });

  it('folds what it used behind "Ran N steps": each in plain words with its app, a quiet mark on one that failed; never a tool’s own name or its data', async () => {
    const one = done({ id: 'r-one', output: 'Done.', steps: [{ tool: 'x', title: 'Read a page', app: '', ok: true }, { tool: 'y', title: ' ', app: '', ok: true }] });
    const [single, turn] = await turns([worked(), one]);
    expect(within(single).getByRole('button', { name: 'Ran 1 step' })).toBeInTheDocument();
    expect(within(turn).queryByLabelText('Steps')).toBeNull();
    fireEvent.click(within(turn).getByRole('button', { name: 'Ran 3 steps' }));
    const lines = within(within(turn).getByRole('list', { name: 'Steps' })).getAllByRole('listitem');
    expect(lines.map((l) => l.textContent)).toEqual(['•Searched issues and pull requestsGitHub', '•Decided urgency for 4 items', '×Sent a messageSlackdid not work']);
    expect(lines.map((l) => l.className)).toEqual(['tool ok', 'tool ok', 'tool err']);
    // Nothing of the engine's: no tool key, no data, no Raw.
    expect(turn.textContent).not.toMatch(/github-search|slack-send|\bdecide\b|\{"|"ret"|Fix the login/);
    expect(within(turn).queryByRole('button', { name: /raw/i })).toBeNull();
    fireEvent.click(within(turn).getByRole('button', { name: 'Ran 3 steps' }));
    expect(within(turn).queryByLabelText('Steps')).toBeNull();
  });

  it('shows what it is doing now on the fold’s line while it runs', async () => {
    const turn = await on([done({ status: 'running', output: '', finished_at: null, steps: [{ tool: 'a', title: 'Searched the inbox', app: 'Gmail', ok: true }, { tool: 'b', title: 'Reading 3 emails', app: 'Gmail', ok: true }] })]);
    const line = within(turn).getByRole('button', { name: 'Reading 3 emails' });
    fireEvent.click(line);
    expect(within(turn).getAllByRole('listitem').map((l) => l.className)).toEqual(['tool ok', 'tool run']);
  });

  it('says the action an approval asks about in plain words, never the tool’s own name', async () => {
    const turn = await on([waiting({ steps: [], question: { question: 'Send this message to #support?', options: ['Yes', 'No'], batch: null, answer_with: null, approval: true, tool: 'slack-send-message', detail: 'Send a message in Slack: “Two tickets are urgent.”' } })]);
    const ask = within(turn).getByRole('region', { name: 'Question' });
    expect(ask).toHaveTextContent('Send this message to #support?');
    expect(ask).toHaveTextContent('Send a message in Slack: “Two tickets are urgent.”');
    expect(ask.textContent).not.toMatch(/slack-send-message/);
    expect(within(ask).getAllByRole('button').map((b) => b.textContent)).toEqual(['Yes', 'No', 'Cancel run']);
  });

  it('shows the answer as markdown, with images inline, link cards and file chips', async () => {
    const turn = await on([rich()]);
    expect(within(turn).getByRole('heading', { name: 'Plan' })).toBeInTheDocument();
    expect(within(turn).getByRole('table')).toHaveTextContent('PartStatusHerodone');
    expect(within(turn).getAllByRole('checkbox').map((c) => (c as HTMLInputElement).checked)).toEqual([true, false]);
    expect(within(turn).getByRole('button', { name: 'Copy' })).toBeInTheDocument();
    expect(within(turn).getByRole('link', { name: 'the brief' })).toHaveAttribute('href', 'https://example.com/brief');
    const images = within(within(turn).getByLabelText('Images')).getAllByRole('img');
    expect(images.map((i) => i.getAttribute('src'))).toEqual([PNG, 'data:image/png;base64,AAAA']);
    const card = within(within(turn).getByLabelText('Links')).getByRole('link');
    expect(card).toHaveAttribute('href', 'https://github.com/acme/app/pull/7');
    expect(card).toHaveTextContent('PRFix the logingithub.com/acme/app/pull/7Pull requestopen ↗');
    const files = within(turn).getByLabelText('Files');
    expect(within(files).getByRole('link')).toHaveTextContent('PDFbrief.pdf2.0 KB');
    expect(files).toHaveTextContent('TXTnotes.txt');
    // It went the whole way and spoke for itself: no "It finished" beside its own words.
    expect(within(turn).queryByText(/It finished/)).toBeNull();
  });

  it('names the files of its folders the bot read and changed, each with what it did', async () => {
    const used = [
      { name: 'Notes/Summary.md', did: 'written' as const },
      { name: 'Invoices/March.pdf', did: 'read' as const },
    ];
    const turn = await on([done({ output: 'Summarised.', files: used, data: { work: { filename: 'Notes/Summary.md', size: 9 } } })]);
    const chips = within(turn).getByLabelText('Files');
    expect(Array.from(chips.querySelectorAll('.att')).map((c) => c.textContent)).toEqual(['MDNotes/Summary.md· written', 'PDFInvoices/March.pdf· read']);
    expect(within(chips).queryByRole('link')).toBeNull();
    const many = Array.from({ length: 9 }, (_, i) => ({ name: `f${i}.txt`, did: 'read' as const }));
    expect(filesOf(done({ files: [...many, ...many] }))).toHaveLength(6);
    expect(filesOf(done({ files: used }))[1]).toEqual({ name: 'Invoices/March.pdf', size: null, url: null, did: 'read' });
  });

  it('shows a failed run’s reason plainly and asks a question in place', async () => {
    const failed = await on([done({ status: 'failed', error: 'step decide: gate easy has no model', summary: undefined })]);
    expect(within(failed).getByText('It failed: Step decide: decision easy has no model.')).toBeInTheDocument();
  });

  it('asks its question inline, with no line saying it waits', async () => {
    const turn = await on([waiting({ summary: 'It is waiting on your answer.' })]);
    expect(within(turn).getByRole('region', { name: 'Question' })).toHaveTextContent('Answer these emails?');
    expect(within(turn).queryByText('It is waiting on your answer.')).toBeNull();
  });

  it('shows an MCP App inline in a sandboxed frame: its own page, or one of Glyphh’s read by its address', async () => {
    server.use(http.get(v1('/mcp-apps/resource'), ({ request }) => HttpResponse.json({ uri: new URL(request.url).searchParams.get('uri'), mimeType: 'text/html;profile=mcp-app', text: '<html><head></head><body>card</body></html>' })));
    const turn = await on([
      done({
        output: 'Decided.',
        apps: [
          { step: 'decide', uri: 'ui://acme/board/1', title: 'Board', html: '<p>board</p>', input: null, result: { n: 1 } },
          { step: 'decide', uri: 'ui://glyphh/decision/1', title: 'Ada decision', html: null, input: { case: 1 }, result: { outcome: 'approve' } },
          { step: 'other', uri: 'ui://acme/gone/1', title: 'Gone', html: null, input: null, result: null },
        ],
      }),
    ]);
    const board = within(within(turn).getByRole('region', { name: 'Board, an app' })).getByTitle('Board') as HTMLIFrameElement;
    expect(board.getAttribute('sandbox')).toBe('allow-scripts');
    expect(board.srcdoc).toContain("default-src 'none'");
    expect(board.srcdoc).toContain('<p>board</p>');
    await waitFor(() => expect((within(turn).getByTitle('Ada decision') as HTMLIFrameElement).srcdoc).toContain('<body>card</body>'));
    expect(within(turn).getByRole('region', { name: 'Gone, an app' })).toHaveTextContent('This app did not come with a page to show.');
  });
});

describe('the turn’s words', () => {
  const run = (given: Partial<BotRun>) => done({ output: '', error: '', summary: undefined, ...given });
  it('tells data from words', () => {
    expect([isJson('{"a": 1}'), isJson('[1]'), isJson('{not json'), isJson('3'), isJson(''), isJson('words')]).toEqual([true, true, false, false, false, false]);
    // A tool's answer cut to fit no longer parses; it is still never shown as the bot's words.
    expect([isJson('{"os": [], "ret": [{"url": "https://api.github.com/re'), isJson('[{"id": 1}, {"id"'), isJson('[see below] and so on')]).toEqual([true, true, false]);
    expect(answerOf(waiting({ output: '{"os": [], "ret": [{"url": "https://api.github.com/re' }))).toBe('');
    expect(answerOf(run({ output: ' Three need you. ' }))).toBe('Three need you.');
    // Its words are its answer alone: never something dug out of the run's data.
    expect(answerOf(run({ output: '{"ok": true}', data: { digest: 'Three need you.' } }))).toBe('');
  });
  it('says what happened to a run with no words when the server did not', () => {
    expect(plainWords('the gates and its gate')).toBe('the decisions and its decision');
    expect(fallbackSummary(run({ status: 'needs_input', question: null }))).toBe('Waiting on your answer.');
    expect(fallbackSummary(waiting())).toBe('');
    expect(fallbackSummary(run({ status: 'skipped', error: 'the bot is paused' }))).toBe('It did not run: The bot is paused.');
    expect(fallbackSummary(run({ status: 'skipped' }))).toBe('It did not run.');
    expect(fallbackSummary(run({ status: 'failed', error: 'cancelled' }))).toBe('Cancelled before it finished.');
    expect(fallbackSummary(run({ status: 'failed', error: 'interrupted by a restart' }))).toMatch(/^It was cut off by a restart/);
    expect(fallbackSummary(run({ status: 'failed' }))).toBe('It failed.');
    expect(fallbackSummary(run({ status: 'running' }))).toBe('');
    expect(fallbackSummary(run({ error: 'it ran out of time' }))).toBe('It ran out of time.');
    expect(fallbackSummary(run({}))).toBe('It finished.');
    expect(wordsOf(run({ output: 'Words.', summary: 'It finished.' }))).toEqual({ answer: 'Words.', summary: '' });
    expect(wordsOf(run({ status: 'failed', error: 'cancelled', summary: 'Cancelled before it finished.' }))).toEqual({ answer: '', summary: 'Cancelled before it finished.' });
  });
  it('finds what a person can look at in the steps’ data, and names files and links', () => {
    const many = Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`s${i}`, { image: `https://x.test/${i}.png`, file: { filename: `f${i}.csv`, size: 10 } }]));
    expect(imagesOf(run({ data: many }))).toHaveLength(6);
    expect(filesOf(run({ data: many }))).toHaveLength(6);
    expect(imagesOf(run({ data: { input: PNG, _kept: { image: PNG }, a: { image: 'ftp://x/y.png', photo_url: PNG, b: { type: 'image', data: 'AA', mimeType: 'text/html' }, alt: { type: 'image', data: 'BB', mimeType: 'image/webp', alt: 'A chart' } } } }), `![chart](${PNG})`)).toEqual([{ src: 'data:image/webp;base64,BB', alt: 'A chart' }]);
    expect(filesOf(run({ data: { a: [{ name: 'no type' }, { name: 'doc.md', mime_type: 'text/markdown', html_url: 'https://github.com/a/b' }, { filename: 'doc.md' }] } }))).toEqual([{ name: 'doc.md', size: null, url: 'https://github.com/a/b' }]);
    expect([fileSize(12), fileSize(2048), fileSize(20480), fileSize(3 * 1024 * 1024)]).toEqual(['12 B', '2.0 KB', '20 KB', '3.0 MB']);
    expect([fileKind('a.markdown'), fileKind('Makefile')]).toEqual(['MARK', 'FILE']);
    expect([linkBadge('Pull request'), linkBadge('Something')]).toEqual(['PR', 'LINK']);
    expect([linkWhere('https://www.notion.so/Weekly/'), linkWhere('not a url')]).toEqual(['notion.so/Weekly', 'not a url']);
  });
});

describe('the MCP Apps bridge', () => {
  const page = () => {
    const sent: Array<Record<string, unknown>> = [];
    const frame = { postMessage: (m: Record<string, unknown>) => sent.push(m) } as unknown as Window;
    const say = (data: unknown, source: unknown = frame) => window.dispatchEvent(new MessageEvent('message', { data, source: source as MessageEventSource }));
    return { sent, frame, say };
  };
  const settled = () => new Promise((r) => setTimeout(r, 0));

  it('initializes the page, hands it its tool’s input and result, and follows its height', async () => {
    const { sent, frame, say } = page();
    const sizes: number[] = [];
    const stop = serve({ frame: () => frame, input: { case: 1 }, result: { outcome: 'approve' }, onSize: (h) => sizes.push(h), openLink: () => undefined });
    say({ jsonrpc: '2.0', id: 1, method: 'ui/initialize', params: {} });
    await settled();
    expect(sent[0]).toMatchObject({ jsonrpc: '2.0', id: 1, result: { protocolVersion: PROTOCOL, hostCapabilities: { openLinks: {} }, hostContext: { theme: 'dark', displayMode: 'inline' } } });
    expect((sent[0]!.result as { hostCapabilities: object }).hostCapabilities).not.toHaveProperty('serverTools');
    say({ jsonrpc: '2.0', method: 'ui/notifications/initialized' });
    expect(sent.slice(1)).toEqual([
      { jsonrpc: '2.0', method: 'ui/notifications/tool-input', params: { arguments: { case: 1 } } },
      { jsonrpc: '2.0', method: 'ui/notifications/tool-result', params: toolResult({ outcome: 'approve' }) },
    ]);
    say({ jsonrpc: '2.0', method: 'ui/notifications/size-changed', params: { height: 412.2 } });
    say({ jsonrpc: '2.0', method: 'ui/notifications/size-changed', params: { height: 99999 } });
    say({ jsonrpc: '2.0', method: 'ui/notifications/size-changed', params: { width: 3 } });
    expect(sizes).toEqual([413, MAX_HEIGHT]);
    // Another window's message, and anything that is not JSON-RPC, is not heard.
    say({ jsonrpc: '2.0', id: 9, method: 'ping' }, {});
    say('hello');
    say({ id: 3, method: 'ping' });
    stop();
    say({ jsonrpc: '2.0', id: 10, method: 'ping' });
    await settled();
    expect(sent).toHaveLength(3);
    expect(toolResult('done').content[0]!.text).toBe('done');
    expect(toolResult(undefined)).toMatchObject({ content: [{ text: 'null' }], structuredContent: {} });
  });

  it('opens web links only, calls tools only when the host lets it, and refuses the rest', async () => {
    const { sent, frame, say } = page();
    const opened: string[] = [];
    const called: unknown[] = [];
    const callTool = (name: string, args: unknown) => (name === 'boom' ? Promise.reject(new Error('It broke.')) : (called.push([name, args]), Promise.resolve({ isError: false })));
    const stop = serve({ frame: () => frame, input: null, result: null, onSize: () => undefined, openLink: (u) => opened.push(u), callTool });
    const ask = async (id: number, method: string, params?: Record<string, unknown>) => {
      say({ jsonrpc: '2.0', id, method, params });
      await settled();
      return sent.find((m) => m.id === id)!;
    };
    expect((await ask(1, 'ui/initialize')).result).toMatchObject({ hostCapabilities: { serverTools: {} } });
    expect(await ask(2, 'ui/open-link', { url: 'https://example.com/a' })).toMatchObject({ result: {} });
    expect(await ask(3, 'ui/open-link', { url: 'javascript:alert(1)' })).toMatchObject({ error: { code: -32000, message: 'Only a web link can be opened.' } });
    expect(await ask(4, 'ui/open-link')).toHaveProperty('error');
    expect(opened).toEqual(['https://example.com/a']);
    expect(await ask(5, 'tools/call', { name: 'ada_learn', arguments: { x: 1 } })).toMatchObject({ result: { isError: false } });
    expect(await ask(6, 'tools/call')).toMatchObject({ result: { isError: false } });
    expect(called).toEqual([['ada_learn', { x: 1 }], ['', {}]]);
    expect(await ask(7, 'tools/call', { name: 'boom' })).toMatchObject({ error: { message: 'It broke.' } });
    expect(await ask(8, 'ui/request-display-mode', { mode: 'fullscreen' })).toMatchObject({ result: { mode: 'inline' } });
    expect(await ask(9, 'ui/message', { content: [] })).toMatchObject({ result: {} });
    expect(await ask(10, 'resources/read')).toMatchObject({ error: { code: -32601 } });
    say({ jsonrpc: '2.0', method: 'ui/notifications/initialized' });
    expect(sent.at(-2)).toMatchObject({ params: { arguments: {} } });
    stop();
    const none = page();
    const quiet = serve({ frame: () => null, input: null, result: null, onSize: () => undefined, openLink: () => undefined });
    none.say({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'x' } }, null);
    await settled();
    expect(none.sent).toEqual([]);
    quiet();
  });

  it('locks the page down whatever it says of itself', () => {
    expect(framed('<html><head><title>x</title></head></html>')).toMatch(/^<html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none';[^"]*"><title>/);
    expect(framed('<p>bare</p>')).toMatch(/^<meta http-equiv="Content-Security-Policy"[^>]*><p>bare<\/p>$/);
  });
});
