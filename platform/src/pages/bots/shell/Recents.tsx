// Recents, as the Glyphh Bot app's (glyphh-bot App.tsx, RecentsMenu): one dropdown of every past run, a bot's or the
// crew's. New chat; a search box; PINNED first, then by workspace; each row the task's first line, the crew's icon or
// the bot's cat, who and how long ago, and a dot while it waits on the person; "…" pins, archives or deletes it;
// Archived at the foot. The "Needs you" chip opens the same list, only the runs that wait.
import { useEffect, useState, type ReactNode } from 'react';
import type { Bot } from '@/api/bots';
import { useArchiveRecent, useDeleteRecent, usePinRecent, useRecentsPaged, type Recent } from '@/api/recents';
import { BotCat, Modal, useEscape } from './bits';
import { Icon, ICON } from './icons';

const PIN = 'M12 17v5M9 3h6l-1 6 3 3v2H7v-2l3-3z';

/** How long ago, as the app says it: now, 12m, 3h, 2d. */
export const short = (iso: string, now = Date.now()): string => {
  const s = Math.max(0, (now - Date.parse(iso)) / 1000);
  if (s < 60) return 'now';
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
};

type Section = { key: string; title: ReactNode; rows: Recent[] };

/** Pinned first, then the crew's runs by the repository they worked in, then the bots' own chats. */
function sections(rows: Recent[]): Section[] {
  const out: Section[] = [];
  const pinned = rows.filter((r) => r.pinned);
  if (pinned.length)
    out.push({
      key: 'pinned',
      title: (
        <>
          <Icon d={PIN} size={11} /> Pinned
        </>
      ),
      rows: pinned,
    });
  const groups = new Map<string, Recent[]>();
  for (const r of rows.filter((x) => !x.pinned)) {
    const key = r.workspace ? r.workspace.split('/').pop()! : 'Bots';
    groups.set(key, [...(groups.get(key) ?? []), r]);
  }
  for (const [key, list] of groups) out.push({ key, title: key, rows: list });
  return out;
}

type RowProps = { r: Recent; bot: Bot | undefined; current: boolean; onPick: (r: Recent) => void; onDelete: (r: Recent) => void };

