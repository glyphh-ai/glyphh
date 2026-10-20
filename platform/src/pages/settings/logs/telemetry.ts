import type { MetricPoint, RuntimeNode } from '@/api/types';
import type { ChipTone } from '@/ui';

/** rrotor's logs and drains docs: OpenTelemetry to your own collector, and RROTOR_SERVER_LOGS. */
export const selfHostingDocs = 'https://docs.glyphh.ai/logs';
export const otelEnv = 'OTEL_EXPORTER_OTLP_ENDPOINT';
export const serverLogsEnv = 'RROTOR_SERVER_LOGS';

type Badge = { tone: ChipTone; label: string };

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

const levels: Record<string, Badge> = {
  trace: { tone: 'neutral', label: 'Trace' },
  debug: { tone: 'neutral', label: 'Debug' },
  info: { tone: 'blue', label: 'Info' },
  warn: { tone: 'amber', label: 'Warning' },
  warning: { tone: 'amber', label: 'Warning' },
  error: { tone: 'red', label: 'Error' },
  fatal: { tone: 'red', label: 'Fatal' },
  critical: { tone: 'red', label: 'Critical' },
};

/** A log line's level as a chip; a level rrotor names that the platform does not know is shown as it is. */
export function levelBadge(level: string | null | undefined): Badge | null {
  if (!level) return null;
  return levels[level.toLowerCase()] ?? { tone: 'neutral', label: capital(level) };
}

/** The levels to filter by: the server reads one as it and above. */
export const levelOptions = [
  { value: '', label: 'All levels' },
  { value: 'debug', label: 'Debug and above' },
  { value: 'info', label: 'Info and above' },
  { value: 'warn', label: 'Warning and above' },
  { value: 'error', label: 'Error and above' },
  { value: 'fatal', label: 'Fatal' },
];

