// The canvas and the file are one program: this module turns a program's `flow` (its FLOW's steps) into the canvas's
// nodes and edges and back, and makes each change the canvas can make (add, connect, disconnect, move, rename, delete)
// as a change to the steps. Pure: no React, no server. A step's `next` is the one place its edges live.
import type { Next, Step, StepKind } from '@/api/programs';

export type StepData = { step: Step };
/** A step on the canvas: its node id is the step's id, its type the step's kind, `data.step` the step but its place. */
export type StepNode = { id: string; type: StepKind; position: { x: number; y: number }; data: StepData };
/** An arrow from a step to the next: `key` is the result that takes it there, for `ask` and `branch`. */
export type StepEdge = { id: string; source: string; target: string; label?: string; data: { key: string | null } };

export const KINDS: readonly StepKind[] = ['tool', 'bot', 'ask', 'branch', 'code'];
/** Steps whose `next` is a map from their result to the next step. */
export const forks = (kind: StepKind) => kind === 'ask' || kind === 'branch';

/** How far apart the canvas lays steps that have no place of their own. */
export const GAP = { x: 300, y: 150 };

const isMap = (next: Next | undefined): next is Record<string, string | null> => typeof next === 'object' && next !== null;

/** A step's arrows: one for a step id, one per key of a map (a key whose step is none ends the program there). */
export function edgesOf(steps: Step[]): StepEdge[] {
  const ids = new Set(steps.map((s) => s.id));
  return steps.flatMap((s): StepEdge[] => {
    const next = s.next;
    if (typeof next === 'string') return ids.has(next) ? [{ id: edgeId(s.id, null, next), source: s.id, target: next, data: { key: null } }] : [];
    if (!isMap(next)) return [];
    return Object.entries(next).flatMap(([key, target]) =>
      target !== null && ids.has(target) ? [{ id: edgeId(s.id, key, target), source: s.id, target, label: key, data: { key } }] : [],
    );
  });
}

export const edgeId = (source: string, key: string | null, target: string) => (key === null ? `${source}->${target}` : `${source}[${key}]->${target}`);

/** The steps as nodes: each where it says (`at`), or laid out down the canvas below the ones that say. */
export function toNodes(steps: Step[]): StepNode[] {
  const placed = steps.filter((s) => s.at);
  let y = placed.length ? Math.max(...placed.map((s) => s.at![1])) + GAP.y : 0;
  return steps.map((s) => {
    const { at, ...step } = s;
    let position: { x: number; y: number };
    if (at) position = { x: at[0], y: at[1] };
    else {
      position = { x: 0, y };
      y += GAP.y;
    }
    return { id: s.id, type: s.kind, position, data: { step } };
  });
}

/** The canvas back as steps, in the nodes' order, each with its place (whole numbers). */
export function toFlow(nodes: ReadonlyArray<Pick<StepNode, 'position' | 'data'>>): Step[] {
  return nodes.map((n) => ({ ...n.data.step, at: [Math.round(n.position.x), Math.round(n.position.y)] }));
}

/** Both at once. */
export const toGraph = (steps: Step[]) => ({ nodes: toNodes(steps), edges: edgesOf(steps) });

/** A free id for a new step of a kind: `ask`, then `ask2`, `ask3`… */
export function freeId(steps: Step[], base: string): string {
  const ids = new Set(steps.map((s) => s.id));
  const root = base.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '') || 'step';
  const start = /^[a-z]/.test(root) ? root : `s_${root}`;
  if (!ids.has(start)) return start;
  for (let n = 2; ; n++) if (!ids.has(`${start}${n}`)) return `${start}${n}`;
}

/** A new step of a kind, as a person drops it on the canvas: what each kind needs, empty, ready to fill. */
export function newStep(kind: StepKind, steps: Step[], at: [number, number]): Step {
  const id = freeId(steps, kind === 'tool' ? 'use' : kind === 'bot' ? 'work' : kind === 'branch' ? 'choose' : kind);
  const round: [number, number] = [Math.round(at[0]), Math.round(at[1])];
  switch (kind) {
    case 'tool':
      return { id, kind, tool: '', input: {}, at: round };
    case 'bot':
      return { id, kind, task: '', at: round };
    case 'ask':
      return { id, kind, question: '', options: ['yes', 'no'], next: {}, at: round };
    case 'branch':
      return { id, kind, on: '', next: { else: null }, at: round };
    case 'code':
      return { id, kind, function: '', input: {}, at: round };
  }
}