function Row({ r, bot, current, onPick, onDelete }: RowProps) {
  const pin = usePinRecent();
  const archive = useArchiveRecent();
  const [menu, setMenu] = useState<{ left: number; top: number } | null>(null);
  useEscape(() => setMenu(null), menu !== null);
  const title = r.title || (r.kind === 'crew' ? 'From the instructions' : 'Run');
  const who = r.kind === 'crew' ? 'Crew' : r.bot_name;
  const act = (fn: () => void) => () => {
    setMenu(null);
    fn();
  };
  return (
    <div className={`rrow ${current ? 'on' : ''} ${menu ? 'menuopen' : ''}`}>
      <button type="button" className="rmain" onClick={() => onPick(r)}>
        <span className="rwho">{r.kind === 'crew' ? <Icon d={ICON.chat} size={14} /> : <BotCat look={bot?.look} mascot={bot?.mascot} size={18} />}</span>
        <span className="rtitle">{title}</span>
        <small>
          {who} · {short(r.created_at)}
        </small>
      </button>
      {r.waiting && <span className="rdot" role="img" aria-label="Needs you" title="Needs you" />}
      <button
        type="button"
        className="rmore"
        title="Pin, archive or delete"
        aria-label={`More: ${title}`}
        aria-haspopup="menu"
        aria-expanded={menu !== null}
        onClick={(e) => {
          const b = e.currentTarget.getBoundingClientRect();
          setMenu(menu ? null : { left: b.right - 160, top: b.bottom + 2 });
        }}
      >
        <Icon d={ICON.more} size={14} />
      </button>
      {menu && (
        <>
          <div className="veil clear menuveil" onMouseDown={() => setMenu(null)} />
          <div className="ctxmenu" role="menu" style={menu}>
            {r.archived ? (
              <button type="button" role="menuitem" onClick={act(() => archive.mutate({ id: r.id, archived: false }))}>
                Restore
              </button>
            ) : (
              <>
                <button type="button" role="menuitem" onClick={act(() => pin.mutate({ id: r.id, pinned: !r.pinned }))}>
                  {r.pinned ? 'Unpin' : 'Pin'}
                </button>
                <button type="button" role="menuitem" onClick={act(() => archive.mutate({ id: r.id, archived: true }))}>
                  Archive
                </button>
              </>
            )}
            <button type="button" role="menuitem" className="danger" onClick={act(() => onDelete(r))}>
              Delete…
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Panel({ bots, waiting, focus, onPick, onNew, onClose }: { bots: Bot[]; waiting: boolean; focus: string | null; onPick: (r: Recent) => void; onNew: () => void; onClose: () => void }) {
  const [words, setWords] = useState('');
  const [q, setQ] = useState('');
  const [archived, setArchived] = useState(false);
  const [deleting, setDeleting] = useState<Recent | null>(null);
  const remove = useDeleteRecent();
  useEffect(() => {
    const t = setTimeout(() => setQ(words.trim()), 200);
    return () => clearTimeout(t);
  }, [words]);
  // A page at a time: "Show more" asks for the next by the cursor the last one gave.
  const list = useRecentsPaged({ q: q || undefined, waiting: waiting || undefined, archived: archived || undefined });
  const rows = (list.data?.pages ?? []).flatMap((p) => p.recents);
  const groups: Section[] = archived ? (rows.length ? [{ key: 'archived', title: 'Archived', rows }] : []) : sections(rows);
  const pick = (r: Recent) => {
    onClose();
    onPick(r);
  };
  return (
    <div className="rpanel" role="dialog" aria-label={waiting ? 'Needs you' : 'Recents'}>
      <div className="rhead">
        {archived ? (
          <button type="button" className="link" onClick={() => setArchived(false)}>
            ‹ Recents
          </button>
        ) : (
          <b>{waiting ? 'Needs you' : 'Recents'}</b>
        )}
        <span className="spacer" />
        <button
          type="button"
          className="btn sm"
          onClick={() => {
            onClose();
            onNew();
          }}
        >
          <Icon d={ICON.plus} size={12} /> New chat
        </button>
      </div>
      <label className="rsearch">
        <Icon d={ICON.search} size={13} />
        <input type="search" aria-label="Search recents" placeholder="Search" value={words} onChange={(e) => setWords(e.target.value)} />
      </label>
      <div className="rlist">
        {list.error ? (
          <p className="err pad">{list.error.message}</p>
        ) : list.data === undefined ? (
          <p className="dim pad">Reading…</p>
        ) : groups.length ? (
          groups.map((s) => (
            <div key={s.key} className="rsec" role="group" aria-label={typeof s.title === 'string' ? s.title : 'Pinned'}>
              <div className="rlabel">{s.title}</div>
              {s.rows.map((r) => (
                <Row key={r.id} r={r} bot={bots.find((b) => b.slug === r.bot_slug)} current={r.id === focus} onPick={pick} onDelete={setDeleting} />
              ))}
            </div>
          ))
        ) : (
          <p className="dim pad">{q ? 'Nothing matches.' : archived ? 'Nothing archived.' : waiting ? 'Nothing waits on you.' : 'No chats yet. Every task you give shows up here.'}</p>
        )}
        {list.hasNextPage && (
          <button type="button" className="btn wide rmorepage" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
            {list.isFetchingNextPage ? 'Reading…' : 'Show more'}
          </button>
        )}
      </div>
      {!archived && !waiting && (
        <button type="button" className="rarch" onClick={() => setArchived(true)}>
          Archived <span className="dim">{list.data?.pages[0]?.archived_count ?? 0}</span>
        </button>
      )}
      {deleting && (
        <Modal
          title="Delete this chat?"
          small
          front
          onClose={() => {
            remove.reset();
            setDeleting(null);
          }}
        >
          <p className="dim">“{deleting.title || 'This run'}” goes for everyone here, with everything said in it. Pull requests it opened stay on GitHub. This cannot be undone.</p>
          {remove.error && <div className="err">{remove.error.message}</div>}
          <div className="row end">
            <button type="button" className="btn ghost" onClick={() => setDeleting(null)}>
              Cancel
            </button>
            <button type="button" className="btn danger solid" disabled={remove.isPending} onClick={() => remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}>
              Delete
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

type Props = {
  bots: Bot[];
  /** How many runs wait on a person now; the chip shows only when some do. */
  needsYou: number;
  focus: string | null;
  onPick: (r: Recent) => void;
  onNew: () => void;
};

/** The Recents chip with its dropdown, and beside it the "Needs you" chip that opens the same list, filtered. */
export function Recents({ bots, needsYou, focus, onPick, onNew }: Props) {
  const [open, setOpen] = useState<'all' | 'waiting' | null>(null);
  // A modal over the panel (Delete…) takes Escape first: the panel stays until it is gone.
  useEscape(() => !document.querySelector('.gb .veil.front') && setOpen(null), open !== null);
  return (
    <div className="recents">
      <button type="button" className={`chip ${open === 'all' ? 'on' : ''}`} title="Past chats" aria-label="Recents" aria-expanded={open === 'all'} onClick={() => setOpen(open === 'all' ? null : 'all')}>
        <Icon d={ICON.recents} size={14} /> <span className="chiptext">Recents</span> <span className="dim">▾</span>
      </button>
      {needsYou > 0 && (
        <button type="button" className={`chip needs ${open === 'waiting' ? 'on' : ''}`} title="Runs that wait on you" aria-expanded={open === 'waiting'} onClick={() => setOpen(open === 'waiting' ? null : 'waiting')}>
          <i className="led" /> Needs you · {needsYou}
        </button>
      )}
      {open && (
        <>
          <div className="veil clear" onMouseDown={() => setOpen(null)} />
          <Panel key={open} bots={bots} waiting={open === 'waiting'} focus={focus} onPick={onPick} onNew={onNew} onClose={() => setOpen(null)} />
        </>
      )}
    </div>
  );
}
