import { csvHeader, guessMapping } from './csv';
import { examples, outputsOf, rolesOf } from './spec';

describe('csvHeader', () => {
  it('reads the first record, with quotes, doubled quotes and a CRLF', () => {
    expect(csvHeader('a, "b,c" ,"say ""hi"""\r\n1,2,3')).toEqual(['a', 'b,c', 'say "hi"']);
  });

  it('keeps an empty column between others, not a trailing one', () => {
    expect(csvHeader('a,,b,\n')).toEqual(['a', '', 'b']);
  });
});

describe('guessMapping', () => {
  it('maps a role by its path or its only name, the outcomes, ts and id; the rest are skipped', () => {
    const spec = { ...examples.find((e) => e.id === 'incidents')!.spec };
    spec.layers = [...spec.layers, { name: 'more', segments: [{ name: 'x', roles: [{ name: 'service' }] }] }];
    const headers = ['error.what.message', 'region', 'service', 'outcome', 'outcome.owner', 'outcome.other', 'ts', 'id', 'notes'];
    expect(guessMapping(headers, rolesOf(spec), outputsOf(spec))).toEqual({
      'error.what.message': 'error.what.message',
      region: 'error.what.region',
      service: null, // two roles take this name: the person picks
      outcome: 'outcome',
      'outcome.owner': 'outcome.owner',
      'outcome.other': null,
      ts: 'ts',
      id: 'id',
      notes: null,
    });
  });
});
