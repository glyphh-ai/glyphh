import type { RunLink } from '@/api/bots';
import { fileKind, fileSize, linkBadge, linkWhere, type FileChip, type Shot } from './answer';

/** Images a run's steps brought back, inline as the chat's markdown shows one; a click opens it whole. */
export function Shots({ shots }: { shots: Shot[] }) {
  if (shots.length === 0) return null;
  return (
    <div className="tshots" aria-label="Images">
      {shots.map((s) => (
        <a key={s.src} href={s.src} target="_blank" rel="noopener noreferrer" title="Open the image">
          <img className="mdimg" src={s.src} alt={s.alt} loading="lazy" />
        </a>
      ))}
    </div>
  );
}

/** A card for a thing with a page (a pull request, a Slack message, an app, a doc), as the app's file card. */
export function LinkCards({ links }: { links: RunLink[] }) {
  if (links.length === 0) return null;
  return (
    <div className="fcards" aria-label="Links">
      {links.map((l) => (
        <a key={l.url} className="fcard tcard" href={l.url} target="_blank" rel="noopener noreferrer">
          <span className="kind">{linkBadge(l.kind)}</span>
          <span className="fmain">
            <b>{l.title}</b>
            <small>{linkWhere(l.url)}</small>
          </span>
          <span className="fmeta">
            <small>{l.kind}</small>
            <small>open ↗</small>
          </span>
        </a>
      ))}
    </div>
  );
}

/** Files a run's steps name, as the app's attachment chips; one with a page opens it. */
export function FileChips({ files }: { files: FileChip[] }) {
  if (files.length === 0) return null;
  return (
    <div className="atts tfiles" aria-label="Files">
      {files.map((f) => {
        const inner = (
          <>
            <span className="kind">{fileKind(f.name)}</span>
            <span className="an">{f.name}</span>
            {f.size !== null && <small>{fileSize(f.size)}</small>}
          </>
        );
        return f.url ? (
          <a key={f.name} className="att" href={f.url} target="_blank" rel="noopener noreferrer" title={f.name}>
            {inner}
          </a>
        ) : (
          <span key={f.name} className="att" title={f.name}>
            {inner}
          </span>
        );
      })}
    </div>
  );
}
