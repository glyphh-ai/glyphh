// The Preview panel: the Glyphh Bot app's Browser panel (glyphh-bot src/renderer/src/panels/Browser.tsx) cut down to
// what a page in a browser can do. It shows a file of the workspace as the page it is (index.html unless another is
// picked or typed), with the stylesheets and scripts it names beside it read from the machine too, in a frame that
// may run the page's scripts and nothing else: it has no access to Glyphh, to this page or to the machine. Images
// show as images. It does not browse the web.
import { useEffect, useRef, useState } from 'react';
import type { WorkClient, Workspace } from '@/api/work';
import { Icon } from '../icons';
import { WICON, why } from './bits';
import { Ready } from './data';
import { useWork, useWorkActions } from './store';

const HOME = 'index.html';
const isImage = (p: string) => /\.(png|jpe?g|gif|webp|bmp|ico|svg)$/i.test(p);
const local = (ref: string) => !/^([a-z][a-z0-9+.-]*:|\/\/|#)/i.test(ref);
const beside = (page: string, ref: string) => {
  const parts = (ref.startsWith('/') ? [] : page.split('/').slice(0, -1)).concat(ref.split(/[?#]/)[0]!.split('/'));
  const out: string[] = [];
  for (const p of parts) {
    if (p === '..') out.pop();
    else if (p && p !== '.') out.push(p);
  }
  return out.join('/');
};
const MOST = 20;

/** The page with the stylesheets and scripts it names from its own folder put inside it (a frame's page has no folder). */
export async function inlined(html: string, page: string, read: (path: string) => Promise<string | null>): Promise<string> {
  const wanted: { tag: string; path: string; css: boolean }[] = [];
  for (const m of html.matchAll(/<link\b[^>]*>/gi)) {
    const href = /\bhref\s*=\s*["']([^"']+)["']/i.exec(m[0])?.[1];
    if (href && /\brel\s*=\s*["']?stylesheet/i.test(m[0]) && local(href)) wanted.push({ tag: m[0], path: beside(page, href), css: true });
  }
  for (const m of html.matchAll(/<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["'][^>]*>\s*<\/script>/gi)) {
    if (local(m[1]!)) wanted.push({ tag: m[0], path: beside(page, m[1]!), css: false });
  }
  let out = html;
  for (const w of wanted.slice(0, MOST)) {
    const text = await read(w.path);
    if (text === null) continue;
    const module = !w.css && /\btype\s*=\s*["']module["']/i.test(w.tag);
    const made = w.css ? `<style>\n${text.replace(/<\/style/gi, '<\\/style')}\n</style>` : `<script${module ? ' type="module"' : ''}>\n${text.replace(/<\/script/gi, '<\\/script')}\n</script>`;
    out = out.replace(w.tag, () => made);
  }
  return out;
}

type Shown = { kind: 'page'; html: string } | { kind: 'image'; src: string } | { kind: 'text'; text: string } | { kind: 'none'; why: string };

function Page({ client, workspace }: { client: WorkClient; workspace: Workspace }) {
  const work = useWorkActions();
  const asked = useWork((s) => s.previewPath);
  const tick = useWork((s) => s.tick);
  const [bar, setBar] = useState(asked);
  const [shown, setShown] = useState<Shown | null>(null);
  const [again, setAgain] = useState(0);
  const made = useRef('');

  useEffect(() => setBar(asked), [asked]);

  useEffect(() => {
    let dead = false;
    const done = (s: Shown) => {
      if (!dead) setShown(s);
    };
    if (made.current) URL.revokeObjectURL(made.current);
    made.current = '';
    if (!asked) {
      setShown(null);
      return;
    }
    setShown(null);
    const text = async (path: string) => {
      const f = await client.file(workspace.id, path).catch(() => null);
      return f && !f.binary && f.text !== null ? f.text : null;
    };
    (async () => {
      if (isImage(asked)) {
        const blob = await client.raw(workspace.id, asked);
        if (dead) return;
        made.current = URL.createObjectURL(blob);
        return done({ kind: 'image', src: made.current });
      }
      const f = await client.file(workspace.id, asked);
      if (f.binary || f.text === null) return done({ kind: 'none', why: f.binary ? `${asked} is not a page, an image or text.` : `${asked} is too big to show here.` });
      if (/\.html?$/i.test(asked)) return done({ kind: 'page', html: await inlined(f.text, asked, text) });
      done({ kind: 'text', text: f.text });
    })().catch((e) => done({ kind: 'none', why: asked === HOME && /404|no such|not found/i.test(why(e)) ? `There is no ${HOME} in ${workspace.name} yet.` : why(e) }));
    return () => {
      dead = true;
    };
  }, [client, workspace.id, workspace.name, asked, tick, again]);

  useEffect(
    () => () => {
      if (made.current) URL.revokeObjectURL(made.current);
    },
    [],
  );

  const go = (path: string) => {
    const p = path.trim().replace(/^\.?\//, '');
    if (!p) return;
    if (p === asked) setAgain((n) => n + 1);
    else work.set({ previewPath: p });
  };

  return (
    <div className="pane browser">
      <div className="btabs">
        <div className="bt on" title={asked || 'Nothing shown yet'}>
          <span>{asked ? asked.split('/').pop() : 'Preview'}</span>
        </div>
      </div>
      <div className="urlbar">
        <button type="button" className="ibtn" title="Reload" aria-label="Reload the preview" onClick={() => setAgain((n) => n + 1)}>
          <Icon d={WICON.refresh} />
        </button>
        <input value={bar} spellCheck={false} placeholder="index.html" aria-label="File to show" onChange={(e) => setBar(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && go(bar)} />
        <button type="button" className="btn tiny" title={`Show ${workspace.name}’s ${HOME}`} onClick={() => go(HOME)}>
          Preview
        </button>
      </div>
      <div className="webviews">
        {shown?.kind === 'page' && (
          <div className="webwrap wk-web">
            {/* Scripts may run; nothing else: no same-origin, no forms, no popups, no top navigation. */}
            <iframe className="web" title={`Preview of ${asked}`} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={shown.html} />
          </div>
        )}
        {shown?.kind === 'image' && (
          <div className="wk-picture">
            <img src={shown.src} alt={asked} />
          </div>
        )}
        {shown?.kind === 'text' && <pre className="wk-plain">{shown.text}</pre>}
        {shown?.kind === 'none' && (
          <div className="empty">
            <b>Nothing to show</b>
            <p>{shown.why}</p>
          </div>
        )}
        {asked && !shown && <p className="dim pad wk-note">Reading {asked}…</p>}
        {!asked && (
          <div className="empty">
            <b>Preview</b>
            <p>Hit Preview to see what the crew built, or pick a file. It shows this repository’s own pages and images; it does not browse the web.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function PreviewPanel() {
  return <Ready>{(client, workspace) => <Page key={workspace.id} client={client} workspace={workspace} />}</Ready>;
}
