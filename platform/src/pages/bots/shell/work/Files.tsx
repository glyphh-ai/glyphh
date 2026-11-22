// The Files panel, as the Glyphh Bot app's (glyphh-bot src/renderer/src/panels/Files.tsx): a lazy tree that keeps
// what is open across refreshes, a search box and Refresh. It reads the machine's own listing; a click opens the file
// in the Editor. The machine offers no way to make, rename or delete a file from here, so there are no such buttons.
import { useCallback, useEffect, useState } from 'react';
import type { Entry, WorkClient, Workspace } from '@/api/work';
import { Icon } from '../icons';
import { Menu, WICON, why, type MenuItem } from './bits';
import { Ready, WorkspacePick } from './data';
import { useWork, useWorkActions } from './store';

function Tree({ client, workspace }: { client: WorkClient; workspace: Workspace }) {
  const work = useWorkActions();
  const tick = useWork((s) => s.tick);
  const active = useWork((s) => s.activeFile);
  const [kids, setKids] = useState<Record<string, Entry[]>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState('');
  const [failed, setFailed] = useState('');
  const [cut, setCut] = useState(false);
  const [menu, setMenu] = useState<{ x: number; y: number; items: MenuItem[] } | null>(null);

  /** Re-read the listed folders from the machine, keeping every open subtree. */
  const reload = useCallback(
    async (dirs: string[]) => {
      const read = await Promise.all(
        dirs.map(async (d) => {
          try {
            return [d, await client.tree(workspace.id, d)] as const;
          } catch (e) {
            if (d === '') setFailed(why(e));
            return [d, null] as const;
          }
        }),
      );
      setKids((k) => {
        const next = { ...k };
        for (const [d, got] of read) {
          if (got) next[d] = got.entries;
          else delete next[d];
        }
        return next;
      });
      if (read.some(([, got]) => got?.truncated)) setCut(true);
      if (read.some(([d, got]) => d === '' && got)) setFailed('');
    },
    [client, workspace.id],
  );

  useEffect(() => {
    setKids({});
    setOpen(new Set());
    setCut(false);
    void reload(['']);
  }, [reload]);

  useEffect(() => {
    if (tick > 0) void reload(['', ...open]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  const toggle = async (n: Entry) => {
    if (n.kind !== 'dir') {
      void work.openFile(n.path).catch((e) => work.toast(why(e)));
      return;
    }
    const next = new Set(open);
    if (next.has(n.path)) next.delete(n.path);
    else {
      next.add(n.path);
      if (!kids[n.path]) await reload([n.path]);
    }
    setOpen(next);
  };

  const rowMenu = (e: React.MouseEvent, n: Entry) => {
    if (n.kind === 'dir') return;
    e.preventDefault();
    e.stopPropagation();
    setMenu({
      x: e.clientX,
      y: e.clientY,
      items: [
        { label: 'Open in the Editor', onPick: () => void work.openFile(n.path).catch((err) => work.toast(why(err))) },
        { label: 'Show in Preview', onPick: () => work.preview(n.path) },
      ],
    });
  };

  const row = (n: Entry, depth: number, label = n.name) => (
    <div
      key={n.path}
      role="treeitem"
      aria-expanded={n.kind === 'dir' ? open.has(n.path) : undefined}
      aria-selected={active === n.path}
      tabIndex={0}
      className={`frow ${active === n.path ? 'on' : ''}`}
      style={{ paddingLeft: 8 + depth * 12 }}
      title={n.path}
      onClick={() => void toggle(n)}
      onKeyDown={(e) => e.key === 'Enter' && void toggle(n)}
      onContextMenu={(e) => rowMenu(e, n)}
    >
      <span className={`caret ${n.kind === 'dir' ? (open.has(n.path) ? 'open' : '') : 'leaf'}`}>▸</span>
      <Icon d={n.kind === 'dir' ? WICON.folder : WICON.file} size={14} />
      <span className={n.kind === 'dir' ? 'fname dir' : 'fname'}>{label}</span>
    </div>
  );

  const walk = (dir: string, depth: number): React.ReactNode[] => {
    const out: React.ReactNode[] = [];
    for (const n of kids[dir] ?? []) {
      out.push(row(n, depth));
      if (n.kind === 'dir' && open.has(n.path)) out.push(...walk(n.path, depth + 1));
    }
    return out;
  };

  // The search is over the names read so far: the folders opened, and the top.
  const q = query.trim().toLowerCase();
  const hits = q
    ? Object.values(kids)
        .flat()
        .filter((n) => n.kind === 'file' && n.path.toLowerCase().includes(q))
        .sort((a, b) => a.path.localeCompare(b.path))
    : null;

  return (
    <div className="pane files">
      <div className="ptool">
        <input className="psearch" value={query} placeholder="Search files" aria-label="Search files" spellCheck={false} onChange={(e) => setQuery(e.target.value)} />
        <WorkspacePick />
        <button type="button" className="ibtn" title="Refresh" aria-label="Refresh the files" onClick={() => void reload(['', ...open])}>
          <Icon d={WICON.refresh} />
        </button>
      </div>
      <div className="ftree" role="tree" aria-label={`Files of ${workspace.name}`}>
        {failed ? (
          <p className="dim pad">{failed}</p>
        ) : hits ? (
          hits.length ? (
            hits.map((n) => row(n, 0, n.path))
          ) : (
            <p className="dim pad">No file in the folders you opened matches "{query}".</p>
          )
        ) : (
          <>
            {walk('', 0)}
            {kids[''] && !kids[''].length && <p className="dim pad">Nothing here yet. The crew will fill it.</p>}
            {cut && <p className="dim pad">A folder has more files than are listed here.</p>}
          </>
        )}
      </div>
      {menu && <Menu {...menu} label="File" onClose={() => setMenu(null)} />}
    </div>
  );
}

export function FilesPanel() {
  return <Ready>{(client, workspace) => <Tree key={workspace.id} client={client} workspace={workspace} />}</Ready>;
}
