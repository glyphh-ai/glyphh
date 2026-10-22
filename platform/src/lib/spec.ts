import type { LeverValue, Spec, SpecOutput, SpecRole } from '@/api/ada';

/**
 * A model's spec as the platform reads it: checked as it is typed (the cloud's bounds and the kernel's shape, so most
 * mistakes show before the server is asked; the server's check is the last word), its roles, and examples to start
 * from. Bounds are the server's (`glyphh_ada/limits.py`) and the kernel's (`glyphh_spec.py`).
 */

export const modelNamePattern = /^[a-z0-9][a-z0-9_.-]{0,62}$/;
const namePattern = /^[A-Za-z_][A-Za-z0-9_-]{0,63}$/;
const specBytesMax = 64 * 1024;
const bounds = { dimension: 8192, roles: 64, outputs: 20, values: 200, k: 200 };

export type Problem = { path: string; message: string };
export type Checked = { spec: Spec; problems: [] } | { spec: null; problems: Problem[] };

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const unit = (v: unknown) => typeof v === 'number' && v >= 0 && v <= 1;

/** Where a JSON parse failed, as a line and column, from the engine's own message. */
function parseProblem(text: string, error: unknown): Problem {
  const message = error instanceof Error ? error.message : String(error);
  const at = /position (\d+)/.exec(message);
  if (!at) return { path: 'JSON', message: 'This is not valid JSON.' };
  const before = text.slice(0, Number(at[1])).split('\n');
  return { path: 'JSON', message: `Not valid JSON at line ${before.length}, column ${before.at(-1)!.length + 1}.` };
}

function checkRole(role: unknown, at: string, problems: Problem[]): void {
  if (!isObject(role)) return void problems.push({ path: at, message: 'A role is an object with a name.' });
  if (typeof role.name !== 'string' || !namePattern.test(role.name)) {
    problems.push({ path: `${at}.name`, message: 'A name is 1 to 64 letters, digits, _ or -, not starting with a digit.' });
  }
  for (const weight of ['similarity_weight', 'security_weight']) {
    if (weight in role && !unit(role[weight])) problems.push({ path: `${at}.${weight}`, message: 'A number from 0 to 1.' });
  }
  if ('key_part' in role && typeof role.key_part !== 'boolean') problems.push({ path: `${at}.key_part`, message: 'true or false.' });
  const numeric = role.numeric_config;
  if (numeric !== undefined && numeric !== null) {
    const n = isObject(numeric) ? numeric : {};
    const [low, high, width] = [n.min_value, n.max_value, n.bin_width];
    if (typeof low !== 'number' || typeof high !== 'number' || typeof width !== 'number' || high <= low || width <= 0) {
      problems.push({ path: `${at}.numeric_config`, message: 'Needs min_value below max_value and a bin_width above 0.' });
    } else if ((high - low) / width > 1000) {
      problems.push({ path: `${at}.numeric_config`, message: 'At most 1,000 bins.' });
    }
  }
  if (role.text_encoding !== undefined && role.text_encoding !== null && role.text_encoding !== 'bag_of_words') {
    problems.push({ path: `${at}.text_encoding`, message: 'Is "bag_of_words" or left out.' });
  }
  if (numeric && role.text_encoding) problems.push({ path: at, message: 'A role is numeric or text, not both.' });
}

function named(list: unknown, at: string, what: string, problems: Problem[]): Record<string, unknown>[] {
  if (!Array.isArray(list) || list.length === 0) {
    problems.push({ path: at, message: `At least one ${what}.` });
    return [];
  }
  const seen = new Set<string>();
  for (const item of list) {
    const name = isObject(item) ? item.name : undefined;
    if (typeof name === 'string' && seen.has(name)) problems.push({ path: at, message: `“${name}” is named twice.` });
    if (typeof name === 'string') seen.add(name);
  }
  return list.filter(isObject);
}