export const sinceOptions = [
  { value: '', label: 'Any time' },
  { value: '1h', label: 'Last hour' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
];

type Attributes = Record<string, unknown> | null | undefined;
const text = (value: unknown): string | null => (typeof value === 'string' && value ? value : typeof value === 'number' ? String(value) : null);

const statuses: Record<string, ChipTone> = { done: 'green', ok: 'green', failed: 'red', error: 'red' };

/**
 * How an audit event ended, from its `outcome.status`: done green, failed red, an HTTP status (a 401 or 403) amber as
 * refused. None when the event says nothing of it.
 */
export function outcomeBadge(attributes: Attributes): Badge | null {
  const status = attributes?.['outcome.status'];
  if (typeof status === 'number') return { tone: 'amber', label: `Refused ${status}` };
  const named = text(status);
  if (!named) return null;
  return { tone: statuses[named.toLowerCase()] ?? 'neutral', label: capital(named) };
}

/** Who did it, from the event's flattened `actor.*`: an API key by the start of its SHA-256, a sign-in by its subject. */
export function actorText(attributes: Attributes): string {
  const type = text(attributes?.['actor.type']);
  const sha = text(attributes?.['actor.key_sha256']);
  const sub = text(attributes?.['actor.sub']);
  switch (type) {
    case 'key':
      return sha ? `API key ${sha.slice(0, 8)}` : 'An API key';
    case 'sign-in':
      return sub ? `${sub} (signed in)` : 'Someone signed in';
    case 'local':
      return 'The local token';
    case 'server':
      return 'Glyphh, over the link';
    case 'rrotor':
      return 'rrotor';
    case 'anonymous':
      return 'No credential';
    case null:
      return 'Not said';
    default:
      return sub ?? type;
  }
}

/** The fields an audit line shows on its own; the rest go under Details. */
export const auditShown = ['actor.type', 'actor.key_sha256', 'actor.sub', 'via', 'outcome.status'];

/** A node's link to Glyphh, however rrotor states it. */
export function linkText(link: unknown): string {
  if (link === true) return 'Linked';
  if (link === false) return 'Not linked';
  if (typeof link === 'string' && link) return capital(link);
  if (typeof link === 'number') return link.toLocaleString('en-GB');
  if (link && typeof link === 'object') return JSON.stringify(link);
  return 'Not said';
}

/** The fields of a record the platform does not show on its own, kept to show beside the rest. */
export function extraFields(record: Record<string, unknown>, shown: readonly string[]): Record<string, unknown> {
  return Object.fromEntries(Object.entries(record).filter(([name, value]) => !shown.includes(name) && value !== undefined && value !== null));
}

/** A runtime's name from what the event says, else from the org's nodes, else its id. */
export function runtimeName(id: string | null | undefined, name: string | null | undefined, nodes: RuntimeNode[] | undefined): string {
  if (name) return name;
  const known = nodes?.find((node) => node.runtime_id === id)?.runtime;
  return known ?? id ?? 'A runtime';
}

/** Where a line came from: "Acme production · rrotor-1". */
export function sourceText(runtime: string, node: string | null | undefined): string {
  return node ? `${runtime} · ${node}` : runtime;
}

/** The runtimes and their nodes to filter by, from the org's nodes. */
export function runtimeOptions(nodes: RuntimeNode[] | undefined) {
  const seen = new Map<string, string>();
  for (const node of nodes ?? []) if (!seen.has(node.runtime_id)) seen.set(node.runtime_id, node.runtime ?? node.runtime_id);
  return [{ value: '', label: 'All runtimes' }, ...[...seen].map(([value, label]) => ({ value, label }))];
}

export function nodeOptions(nodes: RuntimeNode[] | undefined, runtime: string) {
  const named = (nodes ?? []).filter((node) => node.node_id && (!runtime || node.runtime_id === runtime)).map((node) => node.node_id!);
  return [{ value: '', label: 'All nodes' }, ...[...new Set(named)].map((value) => ({ value, label: value }))];
}

/** One node's latest metrics, gathered from its series. A figure the node has not sent is null. */
export type NodeMetrics = {
  key: string;
  runtime_id: string | null;
  runtime: string | null;
  node_id: string | null;
  runs: number | null;
  failed: number | null;
  run_seconds: number | null;
  precedents: number | null;
  cap: number | null;
  link: string | null;
  dropped: number | null;
  at: string | null;
  /** Series of names the platform has no column for. */
  other: MetricPoint[];
};

const add = (sum: number | null, value: number | null | undefined) => (typeof value === 'number' ? (sum ?? 0) + value : sum);

/**
 * rrotor's series gathered by runtime and node: `rrotor.runs` summed (and those whose status is not done),
 * `rrotor.run.seconds` the histograms' sums, `rrotor.precedents` summed across models against `rrotor.precedents.cap`,
 * `rrotor.link.state` its `state`, `rrotor.drain.dropped` summed across drains and signals; the newest point's time.
 */
export function byNode(points: MetricPoint[]): NodeMetrics[] {
  const nodes = new Map<string, NodeMetrics>();
  for (const p of points) {
    const key = `${p.runtime_id ?? ''}/${p.node_id ?? ''}`;
    let n = nodes.get(key);
    if (!n) {
      n = { key, runtime_id: p.runtime_id ?? null, runtime: p.runtime ?? null, node_id: p.node_id ?? null, runs: null, failed: null, run_seconds: null, precedents: null, cap: null, link: null, dropped: null, at: null, other: [] };
      nodes.set(key, n);
    }
    if (p.at && (!n.at || p.at > n.at)) n.at = p.at;
    switch (p.name) {
      case 'rrotor.runs':
        n.runs = add(n.runs, p.value);
        if (p.attributes?.status !== undefined && p.attributes.status !== 'done') n.failed = add(n.failed ?? 0, p.value);
        else n.failed ??= 0;
        break;
      case 'rrotor.run.seconds':
        n.run_seconds = add(n.run_seconds, p.value);
        break;
      case 'rrotor.precedents':
        n.precedents = add(n.precedents, p.value);
        break;
      case 'rrotor.precedents.cap':
        n.cap = typeof p.value === 'number' ? p.value : n.cap;
        break;
      case 'rrotor.link.state':
        n.link = text(p.attributes?.state) ?? n.link;
        break;
      case 'rrotor.drain.dropped':
        n.dropped = add(n.dropped, p.value);
        break;
      default:
        n.other.push(p);
    }
  }
  return [...nodes.values()];
}