/** The result a new arrow from a fork stands for: the first option (or `else`) not yet taken. */
export function freeKey(step: Step): string {
  const taken = isMap(step.next) ? step.next : {};
  const wanted = [...(step.kind === 'ask' ? (step.options ?? []) : []), 'else'];
  const free = wanted.find((k) => !taken[k]);
  if (free !== undefined) return free;
  for (let n = 2; ; n++) if (!taken[`case${n}`]) return `case${n}`;
}

const change = (steps: Step[], id: string, fn: (s: Step) => Step): Step[] => steps.map((s) => (s.id === id ? fn(s) : s));

/** An arrow drawn from one step to another: sets the source's `next` (for a fork, the given result or a free one). */
export function connect(steps: Step[], source: string, target: string, key?: string): Step[] {
  if (source === target) return steps;
  return change(steps, source, (s) => {
    if (!forks(s.kind)) return { ...s, next: target };
    const map = isMap(s.next) ? s.next : {};
    return { ...s, next: { ...map, [key ?? freeKey(s)]: target } };
  });
}

/** An arrow taken away: the step ends there (a fork keeps the result, going nowhere). */
export function disconnect(steps: Step[], edge: Pick<StepEdge, 'source' | 'target' | 'data'>): Step[] {
  return change(steps, edge.source, (s) => {
    if (!isMap(s.next)) {
      const { next: _, ...rest } = s;
      return s.next === edge.target ? rest : s;
    }
    const key = edge.data.key;
    if (key === null || s.next[key] !== edge.target) return s;
    return { ...s, next: { ...s.next, [key]: null } };
  });
}

/** A step taken off the canvas, with every arrow to it. */
export function removeStep(steps: Step[], id: string): Step[] {
  return steps
    .filter((s) => s.id !== id)
    .map((s) => {
      if (s.next === id) {
        const { next: _, ...rest } = s;
        return rest;
      }
      if (isMap(s.next) && Object.values(s.next).includes(id)) return { ...s, next: Object.fromEntries(Object.entries(s.next).map(([k, v]) => [k, v === id ? null : v])) };
      return s;
    });
}

const RESULT = (id: string) => new RegExp(`\\{${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=[.}])`, 'g');
function renameIn(value: unknown, from: string, to: string): unknown {
  if (typeof value === 'string') return value.replace(RESULT(from), `{${to}`);
  if (Array.isArray(value)) return value.map((v) => renameIn(v, from, to));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, renameIn(v, from, to)]));
  return value;
}

/** A valid step id: lowercase, starting with a letter. */
export const goodId = (id: string) => /^[a-z][a-z0-9_]*$/.test(id);

/** A step renamed, with every arrow to it and every `{old}` result named in a later step's words. */
export function renameStep(steps: Step[], from: string, to: string): Step[] {
  if (from === to || !goodId(to) || steps.some((s) => s.id === to)) return steps;
  return steps.map((s) => {
    const own = s.id === from ? { ...s, id: to } : s;
    const next = own.next === from ? to : isMap(own.next) ? Object.fromEntries(Object.entries(own.next).map(([k, v]) => [k, v === from ? to : v])) : own.next;
    const moved: Step = { ...own, ...(own.next === undefined ? {} : { next }) };
    for (const key of ['input', 'task', 'question', 'on', 'title'] as const) if (moved[key] !== undefined) (moved as Record<string, unknown>)[key] = renameIn(moved[key], from, to);
    return moved;
  });
}

/** A step changed in place (its id stays: renaming is renameStep); a key set to undefined is taken away. */
export const updateStep = (steps: Step[], id: string, patch: Partial<Omit<Step, 'id'>>): Step[] =>
  change(steps, id, (s) => Object.fromEntries(Object.entries({ ...s, ...patch }).filter(([, v]) => v !== undefined)) as Step);

/** A step moved on the canvas. */
export const moveStep = (steps: Step[], id: string, x: number, y: number): Step[] => change(steps, id, (s) => ({ ...s, at: [Math.round(x), Math.round(y)] }));

/** Two flows the same, for knowing whether the canvas has unsaved changes. */
export const sameFlow = (a: Step[], b: Step[]) => JSON.stringify(a) === JSON.stringify(b);

/** A tool key as words, when nothing better is known: `slack-send-message` is "Slack send message". */
export const humanize = (key: string) => {
  const words = key.replace(/[-_.]+/g, ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : '';
};
