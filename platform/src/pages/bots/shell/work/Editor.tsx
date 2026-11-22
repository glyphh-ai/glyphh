// The Editor panel: Monaco with tabs, as the Glyphh Bot app's (glyphh-bot src/renderer/src/panels/Editor.tsx): a dot
// on unsaved tabs, Save and Cmd/Ctrl+S, a right-click menu on a tab and on the strip, a question before unsaved work
// is closed, and markdown shown rendered or as source. A save writes the machine's working copy, straight from the
// browser; an image is shown as the image, and a file with no text says so.
import { useEffect, useRef, useState } from 'react';
import { Modal } from '../bits';
import { Icon } from '../icons';
import { mdDoc } from '../md';
import { Menu, WICON, why, type MenuItem } from './bits';
import { loadMonaco, type Monaco } from './monaco';
import { useWork, useWorkActions, type OpenFile, type Work } from './store';

type Ed = ReturnType<Monaco['editor']['create']>;

const isMarkdown = (p: string): boolean => /\.(md|mdx|markdown)$/i.test(p);
const name = (p: string) => p.split('/').pop() ?? p;
/** What a save is, said once it is done: the machine's working copy, which a turn's fresh start replaces. */
export const SAVED_NOTE = 'Saved on the machine. It stays until a bot’s next turn there starts fresh, unless a turn commits it.';

async function saveFile(work: Work, path: string): Promise<boolean> {
  const f = work.get().openFiles.find((x) => x.path === path);
  if (!f || f.kind !== 'text' || f.content === f.saved || !work.client) return true;
  try {
    await work.client.save(f.ws, f.path, f.content);
    work.set((s) => ({ openFiles: s.openFiles.map((x) => (x.path === f.path ? { ...x, saved: f.content } : x)) }));
    return true;
  } catch (e) {
    work.toast(`Could not save ${name(f.path)}: ${why(e)}`);
    return false;
  }
}

async function saveAll(work: Work): Promise<void> {
  let any = false;
  for (const f of work.get().openFiles) if (f.content !== f.saved && (await saveFile(work, f.path))) any = true;
  if (any) work.toast(SAVED_NOTE);
}

function dropFiles(work: Work, paths: string[]) {
  const rest = work.get().openFiles.filter((f) => !paths.includes(f.path));
  const active = work.get().activeFile;
  work.set({ openFiles: rest, activeFile: paths.includes(active) ? (rest.at(-1)?.path ?? '') : active });
}

