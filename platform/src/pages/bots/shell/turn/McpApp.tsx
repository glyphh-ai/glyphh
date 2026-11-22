import { useEffect, useRef, useState } from 'react';
import { callMcpTool, useMcpResource, type RunApp } from '@/api/bots';
import { framed, serve } from './bridge';

/** A UI resource of Glyphh's own: its page is read from the server, and it may call the person's connector tools. */
const own = (uri: string) => uri.startsWith('ui://glyphh/');

/**
 * An MCP App a step's tool result carries, inline in the turn: its page in a sandboxed frame (scripts only, no origin
 * of its own, a locked-down content policy), talking to the platform over the MCP Apps bridge. The page is the
 * result's own when it embeds one; a resource of Glyphh's is read from the server by its address. Only Glyphh's own
 * pages may call tools; any page may ask for a web link to be opened, in a new tab.
 */
export function McpApp({ app }: { app: RunApp }) {
  const read = useMcpResource(app.html === null && own(app.uri) ? app.uri : null);
  const html = app.html ?? read.data?.text ?? null;
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(240);
  useEffect(() => {
    if (html === null) return;
    return serve({
      frame: () => frame.current?.contentWindow ?? null,
      input: app.input,
      result: app.result,
      onSize: setHeight,
      callTool: own(app.uri) ? callMcpTool : undefined,
      openLink: (url) => window.open(url, '_blank', 'noopener,noreferrer'),
    });
  }, [html, app.input, app.result, app.uri]);
  return (
    <section className="tapp" aria-label={`${app.title}, an app`}>
      <div className="tapp-head">
        <span className="kind">APP</span>
        <b>{app.title}</b>
      </div>
      {html !== null ? (
        <iframe ref={frame} title={app.title} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={framed(html)} style={{ height }} />
      ) : (
        <p className="tapp-note">{read.error ? 'This app could not be shown.' : read.isLoading ? 'Opening…' : 'This app did not come with a page to show.'}</p>
      )}
    </section>
  );
}
