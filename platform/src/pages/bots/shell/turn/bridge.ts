// The host's side of an MCP App's bridge (MCP Apps 2026-01-26: JSON-RPC over postMessage between the page in its
// sandboxed frame and the host around it). The page asks `ui/initialize`, says `ui/notifications/initialized`, and is
// then told what its tool was given and answered (`ui/notifications/tool-input`, `ui/notifications/tool-result`);
// after that it may ask for a link to be opened, a tool to be called, or say how tall it is. Pure of React: `serve`
// takes the frame's window and what the host can do, and returns how to stop.

export const PROTOCOL = '2026-01-26';
export const MIN_HEIGHT = 80;
export const MAX_HEIGHT = 900;

type Rpc = { jsonrpc?: string; id?: string | number; method?: string; params?: Record<string, unknown> };

export type Host = {
  /** The frame's own window: only its messages are heard, and answers go to it alone. */
  frame: () => Window | null;
  /** What the page's tool was given, and what it answered (the page renders these). */
  input: unknown;
  result: unknown;
  /** Called with the page's height as it reports it, clamped. */
  onSize: (height: number) => void;
  /** A tool the page calls; left out, the page may call none. */
  callTool?: (name: string, args: unknown) => Promise<unknown>;
  /** A link the page asks to open; only the web. */
  openLink: (url: string) => void;
};

const text = (value: unknown): string => (typeof value === 'string' ? value : JSON.stringify(value ?? null));

/** What the page is told its tool answered, as MCP has a tool's result. */
export const toolResult = (result: unknown) => ({ content: [{ type: 'text', text: text(result) }], structuredContent: result ?? {}, isError: false });

const CONTEXT = { theme: 'dark', displayMode: 'inline', availableDisplayModes: ['inline'], platform: 'web' };
const INITIALIZED = { protocolVersion: PROTOCOL, hostInfo: { name: 'Glyphh', version: '1' }, hostContext: CONTEXT };

/** Answers the page's requests until stopped. */
export function serve(host: Host): () => void {
  const send = (message: Record<string, unknown>) => host.frame()?.postMessage({ jsonrpc: '2.0', ...message }, '*');
  const asked = async (method: string, params: Record<string, unknown>): Promise<unknown> => {
    if (method === 'ui/initialize') return { ...INITIALIZED, hostCapabilities: { openLinks: {}, ...(host.callTool ? { serverTools: {} } : {}) } };
    if (method === 'ping' || method === 'ui/message' || method === 'ui/update-model-context') return {};
    if (method === 'ui/request-display-mode') return { mode: 'inline' };
    if (method === 'ui/open-link') {
      const url = String(params.url ?? '');
      if (!/^https?:\/\//i.test(url)) throw new Error('Only a web link can be opened.');
      host.openLink(url);
      return {};
    }
    if (method === 'tools/call' && host.callTool) return host.callTool(String(params.name ?? ''), params.arguments ?? {});
    throw Object.assign(new Error(`${method} is not available here.`), { code: -32601 });
  };
  const told = (method: string, params: Record<string, unknown>) => {
    if (method === 'ui/notifications/initialized') {
      send({ method: 'ui/notifications/tool-input', params: { arguments: host.input ?? {} } });
      send({ method: 'ui/notifications/tool-result', params: toolResult(host.result) });
    }
    if (method === 'ui/notifications/size-changed' && typeof params.height === 'number') host.onSize(Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, Math.ceil(params.height))));
  };
  const heard = (event: MessageEvent) => {
    const message = event.data as Rpc | null;
    if (event.source !== host.frame() || !message || message.jsonrpc !== '2.0' || typeof message.method !== 'string') return;
    const params = message.params ?? {};
    if (message.id === undefined) return told(message.method, params);
    const id = message.id;
    asked(message.method, params).then(
      (result) => send({ id, result }),
      (err: Error & { code?: number }) => send({ id, error: { code: err.code ?? -32000, message: err.message } }),
    );
  };
  window.addEventListener('message', heard);
  return () => window.removeEventListener('message', heard);
}

/**
 * The page as the frame is given it: locked down by a policy of its own (inline script and style only, pictures from
 * the web, nothing fetched or framed), whatever the page itself says. The frame is sandboxed with scripts alone, so the
 * page has no origin: it cannot read the platform's storage, cookies or pages.
 */
export function framed(html: string): string {
  const policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: https:; font-src data:";
  const meta = `<meta http-equiv="Content-Security-Policy" content="${policy}">`;
  return /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (head) => head + meta) : meta + html;
}