/** An image of the workspace, read from the machine with the ticket and shown from memory. */
function Picture({ file }: { file: OpenFile }) {
  const work = useWorkActions();
  const [src, setSrc] = useState('');
  const [failed, setFailed] = useState('');
  useEffect(() => {
    let url = '';
    let dead = false;
    work.client
      ?.raw(file.ws, file.path)
      .then((blob) => {
        if (dead) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch((e) => !dead && setFailed(why(e)));
    return () => {
      dead = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [work, file.ws, file.path]);
  if (failed) return <p className="dim pad wk-note">{failed}</p>;
  return <div className="wk-picture">{src && <img src={src} alt={name(file.path)} />}</div>;
}

function Tabs() {
  const work = useWorkActions();
  const files = useWork((s) => s.openFiles);
  const active = useWork((s) => s.activeFile);
  const host = useRef<HTMLDivElement>(null);
  const ed = useRef<Ed | null>(null);
  const [m, setM] = useState<Monaco | null>(null);
  const [rendered, setRendered] = useState<Record<string, boolean>>({});
  const [saved, setSaved] = useState(false);
  const [menu, setMenu] = useState<{ x: number; y: number; items: MenuItem[] } | null>(null);
  const [closing, setClosing] = useState<string[] | null>(null);
  const file = files.find((f) => f.path === active);
  const text = file?.kind === 'text';
  const preview = !!file && text && isMarkdown(file.path) && rendered[file.path] !== false;

  const save = async () => {
    const path = work.get().activeFile;
    const f = work.get().openFiles.find((x) => x.path === path);
    if (!f || f.content === f.saved) return;
    if (await saveFile(work, path)) {
      setSaved(true);
      work.toast(SAVED_NOTE);
      setTimeout(() => setSaved(false), 900);
    }
  };
  const saveRef = useRef(save);
  saveRef.current = save;

  const closeFiles = (paths: string[]) => {
    const dirty = work.get().openFiles.filter((f) => paths.includes(f.path) && f.content !== f.saved);
    if (dirty.length) setClosing(paths);
    else dropFiles(work, paths);
  };

  useEffect(() => {
    let dead = false;
    void loadMonaco().then((monaco) => {
      if (dead || !host.current) return;
      const e = monaco.editor.create(host.current, {
        theme: 'glyphh',
        automaticLayout: true,
        fontSize: 13,
        fontFamily: '"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',
        minimap: { enabled: false },
        padding: { top: 12 },
        smoothScrolling: true,
        cursorBlinking: 'phase',
        scrollBeyondLastLine: false,
        model: null,
      });
      e.onDidChangeModelContent(() => {
        const uri = e.getModel()?.uri.path.slice(1);
        const value = e.getValue();
        work.set((s) => ({ openFiles: s.openFiles.map((x) => (x.path === uri && x.content !== value ? { ...x, content: value } : x)) }));
      });
      e.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => void saveRef.current());
      ed.current = e;
      setM(monaco);
    });
    return () => {
      dead = true;
      ed.current?.dispose();
      ed.current = null;
    };
  }, [work]);

  useEffect(() => {
    if (!m || !ed.current) return;
    if (!file || file.kind !== 'text') {
      ed.current.setModel(null);
      return;
    }
    const uri = m.Uri.file('/' + file.path);
    const model = m.editor.getModel(uri) ?? m.editor.createModel(file.content, undefined, uri);
    if (model.getValue() !== file.content) model.setValue(file.content);
    if (ed.current.getModel() !== model) ed.current.setModel(model);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m, file?.path, file?.content, file?.kind]);

  // A closed file's model goes, so a reopen reads the machine afresh.
  useEffect(() => {
    if (!m) return;
    for (const model of m.editor.getModels()) {
      if (model.uri.scheme === 'file' && !files.some((f) => '/' + f.path === model.uri.path)) model.dispose();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m, files.length]);

  const all = () => work.get().openFiles.map((x) => x.path);
  const tabMenu = (e: React.MouseEvent, path: string) => {
    e.preventDefault();
    e.stopPropagation();
    const f = files.find((x) => x.path === path);
    const items: MenuItem[] = [];
    if (f && f.content !== f.saved) items.push({ label: 'Save', onPick: () => void saveFile(work, path).then((ok) => ok && work.toast(SAVED_NOTE)) });
    items.push({ label: 'Close', onPick: () => closeFiles([path]) });
    items.push({ label: 'Close all', onPick: () => closeFiles(all()) });
    items.push({ label: 'Save all', onPick: () => void saveAll(work) });
    setMenu({ x: e.clientX, y: e.clientY, items });
  };
  const stripMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setMenu({
      x: e.clientX,
      y: e.clientY,
      items: [
        { label: 'Save all', onPick: () => void saveAll(work) },
        { label: 'Close all', onPick: () => closeFiles(all()) },
      ],
    });
  };

  const dirty = !!file && file.content !== file.saved;
  const unsaved = closing ? files.filter((f) => closing.includes(f.path) && f.content !== f.saved).length : 0;

  return (
    <div className="pane editor">
      <div className="filetabs" role="tablist" aria-label="Open files" onContextMenu={stripMenu}>
        {!files.length && <span className="dim tabs-empty">No file open</span>}
        {files.map((f) => (
          <div key={f.path} role="tab" aria-selected={f.path === active} tabIndex={0} className={f.path === active ? 'ft on' : 'ft'} onClick={() => work.set({ activeFile: f.path })} onContextMenu={(e) => tabMenu(e, f.path)} title={f.path}>
            {f.content !== f.saved && <i className="unsaved" aria-label="Not saved" />}
            {name(f.path)}
            <button
              type="button"
              title="Close"
              aria-label={`Close ${name(f.path)}`}
              onClick={(e) => {
                e.stopPropagation();
                closeFiles([f.path]);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      {file && (
        <div className="pathbar">
          <span className="ptext">{file.path}</span>
          <span className="spacer" />
          {text && isMarkdown(file.path) && (
            <>
              <button type="button" className={`ibtn ${preview ? 'on' : ''}`} title="Rendered" aria-label="Rendered" onClick={() => setRendered((r) => ({ ...r, [file.path]: true }))}>
                <Icon d={WICON.eye} />
              </button>
              <button type="button" className={`ibtn ${!preview ? 'on' : ''}`} title="Source" aria-label="Source" onClick={() => setRendered((r) => ({ ...r, [file.path]: false }))}>
                <Icon d={WICON.code} />
              </button>
            </>
          )}
          {(dirty || saved) && (
            <button type="button" className="btn tiny" onClick={() => void save()}>
              {saved ? 'Saved' : 'Save ⌘S'}
            </button>
          )}
        </div>
      )}
      <div className="monaco" ref={host} style={{ visibility: file && text && !preview ? 'visible' : 'hidden' }} />
      {file && preview && <div className="mddoc" dangerouslySetInnerHTML={{ __html: mdDoc(file.content) }} />}
      {file?.kind === 'image' && <Picture key={file.path} file={file} />}
      {file && (file.kind === 'binary' || file.kind === 'big') && (
        <div className="empty over">
          <b>{file.kind === 'binary' ? 'Not a text file' : 'Too big to open here'}</b>
          <p>{file.kind === 'binary' ? `${name(file.path)} has no text to show or edit.` : `${name(file.path)} is over 1 MB. Open it on the machine itself.`}</p>
        </div>
      )}
      {!file && (
        <div className="empty over">
          <b>No file open</b>
          <p>Pick one in Files, or a changed file in Diff.</p>
        </div>
      )}
      {menu && <Menu {...menu} label="Open files" onClose={() => setMenu(null)} />}
      {closing && (
        <Modal small front title={closing.length === 1 ? `Close ${name(closing[0]!)}?` : 'Close all tabs?'} onClose={() => setClosing(null)}>
          <p className="dim">{unsaved === 1 ? 'It has unsaved changes.' : `${unsaved} files have unsaved changes.`}</p>
          <div className="row end">
            <button type="button" className="btn" onClick={() => setClosing(null)}>
              Keep editing
            </button>
            <button
              type="button"
              className="btn danger"
              onClick={() => {
                dropFiles(work, closing);
                setClosing(null);
              }}
            >
              Close without saving
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

/** With nothing open the panel says so without asking the machine: its files come from Files and Diff. */
export function EditorPanel() {
  return <Tabs />;
}
