import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { forgetTickets } from '@/api/work';
import { createQueryClient, Providers } from '@/App';
import { http, HttpResponse, server } from '@/test/server';
import { ShellContext } from '../bits';
import '../glyphh-bot.css';
import { SAVED_NOTE } from './Editor';
import { machine, machineFake, record, site, TEXT } from './fake';
import { WorkPanelHost, WorkPanelIcons, WorkProvider } from './index';
import { inlined } from './Preview';
import { drawn, IDLE_MS, LIVE_MS } from './Terminal';

// Monaco and xterm draw on a canvas jsdom does not have: the panels reach them through one small module each.
const fakes = vi.hoisted(() => {
  type Model = { uri: { path: string; scheme: string; toString(): string }; value: string; getValue(): string; setValue(v: string): void; dispose(): void };
  const models = new Map<string, Model>();
  const model = (text: string, at: { path: string; scheme: string; toString(): string }): Model => {
    const m: Model = { uri: at, value: text, getValue: () => m.value, setValue: (v) => void (m.value = v), dispose: () => void models.delete(at.toString()) };
    models.set(at.toString(), m);
    return m;
  };
  const uri = (scheme: string, path: string) => ({ scheme, path, toString: () => `${scheme}://${path}` });
  const editors: { model: Model | null; changed: () => void; saveKey: () => void; type(v: string): void }[] = [];
  const diffs: { original: string; modified: string; path: string }[] = [];
  const monaco = {
    KeyMod: { CtrlCmd: 1 },
    KeyCode: { KeyS: 2 },
    Uri: { file: (p: string) => uri('file', p), parse: (s: string) => uri('glyphh-diff', s.replace('glyphh-diff://', '')) },
    editor: {
      getModel: (at: { toString(): string }) => models.get(at.toString()) ?? null,
      getModels: () => [...models.values()],
      createModel: (text: string, _lang: undefined, at: { path: string; scheme: string; toString(): string }) => model(text, at),
      create: () => {
        const ed = {
          model: null as Model | null,
          changed: () => undefined as void,
          saveKey: () => undefined as void,
          type(v: string) {
            ed.model!.value = v;
            ed.changed();
          },
          onDidChangeModelContent: (fn: () => void) => void (ed.changed = fn),
          addCommand: (_k: number, fn: () => void) => void (ed.saveKey = fn),
          getModel: () => ed.model,
          setModel: (m: Model | null) => void (ed.model = m),
          getValue: () => ed.model?.value ?? '',
          dispose: () => undefined,
        };
        editors.push(ed);
        return ed;
      },
      createDiffEditor: () => ({
        setModel: (m: { original: Model; modified: Model }) => void diffs.push({ original: m.original.value, modified: m.modified.value, path: m.modified.uri.path }),
        dispose: () => undefined,
      }),
    },
  };
  const terms: { text: string; cleared: number; gone: boolean }[] = [];
  return { monaco, editors, diffs, models, terms };
});
vi.mock('./monaco', () => ({ loadMonaco: async () => fakes.monaco }));
vi.mock('./term', () => ({
  makeTerm: () => {
    const t = { text: '', cleared: 0, gone: false };
    fakes.terms.push(t);
    return { write: (s: string) => void (t.text += s), clear: () => void ((t.text = ''), (t.cleared += 1)), dispose: () => void (t.gone = true) };
  },
}));

