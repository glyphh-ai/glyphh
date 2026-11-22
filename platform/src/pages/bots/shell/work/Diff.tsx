// The Diff panel, in the Glyphh Bot app's chrome (glyphh-bot src/renderer/src/panels/Diff.tsx): one fold per file
// with its +/- counts, expand all, collapse all and refresh, keeping what is open and where you were scrolled. What it
// shows is a turn's branch against the branch it started from, read from the machine; each file opens as Monaco's
// own diff of the two.
import { useEffect, useRef, useState } from 'react';
import type { Changed, Diff, WorkClient, Workspace } from '@/api/work';
import { Icon } from '../icons';
import { WICON, why } from './bits';
import { Ready } from './data';
import { loadMonaco } from './monaco';
import { useWork, useWorkActions } from './store';

const LINE = 19;
const lines = (s: string | null) => (s ? s.split('\n').length : 0);

/** Monaco's diff of one file: what the base has against what the branch has. */
function Sides({ file }: { file: Changed }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let dead = false;
    let drop = () => undefined as void;
    void loadMonaco().then((monaco) => {
      if (dead || !host.current) return;
      const uri = (side: string) => monaco.Uri.parse(`glyphh-diff://${side}/${file.path}`);
      const model = (side: string, text: string | null) => {
        const at = uri(side);
        monaco.editor.getModel(at)?.dispose();
        // The right side takes the file's own name, so both sides are coloured as its language.
        return monaco.editor.createModel(text ?? '', undefined, at);
      };
      const original = model('base', file.before);
      const modified = model('branch', file.after);
      const ed = monaco.editor.createDiffEditor(host.current, {
        theme: 'glyphh',
        automaticLayout: true,
        readOnly: true,
        originalEditable: false,
        renderSideBySide: false,
        fontSize: 12,
        fontFamily: '"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderOverviewRuler: false,
        lineNumbersMinChars: 3,
        hideUnchangedRegions: { enabled: true },
        scrollbar: { alwaysConsumeMouseWheel: false },
      });
      ed.setModel({ original, modified });
      drop = () => {
        ed.dispose();
        original.dispose();
        modified.dispose();
      };
    });
    return () => {
      dead = true;
      drop();
    };
  }, [file.path, file.before, file.after]);
  // As tall as what it shows: the changed lines with a little around them, or the whole of a short file.
  const rows = Math.min(Math.max(lines(file.before), lines(file.after)) + file.removed, file.added + file.removed + 8);
  const tall = Math.min(420, Math.max(3, rows) * LINE + 6);
  return <div className="wk-sides" ref={host} style={{ height: tall }} aria-label={`Changes to ${file.path}`} />;
}

function Changes({ client, workspace }: { client: WorkClient; workspace: Workspace }) {
  const work = useWorkActions();
  const tick = useWork((s) => s.tick);
  const [branch, setBranch] = useState(workspace.branches[0] ?? '');
  const [res, setRes] = useState<{ diff?: Diff; error?: string } | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const scroller = useRef<HTMLDivElement>(null);
  const seq = useRef(0);
  const first = useRef(true);

  const refresh = async () => {
    const n = ++seq.current;
    const out = await client.diff(workspace.id, branch || undefined).then(
      (diff) => ({ diff }),
      (e) => ({ error: why(e) }),
    );
    if (n !== seq.current) return;
    const keep = scroller.current?.scrollTop ?? 0;
    const got = 'diff' in out ? out.diff.files : [];
    // The first look opens a small change set; after that, what you opened stays as you left it.
    if (first.current && got.length) {
      first.current = false;
      if (got.length <= 5) setExpanded(new Set(got.map((f) => f.path)));
    }
    setRes(out);
    requestAnimationFrame(() => {
      if (scroller.current) scroller.current.scrollTop = keep;
    });
  };

  useEffect(() => {
    first.current = true;
    setRes(null);
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch, workspace.id]);
  useEffect(() => {
    if (tick > 0) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  const files = res?.diff?.files ?? [];
  const add = files.reduce((s, f) => s + f.added, 0);
  const del = files.reduce((s, f) => s + f.removed, 0);
  const base = res?.diff?.base;

  return (
    <div className="pane diffpane">
      <div className="ptool">
        <span className="dsum">
          {!res ? (
            'loading…'
          ) : res.error ? (
            'error'
          ) : files.length ? (
            <>
              {files.length} file{files.length === 1 ? '' : 's'}
              <i className="add">+{add}</i>
              <i className="del">−{del}</i>
            </>
          ) : (
            'no changes'
          )}
        </span>
        <select className="wk-pick" aria-label="Branch" title={base ? `Against ${base}` : 'Branch'} value={branch} onChange={(e) => setBranch(e.target.value)}>
          {workspace.branches.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
          <option value="">Files as they are now</option>
        </select>
        <span className="spacer" />
        <button type="button" className="ibtn" title="Expand all" aria-label="Expand all" onClick={() => setExpanded(new Set(files.map((f) => f.path)))}>
          <Icon d={WICON.expand} />
        </button>
        <button type="button" className="ibtn" title="Collapse all" aria-label="Collapse all" onClick={() => setExpanded(new Set())}>
          <Icon d={WICON.collapse} />
        </button>
        <button type="button" className="ibtn" title="Refresh" aria-label="Refresh the changes" onClick={() => void refresh()}>
          <Icon d={WICON.refresh} />
        </button>
      </div>
      <div className="dfiles" ref={scroller}>
        {res?.error && <p className="dim pad">{res.error}</p>}
        {res?.diff && !files.length && <p className="dim pad">{branch ? `${branch} has no changes against ${base}.` : `Nothing has changed against ${base}.`}</p>}
        {files.map((f) => {
          const isOpen = expanded.has(f.path);
          return (
            <div key={f.path} className={`dfile ${isOpen ? '' : 'collapsed'}`}>
              <div
                className="dhead"
                role="button"
                tabIndex={0}
                aria-expanded={isOpen}
                title="Click to fold, double-click to open in the Editor"
                onClick={() =>
                  setExpanded((s) => {
                    const n = new Set(s);
                    if (n.has(f.path)) n.delete(f.path);
                    else n.add(f.path);
                    return n;
                  })
                }
                onDoubleClick={() => f.status !== 'deleted' && void work.openFile(f.path).catch((e) => work.toast(why(e)))}
              >
                <span className="caret">{isOpen ? '▾' : '▸'}</span>
                <span className="dname">{f.path}</span>
                {f.status !== 'modified' && <span className="wk-status">{f.status === 'added' ? 'new' : 'deleted'}</span>}
                <span className="dstat">
                  <i className="add">+{f.added}</i>
                  <i className="del">−{f.removed}</i>
                </span>
              </div>
              {isOpen && <div className="dbody">{f.binary ? <p className="dim pad wk-note">Not a text file: its changes cannot be shown line by line.</p> : <Sides file={f} />}</div>}
            </div>
          );
        })}
        {res?.diff?.truncated && <p className="dim pad">There are more changes than are shown here.</p>}
      </div>
    </div>
  );
}

export function DiffPanel() {
  return <Ready>{(client, workspace) => <Changes key={workspace.id} client={client} workspace={workspace} />}</Ready>;
}
