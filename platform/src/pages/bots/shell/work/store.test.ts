import { frameOf, openPanels } from './layouts';
import { Work } from './store';

const made = () => {
  const work = new Work();
  const said: string[] = [];
  work.toast = (t) => said.push(t);
  return { work, said };
};

describe('the work panels’ layout, as the Glyphh Bot app keeps it', () => {
  it('opens panels into the layout’s frame (full, then under), focuses one already open, and closes them', () => {
    const { work } = made();
    expect(work.get().layout.name).toBe('Default');
    work.openPanel('files');
    work.openPanel('editor');
    expect(work.get().layout.frames[0]!.stack).toEqual(['files', 'editor']);
    expect(work.get().focused).toBe('editor');
    work.openPanel('files');
    expect(work.get().layout.frames[0]!.stack).toEqual(['files', 'editor']);
    expect(work.get().focused).toBe('files');
    work.closePanel('files');
    expect(openPanels(work.get().layout)).toEqual(['editor']);
    expect(work.get().focused).toBeNull();
    work.closeAllPanels();
    expect(openPanels(work.get().layout)).toEqual([]);
  });

  it('expands one panel over the desk and puts it back; opening another ends it', () => {
    const { work } = made();
    work.openPanel('files');
    work.toggleExpand('files');
    expect(work.get().expanded).toBe('files');
    work.openPanel('diff');
    expect(work.get().expanded).toBeNull();
    work.toggleExpand('diff');
    work.toggleExpand('diff');
    expect(work.get().expanded).toBeNull();
    work.toggleExpand('diff');
    work.closePanel('diff');
    expect(work.get().expanded).toBeNull();
  });

  it('switches to a built-in layout keeping the open panels, and a pinned frame takes every new one', () => {
    const { work, said } = made();
    work.openPanel('files');
    work.switchLayout('Side by side');
    expect(work.get().layout.frames).toHaveLength(2);
    expect(frameOf(work.get().layout, 'files')).toBe(0);
    work.togglePin(1);
    expect(work.get().layout.frames[1]!.pinned).toBe(true);
    work.openPanel('terminal');
    work.openPanel('diff');
    expect(work.get().layout.frames[1]!.stack).toEqual(['terminal', 'diff']);
    work.togglePin(1);
    expect(work.get().layout.frames.some((f) => f.pinned)).toBe(false);
    // A header dropped on another frame moves its panel there.
    work.openPanel('diff', 0);
    expect(work.get().layout.frames.map((f) => f.stack)).toEqual([['files', 'diff'], ['terminal']]);
    work.switchLayout('Nope');
    expect(said).toEqual(['No layout called Nope.']);
  });

  it('keeps the person’s layouts and the one on screen in this browser, per person', () => {
    const { work } = made();
    work.signIn('u-1');
    work.switchLayout('Dev');
    expect(openPanels(work.get().layout).sort()).toEqual(['browser', 'diff', 'editor', 'files']);
    const dev = work.get().layout;
    work.saveLayout({ name: 'Mine', cols: 2, rows: 1, frames: [{ col: 0, row: 0, stack: ['files'] }, { col: 1, row: 0, pinned: true }] });
    expect(() => work.saveLayout({ name: 'Dev', cols: 1, rows: 1, frames: [] })).toThrow(/built-in layout/);
    work.saveLayout({ name: 'Ours', cols: 2, rows: 1, frames: [] }, 'Mine');
    expect(work.get().layouts.map((l) => l.name)).toEqual(['Ours']);

    const again = new Work();
    again.signIn('u-1');
    expect(again.get().layouts.map((l) => l.name)).toEqual(['Ours']);
    expect(again.get().layout).toEqual(dev);
    again.removeLayout('Ours');
    const other = new Work();
    other.signIn('u-2');
    expect(other.get().layouts).toEqual([]);
    expect(other.get().layout.name).toBe('Default');
    const third = new Work();
    third.signIn('u-1');
    expect(third.get().layouts).toEqual([]);
  });

  it('reads nothing kept that is not a layout', () => {
    localStorage.setItem('glyphh.work.layouts.u-9', '{not json');
    localStorage.setItem('glyphh.work.layout.u-9', '"words"');
    const work = new Work();
    work.signIn('u-9');
    expect(work.get().layouts).toEqual([]);
    expect(work.get().layout.name).toBe('Default');
  });

  it('starts another machine with nothing open in the Editor, and is inert without one', async () => {
    const { work } = made();
    await work.openFile('README.md');
    expect(work.get().openFiles).toEqual([]);
    work.setPlace('rr-studio', null);
    expect(work.client?.place).toBe('rr-studio');
    work.set({ ws: 'acme__site', openFiles: [{ ws: 'acme__site', path: 'a', content: '', saved: '', kind: 'text' }], activeFile: 'a' });
    work.setPlace('rr-studio', 'run-1');
    expect(work.get().openFiles).toHaveLength(1);
    work.pickWorkspace('acme__site');
    expect(work.get().openFiles).toHaveLength(1);
    work.pickWorkspace('acme__docs');
    expect(work.get().openFiles).toEqual([]);
    work.setPlace(null, null);
    expect(work.client).toBeNull();
    expect(work.get().ws).toBe('');
  });
});