const plain = (s: string) => s.replace(/\x1b\[[0-9;]*m/g, '');

function open(given: Parameters<typeof machineFake>[0] = {}, runsOn: string | null = 'rr-studio') {
  const fake = machineFake(given);
  server.use(...fake.handlers);
  const said: string[] = [];
  const shell = { toast: (t: string) => void said.push(t), openDecisions: () => undefined, editBot: () => undefined, openConnections: () => undefined };
  const user = userEvent.setup();
  const view = render(
    <Providers client={createQueryClient()}>
      <ShellContext.Provider value={shell}>
        <div className="gb">
          <div className="app">
            <WorkProvider runsOn={runsOn} runId={null}>
              <header role="banner">
                <WorkPanelIcons />
              </header>
              <div className="deskrow">
                <div className="panels bare">
                  <WorkPanelHost />
                </div>
              </div>
            </WorkProvider>
          </div>
        </div>
      </ShellContext.Provider>
    </Providers>,
  );
  const tools = () => screen.getByRole('toolbar', { name: 'Work panels' });
  const press = (name: string) => user.click(within(tools()).getByRole('button', { name }));
  return { fake, said, user, view, tools, press };
}

describe('the rrotor’s work panels', () => {
  beforeEach(() => {
    forgetTickets();
    fakes.editors.length = 0;
    fakes.diffs.length = 0;
    fakes.terms.length = 0;
    fakes.models.clear();
    URL.createObjectURL = vi.fn(() => 'blob:picture');
    URL.revokeObjectURL = vi.fn();
  });

  it('draws nothing and asks no machine unless what is selected runs on a rrotor', async () => {
    const { fake, view } = open({}, null);
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument();
    expect(view.container.querySelector('.wk-host')).toBeNull();
    await new Promise((r) => setTimeout(r, 20));
    expect(fake.state.tickets).toBe(0);
  });

  it('has the app’s five icons and the layouts, and asks the machine only once a panel is open', async () => {
    const { fake, press, tools, view } = open();
    expect(within(tools()).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual(['Files', 'Preview', 'Terminal', 'Editor', 'Diff', 'Layouts']);
    expect(view.container.querySelector('.wk-host')).toHaveClass('shut');
    expect(fake.state.tickets).toBe(0);
    await press('Files');
    const files = await screen.findByRole('region', { name: 'Files' });
    expect(within(tools()).getByRole('button', { name: 'Files' })).toHaveAttribute('aria-pressed', 'true');
    expect(await within(files).findByRole('tree', { name: 'Files of acme/site' })).toBeInTheDocument();
    expect(fake.state.seen).toEqual(['workspaces', 'tree ']);
    await press('Files');
    expect(screen.queryByRole('region', { name: 'Files' })).not.toBeInTheDocument();
  });

  it('lists the machine’s files as a lazy tree, searches the names read, and opens a file in the Editor', async () => {
    const { fake, press, user } = open();
    await press('Files');
    const tree = await screen.findByRole('tree');
    await waitFor(() => expect(within(tree).getAllByRole('treeitem').map((r) => r.textContent)).toEqual(['▸attachments', '▸src', '▸index.html', '▸README.md']));
    await user.click(within(tree).getByRole('treeitem', { name: /src/ }));
    await waitFor(() => expect(within(tree).getAllByRole('treeitem')).toHaveLength(6));
    expect(fake.state.seen).toContain('tree src');
    // Folding and opening again reads nothing new.
    await user.click(within(tree).getByRole('treeitem', { name: /^▸src/ }));
    expect(within(tree).getAllByRole('treeitem')).toHaveLength(4);
    await user.click(within(tree).getByRole('treeitem', { name: /^▸src/ }));
    expect(fake.state.seen.filter((s) => s === 'tree src')).toHaveLength(1);
    const files = screen.getByRole('region', { name: 'Files' });
    await user.type(within(files).getByRole('textbox', { name: 'Search files' }), 'TIMER');
    expect(within(tree).getAllByRole('treeitem').map((r) => r.textContent)).toEqual(['▸src/timer.js']);
    await user.clear(within(files).getByRole('textbox', { name: 'Search files' }));
    await user.type(within(files).getByRole('textbox', { name: 'Search files' }), 'zzz');
    expect(tree).toHaveTextContent('No file in the folders you opened matches "zzz".');
    await user.clear(within(files).getByRole('textbox', { name: 'Search files' }));
    await user.click(within(files).getByRole('button', { name: 'Refresh the files' }));
    await waitFor(() => expect(fake.state.seen.filter((s) => s === 'tree src')).toHaveLength(2));
    // No button for what the machine cannot do from here.
    expect(within(files).queryByRole('button', { name: /New|Rename|Delete/ })).not.toBeInTheDocument();
    await user.click(within(tree).getByRole('treeitem', { name: /README\.md/ }));
    const editor = await screen.findByRole('region', { name: 'Editor' });
    expect(await within(editor).findByRole('tab', { name: /README\.md/ })).toHaveAttribute('aria-selected', 'true');
    expect(within(tree).getByRole('treeitem', { name: /README\.md/ })).toHaveAttribute('aria-selected', 'true');
  });

  it('says what is missing when the machine has no repository yet, did not answer, or cannot list', async () => {
    const none = open({ workspaces: [] });
    await none.press('Files');
    expect(await screen.findByText('The crew has not worked in a repository on this machine yet.')).toBeInTheDocument();
    none.view.unmount();

    forgetTickets();
    const down = open();
    let fail = true;
    server.use(http.get(`${machine}/v1/work`, () => (fail ? HttpResponse.error() : HttpResponse.json({ workspaces: [site()] }))));
    await down.press('Diff');
    const diff = await screen.findByRole('region', { name: 'Diff' });
    expect(await within(diff).findByText('This machine could not be read')).toBeInTheDocument();
    expect(diff).toHaveTextContent('a rrotor on a computer answers only in a browser on that same computer');
    fail = false;
    await down.user.click(within(diff).getByRole('button', { name: 'Try again' }));
    expect(await within(diff).findByText('3 files', { exact: false })).toBeInTheDocument();
  });

  it('edits a file in Monaco with a dot on the unsaved tab, saves it to the machine and says what a save is', async () => {
    const { fake, press, user, said } = open();
    await press('Editor');
    const editor = await screen.findByRole('region', { name: 'Editor' });
    expect(within(editor).getByText('No file open', { selector: 'b' })).toBeInTheDocument();
    expect(fake.state.tickets).toBe(0);
    await press('Files');
    await user.click(await screen.findByRole('treeitem', { name: /README\.md/ }));
    const tab = await within(editor).findByRole('tab', { name: /README\.md/ });
    await waitFor(() => expect(fakes.editors[0]?.model?.value).toBe(TEXT['README.md']));
    expect(within(editor).queryByRole('button', { name: /Save/ })).not.toBeInTheDocument();
    // Markdown opens rendered; Source shows the text to edit.
    expect(editor.querySelector('.mddoc')).toHaveTextContent('The launch page.');
    await user.click(within(editor).getByRole('button', { name: 'Source' }));
    expect(editor.querySelector('.mddoc')).toBeNull();
    fakes.editors[0]!.type('# Site\n\nNew words.\n');
    expect(await within(tab).findByLabelText('Not saved')).toBeInTheDocument();
    await user.click(within(editor).getByRole('button', { name: 'Save ⌘S' }));
    await waitFor(() => expect(fake.state.saved).toEqual([{ path: 'README.md', text: '# Site\n\nNew words.\n' }]));
    expect(await within(editor).findByRole('button', { name: 'Saved' })).toBeInTheDocument();
    expect(within(tab).queryByLabelText('Not saved')).not.toBeInTheDocument();
    expect(said).toEqual([SAVED_NOTE]);
    // While a bot's turn holds the repository, the save is refused in plain words and the tab stays unsaved.
    fake.state.refuse = { status: 409, code: 'E_BUSY', message: 'held' };
    fakes.editors[0]!.type('# Again\n');
    fakes.editors[0]!.saveKey();
    await waitFor(() => expect(said.at(-1)).toBe('Could not save README.md: A bot is working in this repository right now. Save again when its turn ends.'));
    expect(within(tab).getByLabelText('Not saved')).toBeInTheDocument();
    expect(fake.state.saved).toHaveLength(1);
    // Closing unsaved work asks first.
    await user.click(within(tab).getByRole('button', { name: 'Close README.md' }));
    const ask = await screen.findByRole('dialog', { name: 'Close README.md?' });
    expect(ask).toHaveTextContent('It has unsaved changes.');
    await user.click(within(ask).getByRole('button', { name: 'Keep editing' }));
    expect(within(editor).getByRole('tab', { name: /README\.md/ })).toBeInTheDocument();
    await user.click(within(tab).getByRole('button', { name: 'Close README.md' }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Close without saving' }));
    expect(within(editor).queryByRole('tab')).not.toBeInTheDocument();
    expect(within(editor).getByText('No file open', { selector: 'b' })).toBeInTheDocument();
  });

  it('shows an image as the image, and says so for a file with no text or too big', async () => {
    const { fake, press, user } = open();
    await press('Files');
    await user.click(await screen.findByRole('treeitem', { name: /attachments/ }));
    await user.click(await screen.findByRole('treeitem', { name: /sketch\.png/ }));
    const editor = await screen.findByRole('region', { name: 'Editor' });
    expect(await within(editor).findByRole('img', { name: 'sketch.png' })).toHaveAttribute('src', 'blob:picture');
    expect(fake.state.seen).toContain('raw attachments/sketch.png');
    expect(fake.state.seen).not.toContain('file attachments/sketch.png');
    // The tabs' menu saves and closes them all.
    await user.click(within(screen.getByRole('tree')).getByRole('treeitem', { name: /brief\.txt/ }));
    await within(editor).findByRole('tab', { name: /brief\.txt/ });
    await user.pointer({ keys: '[MouseRight]', target: within(editor).getByRole('tablist', { name: 'Open files' }) });
    const menu = await screen.findByRole('menu', { name: 'Open files' });
    expect(within(menu).getAllByRole('menuitem').map((m) => m.textContent)).toEqual(['Save all', 'Close all']);
    await user.click(within(menu).getByRole('menuitem', { name: 'Close all' }));
    expect(within(editor).queryByRole('tab')).not.toBeInTheDocument();
  });

  it('shows a turn’s branch against its base as Monaco’s diff per file, with the app’s counts and folds', async () => {
    const { fake, press, user } = open();
    await press('Diff');
    const diff = await screen.findByRole('region', { name: 'Diff' });
    await waitFor(() => expect(diff.querySelector('.dsum')).toHaveTextContent('3 files+4−1'));
    // The newest branch first, against the branch it started from.
    expect(within(diff).getByRole('combobox', { name: 'Branch' })).toHaveValue('turn/2-dex');
    expect(within(diff).getByRole('combobox', { name: 'Branch' })).toHaveAttribute('title', 'Against main');
    expect(fake.state.seen).toContain('diff turn/2-dex');
    const heads = within(diff).getAllByRole('button', { expanded: true });
    expect(heads.map((h) => h.textContent)).toEqual(['▾src/timer.js+2−1', '▾attachments/brief.txtnew+2−0', '▾attachments/sketch.pngnew+0−0']);
    await waitFor(() => expect(fakes.diffs.map((d) => d.path)).toEqual(['branch/src/timer.js', 'branch/attachments/brief.txt']));
    expect(fakes.diffs[0]!.original).toBe(TEXT['src/timer.js']);
    expect(fakes.diffs[0]!.modified).toContain('Math.floor(s / 60)');
    expect(fakes.diffs[1]!.original).toBe('');
    expect(diff).toHaveTextContent('Not a text file: its changes cannot be shown line by line.');
    await user.click(within(diff).getByRole('button', { name: 'Collapse all' }));
    expect(within(diff).queryAllByRole('button', { expanded: true })).toHaveLength(0);
    await user.click(heads[0]!);
    expect(within(diff).getAllByRole('button', { expanded: true })).toHaveLength(1);
    await user.click(within(diff).getByRole('button', { name: 'Expand all' }));
    expect(within(diff).getAllByRole('button', { expanded: true })).toHaveLength(3);
    await user.click(within(diff).getByRole('button', { name: 'Refresh the changes' }));
    await waitFor(() => expect(fake.state.seen.filter((s) => s === 'diff turn/2-dex')).toHaveLength(2));
    // Another branch, and the files as they are now.
    await user.selectOptions(within(diff).getByRole('combobox', { name: 'Branch' }), 'turn/1-juno');
    expect(await within(diff).findByText('turn/1-juno has no changes against main.')).toBeInTheDocument();
    await user.selectOptions(within(diff).getByRole('combobox', { name: 'Branch' }), 'Files as they are now');
    await waitFor(() => expect(fake.state.seen.at(-1)).toBe('diff '));
    // A double click on a changed file opens it in the Editor.
    await user.dblClick(await within(diff).findByRole('button', { name: /src\/timer\.js/ }));
    expect(await within(await screen.findByRole('region', { name: 'Editor' })).findByRole('tab', { name: /timer\.js/ })).toBeInTheDocument();
  });

  it('draws the record of what a turn ran, read-only, and keeps asking for its new lines', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { fake, press } = open({ live: true });
      await press('Terminal');
      const term = await screen.findByRole('region', { name: 'Terminal' });
      await waitFor(() => expect(fakes.terms[0]?.text).toContain('npm test'));
      expect(plain(fakes.terms[0]!.text)).toBe(
        'What the bots ran in acme/site. Read-only: nothing typed here runs on the machine.\nDex starts turn 2 on turn/2-dex\n$ git checkout -B turn/2-dex origin/main\n$ npm test\n3 passed\n',
      );
      expect(within(term).getByRole('status')).toHaveTextContent('a turn is running');
      expect(term.querySelector('textarea, input')).toBeNull();
      // Only the lines after the last one it has are asked for, every second or so while a turn runs.
      fake.state.lines.push({ n: 4, at: '2026-11-22T10:00:20Z', kind: 'err', text: 'warning: 1 skipped\n' });
      await vi.advanceTimersByTimeAsync(LIVE_MS + 50);
      await waitFor(() => expect(plain(fakes.terms[0]!.text)).toMatch(/3 passed\nwarning: 1 skipped\n$/));
      expect(fake.state.seen.filter((s) => s.startsWith('terminal'))).toEqual(['terminal 0', 'terminal 4']);
      // The turn over, it asks less often; a record cut short when the next turn starts is drawn again.
      fake.state.live = false;
      await vi.advanceTimersByTimeAsync(LIVE_MS + 50);
      await waitFor(() => expect(within(term).getByRole('status')).toHaveTextContent('read-only'));
      fake.state.lines = record().slice(0, 1);
      await vi.advanceTimersByTimeAsync(LIVE_MS + 50);
      expect(fake.state.seen.filter((s) => s.startsWith('terminal'))).toHaveLength(3);
      await vi.advanceTimersByTimeAsync(IDLE_MS);
      await waitFor(() => expect(fakes.terms[0]!.cleared).toBe(1));
      await press('Terminal');
      expect(fakes.terms[0]!.gone).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('draws a command bright after its $, what it printed plain, a note dim and an error red', () => {
    const at = '2026-11-22T10:00:00Z';
    expect(drawn({ n: 0, at, kind: 'cmd', text: 'ls' })).toBe('\x1b[2m$\x1b[0m \x1b[1;97mls\x1b[0m\n');
    expect(drawn({ n: 1, at, kind: 'out', text: 'a\nb\n' })).toBe('a\nb\n');
    expect(drawn({ n: 2, at, kind: 'note', text: 'turn ends' })).toBe('\x1b[2mturn ends\x1b[0m\n');
    expect(drawn({ n: 3, at, kind: 'err', text: 'no' })).toBe('\x1b[31mno\x1b[0m\n');
  });

  it('previews the repository’s page in a frame that may only run its scripts, with its styles and scripts put inside', async () => {
    const { fake, press, user } = open();
    await press('Preview');
    const preview = await screen.findByRole('region', { name: 'Preview' });
    expect(await within(preview).findByText(/it does not browse the web/)).toBeInTheDocument();
    await user.click(within(preview).getByRole('button', { name: 'Preview' }));
    const frame = await within(preview).findByTitle('Preview of index.html');
    expect(frame).toHaveAttribute('sandbox', 'allow-scripts');
    const html = frame.getAttribute('srcdoc')!;
    expect(html).toContain('<style>\nbody { background: #000;');
    expect(html).toContain('<script type="module">\nexport function format(ms)');
    expect(html).not.toContain('href="src/site.css"');
    expect(fake.state.seen).toEqual(expect.arrayContaining(['file index.html', 'file src/site.css', 'file src/timer.js']));
    // A typed path: an image is shown as the image, text as text, and what is not there is said.
    const bar = within(preview).getByRole('textbox', { name: 'File to show' });
    await user.clear(bar);
    await user.type(bar, 'attachments/sketch.png{Enter}');
    expect(await within(preview).findByRole('img', { name: 'attachments/sketch.png' })).toHaveAttribute('src', 'blob:picture');
    await user.clear(bar);
    await user.type(bar, './attachments/brief.txt{Enter}');
    expect(await within(preview).findByText(/Ship the page by Friday/)).toBeInTheDocument();
    await user.clear(bar);
    await user.type(bar, 'nope.html{Enter}');
    expect(await within(preview).findByText('There is no nope.html.')).toBeInTheDocument();
    await user.clear(bar);
    await user.type(bar, 'data.bin{Enter}');
    expect(await within(preview).findByText('data.bin is not a page, an image or text.')).toBeInTheDocument();
    await user.clear(bar);
    await user.type(bar, 'big.log{Enter}');
    expect(await within(preview).findByText('big.log is too big to show here.')).toBeInTheDocument();
    const before = fake.state.seen.length;
    await user.click(within(preview).getByRole('button', { name: 'Reload the preview' }));
    await waitFor(() => expect(fake.state.seen.length).toBe(before + 1));
  });

  it('puts only the page’s own stylesheets and scripts inside it, never one from the web', async () => {
    const read = async (p: string) => ({ 'a/s.css': 'p{}', 'app.js': 'let a="</script>"', 'a/m.js': 'import 1' })[p] ?? null;
    const html = [
      '<link rel="stylesheet" href="s.css">',
      '<link rel="stylesheet" href="https://cdn.test/x.css">',
      '<link rel="icon" href="i.png">',
      '<link rel="stylesheet" href="gone.css">',
      '<script src="../app.js"></script>',
      '<script type="module" src="./m.js"></script>',
      '<script src="//cdn.test/y.js"></script>',
    ].join('\n');
    expect(await inlined(html, 'a/index.html', read)).toBe(
      [
        '<style>\np{}\n</style>',
        '<link rel="stylesheet" href="https://cdn.test/x.css">',
        '<link rel="icon" href="i.png">',
        '<link rel="stylesheet" href="gone.css">',
        '<script>\nlet a="<\\/script>"\n</script>',
        '<script type="module">\nimport 1\n</script>',
        '<script src="//cdn.test/y.js"></script>',
      ].join('\n'),
    );
  });

  it('places the panels in the layout’s frames: pin, expand, and a header dropped on another frame', async () => {
    const { press, user, view } = open();
    await press('Layouts');
    const menu = await screen.findByRole('menu', { name: 'Layouts' });
    expect(within(menu).getAllByRole('menuitem').map((m) => m.textContent)).toEqual(['✓ Default', 'Side by side', 'Dev', 'Review', 'Manage layouts…']);
    await user.click(within(menu).getByRole('menuitem', { name: 'Side by side' }));
    await press('Files');
    await press('Diff');
    const host = view.container.querySelector('.wk-host')!;
    expect(host).toHaveAttribute('data-layout', 'Side by side');
    const files = await screen.findByRole('region', { name: 'Files' });
    const diff = await screen.findByRole('region', { name: 'Diff' });
    // One frame showing: Files full, Diff under it.
    expect(parseFloat(files.style.height)).toBeCloseTo(50);
    expect(parseFloat(diff.style.top)).toBeCloseTo(50);
    // A header dragged over a panel lights the frame it would drop into.
    const data = new Map<string, string>();
    const dataTransfer = { setData: (k: string, v: string) => void data.set(k, v), getData: (k: string) => data.get(k) ?? '', get types() { return [...data.keys()]; }, effectAllowed: '' };
    fireEvent.dragStart(diff.querySelector('.dhead')!, { dataTransfer });
    fireEvent.dragOver(files, { dataTransfer });
    expect(files).toHaveClass('over');
    fireEvent.dragLeave(files, { dataTransfer, relatedTarget: document.body });
    expect(files).not.toHaveClass('over');
    // Pin the frame Files is in: the next panel stacks there.
    await user.click(within(files).getByRole('button', { name: 'Pin the frame Files is in' }));
    expect(within(files).getByRole('button', { name: 'Unpin the frame Files is in' })).toHaveTextContent('Pinned');
    expect(host.querySelector('.dframe.pinned')).not.toBeNull();
    await press('Terminal');
    const term = await screen.findByRole('region', { name: 'Terminal' });
    expect(parseFloat(term.style.left)).toBeCloseTo(50);
    // Expanded, a panel fills the desk; the others stay mounted, hidden.
    await user.click(within(term).getByRole('button', { name: 'Expand Terminal' }));
    expect(host).toHaveClass('expanded');
    expect(term.style.width).toBe('100%');
    expect(screen.queryByRole('region', { name: 'Files' })).not.toBeInTheDocument();
    expect(host.querySelectorAll('section.dslot')).toHaveLength(3);
    await user.click(within(term).getByRole('button', { name: 'Put Terminal back' }));
    expect(host).not.toHaveClass('expanded');
    await user.click(within(term).getByRole('button', { name: 'Close Terminal' }));
    expect(screen.queryByRole('region', { name: 'Terminal' })).not.toBeInTheDocument();
    await press('Layouts');
    await user.click(within(await screen.findByRole('menu')).getByRole('menuitem', { name: 'Close all panels' }));
    expect(host).toHaveClass('shut');
  });

  it('manages layouts as the app does: copy a built-in, shape it, pin a frame, save and open, edit and delete', async () => {
    const { press, user, said, view } = open();
    await press('Layouts');
    await user.click(within(await screen.findByRole('menu')).getByRole('menuitem', { name: 'Manage layouts…' }));
    const list = await screen.findByRole('dialog', { name: 'Layouts' });
    expect(Array.from(list.querySelectorAll('.lm-row')).map((r) => r.querySelector('.lm-main')!.textContent)).toEqual([
      'Defaultbuilt in · 1 frame · on screen',
      'Side by sidebuilt in · 2 frames',
      'Devbuilt in · 4 frames',
      'Reviewbuilt in · 2 frames',
    ]);
    // A built-in is copied, never edited; its name cannot be taken.
    await user.click(within(list).getByRole('button', { name: 'Copy Review' }));
    const copy = await screen.findByRole('dialog', { name: 'New layout' });
    expect(within(copy).getByRole('textbox', { name: 'Name' })).toHaveValue('Review copy');
    await user.clear(within(copy).getByRole('textbox', { name: 'Name' }));
    await user.type(within(copy).getByRole('textbox', { name: 'Name' }), 'Dev');
    await user.click(within(copy).getByRole('button', { name: 'Save' }));
    expect(said.at(-1)).toBe('"Dev" is a built-in layout. Pick another name.');
    await user.click(within(copy).getByRole('button', { name: 'Back' }));
    // A new one: a shape, a frame that starts with a panel, a pin, and split and merge.
    await user.click(within(await screen.findByRole('dialog', { name: 'Layouts' })).getByRole('button', { name: '+ New layout' }));
    const fresh = await screen.findByRole('dialog', { name: 'New layout' });
    await user.click(within(fresh).getByRole('button', { name: 'Save' }));
    expect(said.at(-1)).toBe('Give the layout a name.');
    await user.type(within(fresh).getByRole('textbox', { name: 'Name' }), 'Mine');
    await user.click(within(fresh).getByRole('button', { name: 'Main and two' }));
    const frames = within(fresh).getByRole('group', { name: 'Frames' });
    expect(within(frames).getAllByRole('button')).toHaveLength(3);
    expect(within(frames).getAllByRole('button')[0]).toHaveTextContent('empty1 x 2');
    await user.selectOptions(within(fresh).getByRole('combobox', { name: 'The panel this frame opens with' }), 'Starts with Preview');
    expect(within(frames).getAllByRole('button')[0]).toHaveTextContent('Preview');
    await user.click(within(frames).getAllByRole('button')[1]!);
    await user.click(within(fresh).getByRole('button', { name: 'Pin' }));
    expect(within(frames).getAllByRole('button')[1]).toHaveTextContent('pinned · new panels go here');
    expect(within(fresh).getByRole('button', { name: 'Merge down' })).toBeEnabled();
    await user.click(within(fresh).getByRole('button', { name: 'Merge down' }));
    expect(within(frames).getAllByRole('button')).toHaveLength(2);
    await user.click(within(fresh.querySelector<HTMLElement>('.lm-cellbar')!).getByRole('button', { name: 'Split' }));
    expect(within(frames).getAllByRole('button')).toHaveLength(3);
    await user.clear(within(fresh).getByRole('spinbutton', { name: 'Columns' }));
    await user.type(within(fresh).getByRole('spinbutton', { name: 'Columns' }), '3');
    expect(within(frames).getAllByRole('button').length).toBeGreaterThan(3);
    await user.click(within(fresh).getByRole('button', { name: 'Save and open' }));
    expect(said.at(-1)).toBe('Saved Mine.');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(view.container.querySelector('.wk-host')).toHaveAttribute('data-layout', 'Mine');
    expect(await screen.findByRole('region', { name: 'Preview' })).toBeInTheDocument();
    // It is in the menu and the list as yours; the one on screen can be saved under a name; yours can be deleted.
    await press('Layouts');
    expect(within(await screen.findByRole('menu')).getByRole('menuitem', { name: '✓ Mine' })).toBeInTheDocument();
    await user.click(within(screen.getByRole('menu')).getByRole('menuitem', { name: 'Manage layouts…' }));
    const again = await screen.findByRole('dialog', { name: 'Layouts' });
    expect(again.querySelector('.lm-row.on .lm-main')).toHaveTextContent(/^Mineyours · \d+ frames · one pinned · on screen$/);
    await user.click(within(again).getByRole('button', { name: 'Save the one on screen…' }));
    const edit = await screen.findByRole('dialog', { name: 'Edit Mine' });
    await user.clear(within(edit).getByRole('textbox', { name: 'Name' }));
    await user.type(within(edit).getByRole('textbox', { name: 'Name' }), 'Ours');
    await user.click(within(edit).getByRole('button', { name: 'Save' }));
    const renamed = await screen.findByRole('dialog', { name: 'Layouts' });
    expect(within(renamed).queryByRole('button', { name: 'Edit Mine' })).not.toBeInTheDocument();
    await user.click(within(renamed).getByRole('button', { name: 'Edit Ours' }));
    await user.click(within(await screen.findByRole('dialog', { name: 'Edit Ours' })).getByRole('button', { name: 'Back' }));
    const last = await screen.findByRole('dialog', { name: 'Layouts' });
    await user.click(within(last).getByRole('button', { name: 'Delete Ours' }));
    await user.click(within(last).getByRole('button', { name: 'Delete Ours for good' }));
    expect(within(last).queryByText('Ours')).not.toBeInTheDocument();
    await user.click(within(last).getByRole('button', { name: 'Open Review' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(view.container.querySelector('.wk-host')).toHaveAttribute('data-layout', 'Review');
    // No word of how a bot works inside is on the panels.
    const words = [document.body.textContent ?? '', ...Array.from(document.querySelectorAll('[aria-label],[title],[placeholder]')).flatMap((el) => [el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('placeholder')])].join(' ');
    expect(words).not.toMatch(/\b(gates?|loop|spec|skills?|json|swarms?|projects?|markup)\b/i);
  });

  it('picks which of the machine’s repositories the panels read when there is more than one', async () => {
    const { fake, press, user } = open({ workspaces: [site(), site({ id: 'acme__docs', name: 'acme/docs', branches: [] })] });
    await press('Files');
    const files = await screen.findByRole('region', { name: 'Files' });
    const pick = await within(files).findByRole('combobox', { name: 'Repository' });
    expect(pick).toHaveValue('acme__site');
    await user.selectOptions(pick, 'acme/docs');
    expect(await within(files).findByRole('tree', { name: 'Files of acme/docs' })).toBeInTheDocument();
    expect(fake.state.seen.filter((s) => s === 'tree ')).toHaveLength(2);
    // A repository no turn has branched in shows its files as they are now.
    await press('Diff');
    await waitFor(() => expect(fake.state.seen.at(-1)).toBe('diff '));
  });
});