function checkOutput(output: unknown, at: string, problems: Problem[]): void {
  if (output === undefined) return;
  if (!isObject(output)) return void problems.push({ path: at, message: 'An object: costs, ask, ask_below, values.' });
  for (const bar of ['ask', 'ask_below']) {
    if (bar in output && typeof output[bar] !== 'number') problems.push({ path: `${at}.${bar}`, message: 'A number.' });
  }
  if ('costs' in output && (!isObject(output.costs) || !Object.values(output.costs).every(isObject))) {
    problems.push({ path: `${at}.costs`, message: 'An object of decided outcome → {true outcome: cost}.' });
  }
  const values = output.values;
  if (values !== undefined && (!Array.isArray(values) || !values.every((v) => typeof v === 'string' && v))) {
    problems.push({ path: `${at}.values`, message: 'A list of outcomes.' });
  } else if (Array.isArray(values) && values.length > bounds.values) {
    problems.push({ path: `${at}.values`, message: `At most ${bounds.values} outcomes.` });
  }
}

/** The spec's problems as typed, first to last; none means the server is worth asking. */
export function checkSpec(text: string): Checked {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    return { spec: null, problems: [parseProblem(text, error)] };
  }
  const problems: Problem[] = [];
  if (new TextEncoder().encode(text).length > specBytesMax) problems.push({ path: 'spec', message: 'A spec is at most 64 KB of JSON.' });
  if (!isObject(parsed)) return { spec: null, problems: [{ path: 'spec', message: 'A spec is a JSON object: name, layers, output, settings.' }] };
  if (typeof parsed.name !== 'string' || !namePattern.test(parsed.name)) {
    problems.push({ path: 'name', message: 'A name is 1 to 64 letters, digits, _ or -, not starting with a digit.' });
  }
  if ('dimension' in parsed) {
    const dim = parsed.dimension;
    if (typeof dim !== 'number' || !Number.isInteger(dim) || dim < 256 || dim > bounds.dimension) {
      problems.push({ path: 'dimension', message: `A whole number from 256 to ${bounds.dimension.toLocaleString('en-GB')}.` });
    }
  }
  if ('seed' in parsed && !Number.isInteger(parsed.seed)) problems.push({ path: 'seed', message: 'A whole number.' });
  let roles = 0;
  named(parsed.layers, 'layers', 'layer', problems).forEach((layer, i) => {
    const lp = `layers[${i}]`;
    if (typeof layer.name !== 'string' || !namePattern.test(layer.name)) problems.push({ path: `${lp}.name`, message: 'A layer needs a name.' });
    named(layer.segments, `${lp}.segments`, 'segment', problems).forEach((segment, j) => {
      const sp = `${lp}.segments[${j}]`;
      if (typeof segment.name !== 'string' || !namePattern.test(segment.name)) problems.push({ path: `${sp}.name`, message: 'A segment needs a name.' });
      const list = Array.isArray(segment.roles) ? segment.roles : [];
      named(segment.roles, `${sp}.roles`, 'role', problems);
      list.forEach((role, k) => checkRole(role, `${sp}.roles[${k}]`, problems));
      roles += list.length;
    });
  });
  if (roles > bounds.roles) problems.push({ path: 'layers', message: `A cloud model has at most ${bounds.roles} roles.` });
  checkOutput(parsed.output, 'output', problems);
  if (parsed.outputs !== undefined) {
    if (!isObject(parsed.outputs)) problems.push({ path: 'outputs', message: 'An object: output name → {values, costs, ask}.' });
    else {
      if (Object.keys(parsed.outputs).length > bounds.outputs) problems.push({ path: 'outputs', message: `At most ${bounds.outputs} named outputs.` });
      for (const [name, output] of Object.entries(parsed.outputs)) checkOutput(output, `outputs.${name}`, problems);
    }
  }
  if (parsed.settings !== undefined) {
    if (!isObject(parsed.settings)) problems.push({ path: 'settings', message: 'An object of settings.' });
    else for (const [name, value] of Object.entries(parsed.settings)) {
      const problem = leverProblem(name, value as LeverValue);
      if (problem) problems.push({ path: `settings.${name}`, message: problem });
    }
  }
  return problems.length ? { spec: null, problems } : { spec: parsed as Spec, problems: [] };
}

/** A role with its path, layer.segment.role, as cases and CSV headers name it. */
export type RolePath = { path: string; layer: string; segment: string; role: SpecRole };

export function rolesOf(spec: Spec): RolePath[] {
  return spec.layers.flatMap((layer) =>
    layer.segments.flatMap((segment) => segment.roles.map((role) => ({ path: `${layer.name}.${segment.name}.${role.name}`, layer: layer.name, segment: segment.name, role }))),
  );
}

