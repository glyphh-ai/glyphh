import type { AuditActor, RuntimeNode } from '@/api/types';
import type { ChipTone } from '@/ui';

/** rrotor's self-hosting docs: OpenTelemetry to your own collector, and RROTOR_SERVER_LOGS. */
export const selfHostingDocs = 'https://github.com/glyphh-ai/rrotor/tree/main/docs/self-hosting';
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

/** The levels to filter by, as rrotor names them. */
export const levelOptions = [
  { value: '', label: 'All levels' },
  { value: 'debug', label: 'Debug' },
  { value: 'info', label: 'Info' },
  { value: 'warn', label: 'Warning' },
  { value: 'error', label: 'Error' },
];

export const sinceOptions = [
  { value: '', label: 'Any time' },
  { value: '1h', label: 'Last hour' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
];

const outcomes: Record<string, ChipTone> = {
  allowed: 'green',
  allow: 'green',
  ok: 'green',
  success: 'green',
  succeeded: 'green',
  denied: 'amber',
  deny: 'amber',
  refused: 'amber',
  error: 'red',
  failed: 'red',
  failure: 'red',
};

/** An audit event's outcome as a chip: allowed green, denied amber, failed red. */
export function outcomeBadge(outcome: string | null | undefined): Badge | null {
  if (!outcome) return null;
  return { tone: outcomes[outcome.toLowerCase()] ?? 'neutral', label: capital(outcome) };
}

const actorKinds: Record<string, string> = {
  user: 'member',
  member: 'member',
  key: 'API key',
  runtime_key: 'API key',
  api_key: 'API key',
  install: 'install',
  client: 'app',
  runtime: 'runtime',
  system: 'rrotor',
};

/** Who did it: "chris@example.com (member)", "Production app (API key)". */
export function actorText(actor: AuditActor | null | undefined): string {
  if (!actor) return 'Someone';
  const kind = actor.kind ? (actorKinds[actor.kind.toLowerCase()] ?? actor.kind) : null;
  if (actor.id && kind) return `${actor.id} (${kind})`;
  if (actor.id) return actor.id;
  // rrotor is written in lower case, even first.
  return kind ? (kind === 'rrotor' ? kind : capital(kind)) : 'Someone';
}

/** What it was done to, as the event names it. */
export function targetText(target: unknown): string {
  if (target === null || target === undefined || target === '') return '';
  if (typeof target === 'string' || typeof target === 'number' || typeof target === 'boolean') return String(target);
  return JSON.stringify(target);
}

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
  return Object.fromEntries(Object.entries(record).filter(([name, value]) => !shown.includes(name) && value !== undefined));
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
