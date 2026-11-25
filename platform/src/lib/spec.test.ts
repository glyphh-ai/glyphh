import { caseFrom, changesText, checkSpec, examples, leverFromText, leverOf, leverProblem, outputOf, outputsOf, rolesOf } from './spec';

const problems = (spec: unknown) => checkSpec(typeof spec === 'string' ? spec : JSON.stringify(spec)).problems.map((p) => `${p.path}: ${p.message}`);
const layer = (roles: unknown[]) => ({ name: 'a', segments: [{ name: 's', roles }] });

describe('checkSpec', () => {
  it.each(examples.map((e) => [e.id, e.spec] as const))('takes the %s example', (_, spec) => {
    expect(checkSpec(JSON.stringify(spec)).spec).toEqual(spec);
  });

  it('says where the JSON breaks, or that it is not JSON at all', () => {
    expect(problems('{\n  "name": "x",\n  oops')).toEqual([expect.stringMatching(/^JSON: Not valid JSON at line 3, column \d+\.$/)]);
    expect(checkSpec('[]').problems[0]!.message).toMatch(/A spec is a JSON object/);
  });

  it('reads a parse error without a position as plain invalid JSON', () => {
    const parse = JSON.parse;
    JSON.parse = () => {
      throw new SyntaxError('Unexpected end');
    };
    try {
      expect(problems('{')).toEqual(['JSON: This is not valid JSON.']);
    } finally {
      JSON.parse = parse;
    }
  });

  it('names each problem by its path', () => {
    expect(
      problems({
        name: '9bad',
        seed: 1.5,
        dimension: 100,
        layers: [
          {
            name: '',
            segments: [
              {
                name: 's',
                roles: [
                  'role',
                  { name: 'w', similarity_weight: 2, key_part: 'yes', text_encoding: 'tfidf' },
                  { name: 'n', numeric_config: { min_value: 0, max_value: 5000, bin_width: 1 } },
                  { name: 'm', numeric_config: { min_value: 0, max_value: 1, bin_width: 1 }, text_encoding: 'bag_of_words' },
                ],
              },
              { roles: [] },
            ],
          },
        ],
        output: { ask: 'often', costs: { a: 1 }, values: [''] },
        outputs: { many: { values: Array.from({ length: 201 }, (_, i) => `v${i}`) }, bad: 3 },
        settings: { k: 0, lexicon: 'yes', calibrate_by: 'both', shortlist: 50, refresh_every: null, word_floor: 'x', rare: 1.5, made_up: 1 },
      }),
    ).toEqual([
      'name: A name is 1 to 64 letters, digits, _ or -, not starting with a digit.',
      'dimension: A whole number from 256 to 8,192.',
      'seed: A whole number.',
      'layers[0].name: A layer needs a name.',
      'layers[0].segments[0].roles[0]: A role is an object with a name.',
      'layers[0].segments[0].roles[1].similarity_weight: A number from 0 to 1.',
      'layers[0].segments[0].roles[1].key_part: true or false.',
      'layers[0].segments[0].roles[1].text_encoding: Is "bag_of_words" or left out.',
      'layers[0].segments[0].roles[2].numeric_config: At most 1,000 bins.',
      'layers[0].segments[0].roles[3]: A role is numeric or text, not both.',
      'layers[0].segments[1].name: A segment needs a name.',
      'layers[0].segments[1].roles: At least one role.',
      'output.ask: A number.',
      'output.costs: An object of decided outcome → {true outcome: cost}.',
      'output.values: A list of outcomes.',
      'outputs.many.values: At most 200 outcomes.',
      'outputs.bad: An object: costs, ask, ask_below, values.',
      'settings.k: From 1 to 200.',
      'settings.lexicon: true or false.',
      'settings.calibrate_by: One of loss, cost.',
      'settings.shortlist: 0, or 100 to 10,000.',
      'settings.word_floor: A number.',
      'settings.rare: A whole number.',
    ]);
  });

  it('holds a cloud model to its bounds: roles, outputs, size, layers and settings', () => {
    const roles = Array.from({ length: 65 }, (_, i) => ({ name: `r${i}` }));
    expect(problems({ name: 'x', layers: [layer(roles)] })).toEqual(['layers: A cloud model has at most 64 roles.']);
    const outputs = Object.fromEntries(Array.from({ length: 21 }, (_, i) => [`o${i}`, {}]));
    expect(problems({ name: 'x', layers: [layer([{ name: 'r' }])], outputs })).toEqual(['outputs: At most 20 named outputs.']);
    expect(problems({ name: 'x', layers: [layer([{ name: 'r', lexicons: ['y'.repeat(70_000)] }])] })).toEqual(['spec: A spec is at most 64 KB of JSON.']);
    expect(problems({ name: 'x', layers: [] })).toEqual(['layers: At least one layer.']);
    expect(problems({ name: 'x', layers: [layer([{ name: 'r' }])], outputs: [], settings: [] })).toEqual([
      'outputs: An object: output name → {values, costs, ask}.',
      'settings: An object of settings.',
    ]);
  });
});

describe('a spec’s roles, outputs and cases', () => {
  const spec = examples.find((e) => e.id === 'incidents')!.spec;

  it('lists each role by its path, and the outputs it decides', () => {
    expect(rolesOf(spec).map((r) => r.path)).toEqual(['error.what.message', 'error.what.service', 'error.what.region']);
    expect(outputsOf(spec)).toEqual(['default', 'owner']);
    expect(outputOf(spec, 'default')).toEqual({ ask_below: 0.6 });
    expect(outputOf(spec, 'owner')!.values).toHaveLength(3);
  });

  it('makes a case in the spec’s shape, numbers as numbers and empty values left out', () => {
    const credit = examples.find((e) => e.id === 'credit')!.spec;
    expect(caseFrom(credit, { 'applicant.money.amount': '2500', 'applicant.money.purpose': ' car ', 'applicant.person.job': '' })).toEqual({
      applicant: { money: { amount: 2500, purpose: 'car' } },
    });
  });
});

describe('levers', () => {
  it('reads a lever’s typed value, and says what is wrong with it', () => {
    expect(leverFromText(leverOf('k'), '20')).toBe(20);
    expect(leverFromText(leverOf('refresh_every'), '')).toBeNull();
    expect(leverFromText(leverOf('k'), '')).toBeNaN();
    expect(leverFromText(leverOf('calibrate_by'), 'cost')).toBe('cost');
    expect(leverFromText(undefined, 'x')).toBe('x');
    expect(leverProblem('refresh_every', null)).toBeNull();
    expect(leverProblem('k', null)).toBe('A number.');
    expect(leverProblem('made_up', 3)).toBeNull();
    expect(leverProblem('word_weights', false)).toBeNull();
    expect(leverProblem('shortlist', 0)).toBeNull();
  });

  it('says settings changes in words', () => {
    expect(changesText({ word_evidence: 1, lexicon: false, interactions: true, refresh_every: null })).toBe('word_evidence 1, lexicon off, interactions on, refresh_every none');
  });
});