/** The outputs a model decides: the default one, then its named ones. */
export function outputsOf(spec: Spec): string[] {
  return ['default', ...Object.keys(spec.outputs ?? {})];
}

export function outputOf(spec: Spec, name: string): SpecOutput | undefined {
  return name === 'default' ? spec.output : spec.outputs?.[name];
}

/** A case in the spec's shape, {layer: {segment: {role: value}}}, from values by role path; empty ones left out. */
export function caseFrom(spec: Spec, values: Record<string, string>): Record<string, unknown> {
  const data: Record<string, Record<string, Record<string, unknown>>> = {};
  for (const { path, layer, segment, role } of rolesOf(spec)) {
    const raw = values[path]?.trim();
    if (!raw) continue;
    const value = role.numeric_config ? Number(raw) : raw;
    ((data[layer] ??= {})[segment] ??= {})[role.name] = value;
  }
  return data;
}

// The levers (docs/specs/ada-cloud.md 5.1; the kernel's Settings.RANGES, k held to the cloud's 200).

export type Lever = {
  name: string;
  label: string;
  about: string;
  kind: 'int' | 'float' | 'bool' | 'choice';
  min?: number;
  max?: number;
  step?: number;
  choices?: string[];
  /** A number that may be left empty (none). */
  optional?: boolean;
  /** What a change does: on at once, or a new store of the cases written first. */
  effect: 'live' | 'reencode' | 'recalibrate';
};

export const levers: Lever[] = [
  { name: 'k', label: 'Precedents that vote', about: 'How many of the nearest precedents vote on an answer.', kind: 'int', min: 1, max: bounds.k, effect: 'live' },
  { name: 'min_sim', label: 'Least similarity', about: 'How alike a precedent must be to vote. Higher says nothing rather than guess.', kind: 'float', min: 0, max: 1, step: 0.01, effect: 'live' },
  { name: 'word_evidence', label: 'Word evidence', about: 'How much a case’s words weigh on the vote.', kind: 'float', min: 0, max: 5, step: 0.1, effect: 'live' },
  { name: 'shortlist', label: 'Shortlist', about: 'Candidates a read re-ranks exactly: 0 reads every precedent, else 100 to 10,000.', kind: 'int', min: 0, max: 10000, effect: 'live' },
  { name: 'exact_below', label: 'Read whole below', about: 'A model holding fewer precedents is read whole.', kind: 'int', min: 0, max: 100_000_000, effect: 'live' },
  { name: 'refresh_every', label: 'Learn again every', about: 'Learn again each time the model holds so many more precedents. Empty: only when asked.', kind: 'int', min: 10, max: 1_000_000, optional: true, effect: 'live' },
  { name: 'calibrate_by', label: 'Calibrate by', about: 'loss: probabilities that mean what they say. cost: probabilities that decide best by the costs.', kind: 'choice', choices: ['loss', 'cost'], effect: 'recalibrate' },
  { name: 'calibrate_sample', label: 'Calibration sample', about: 'The newest precedents a calibration holds out.', kind: 'int', min: 10, max: 1_000_000, effect: 'recalibrate' },
  { name: 'word_weights', label: 'Word weights', about: 'Learn a weight for each word of a text role.', kind: 'bool', effect: 'reencode' },
  { name: 'word_floor', label: 'Word floor', about: 'The least a learned word weighs.', kind: 'float', min: 0, max: 1, step: 0.01, effect: 'reencode' },
  { name: 'interactions', label: 'Role pairs', about: 'Learn pairs of roles that tell more together.', kind: 'bool', effect: 'reencode' },
  { name: 'max_interactions', label: 'Most role pairs', about: 'At most this many pairs of roles.', kind: 'int', min: 0, max: 50, effect: 'reencode' },
  { name: 'rare', label: 'Rare below', about: 'Values, words and pairs seen fewer times are not learned from.', kind: 'int', min: 1, max: 100_000, effect: 'reencode' },
  { name: 'word_pairs', label: 'Word pairs', about: 'Learn pairs of words, for intents that are phrases.', kind: 'bool', effect: 'reencode' },
  { name: 'max_word_pairs', label: 'Most word pairs', about: 'At most this many word pairs per text role.', kind: 'int', min: 0, max: 200, effect: 'reencode' },
  { name: 'lexicon', label: 'Lexicon', about: 'Read words through WordNet and Moby: synonyms and near words.', kind: 'bool', effect: 'reencode' },
];

export const effectText: Record<Lever['effect'], string> = {
  live: 'Applies at once',
  recalibrate: 'Recalibrates',
  reencode: 'Rewrites the cases',
};

export const leverOf = (name: string) => levers.find((lever) => lever.name === name);

/** A lever's value out of range, in words; null when it is fine. Unknown levers are the server's to judge. */
export function leverProblem(name: string, value: LeverValue): string | null {
  const lever = leverOf(name);
  if (!lever) return null;
  if (lever.kind === 'bool') return typeof value === 'boolean' ? null : 'true or false.';
  if (lever.kind === 'choice') return lever.choices!.includes(String(value)) ? null : `One of ${lever.choices!.join(', ')}.`;
  if (value === null && lever.optional) return null;
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'A number.';
  if (lever.kind === 'int' && !Number.isInteger(value)) return 'A whole number.';
  if (value < lever.min! || value > lever.max!) return `From ${lever.min!.toLocaleString('en-GB')} to ${lever.max!.toLocaleString('en-GB')}.`;
  if (name === 'shortlist' && value > 0 && value < 100) return '0, or 100 to 10,000.';
  return null;
}

/** A lever's value as typed into its field: a number, empty (none), a choice or a switch. */
export function leverFromText(lever: Lever | undefined, text: string): LeverValue {
  if (!lever || lever.kind === 'choice') return text;
  if (text.trim() === '' && lever.optional) return null;
  return text.trim() === '' ? Number.NaN : Number(text);
}

/** Settings changes, in words: "word_evidence 1, lexicon off". */
export function changesText(changes: Record<string, LeverValue>): string {
  return Object.entries(changes)
    .map(([name, value]) => `${name} ${value === true ? 'on' : value === false ? 'off' : value === null ? 'none' : value}`)
    .join(', ');
}

// Examples to start from, each a spec the kernel takes.

const ticket: Spec = {
  name: 'tickets',
  layers: [
    {
      name: 'ticket',
      segments: [
        {
          name: 'about',
          roles: [
            { name: 'subject', text_encoding: 'bag_of_words' },
            { name: 'product' },
            { name: 'plan' },
            { name: 'id', key_part: true, similarity_weight: 0 },
          ],
        },
      ],
    },
  ],
  output: { ask_below: 0.6 },
};

const credit: Spec = {
  name: 'credit',
  layers: [
    {
      name: 'applicant',
      segments: [
        {
          name: 'money',
          roles: [
            { name: 'amount', numeric_config: { min_value: 0, max_value: 20000, bin_width: 500 } },
            { name: 'months', numeric_config: { min_value: 0, max_value: 72, bin_width: 6 } },
            { name: 'purpose' },
          ],
        },
        {
          name: 'person',
          roles: [
            { name: 'age', numeric_config: { min_value: 18, max_value: 80, bin_width: 5 } },
            { name: 'housing' },
            { name: 'job' },
          ],
        },
      ],
    },
  ],
  output: { costs: { good: { bad: 5 }, bad: { good: 1 } }, ask: 0.5 },
  settings: { calibrate_by: 'cost' },
};

const incident: Spec = {
  name: 'incidents',
  layers: [
    {
      name: 'error',
      segments: [
        {
          name: 'what',
          roles: [
            { name: 'message', text_encoding: 'bag_of_words' },
            { name: 'service' },
            { name: 'region' },
          ],
        },
      ],
    },
  ],
  output: { ask_below: 0.6 },
  outputs: { owner: { values: ['platform', 'payments', 'search'] } },
};

export const examples: Array<{ id: string; label: string; spec: Spec }> = [
  { id: 'tickets', label: 'Support tickets: route each to a team', spec: ticket },
  { id: 'credit', label: 'Credit: approve or refuse, by what a mistake costs', spec: credit },
  { id: 'incidents', label: 'Incidents: the fix and the owner', spec: incident },
];

export const specText = (spec: Spec) => JSON.stringify(spec, null, 2);
