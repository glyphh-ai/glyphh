import { adaReleases, releaseOf as made } from '@/test/ada';
import { choosable, defaultTarget, inlineParts, isBeta, notesBlocks, optionText, releaseOf, statusText, targetsFor, upgradePath } from './releases';

describe('Ada’s versions', () => {
  it('finds a version by its name or an alias, and knows a beta even before the list is read', () => {
    const releases = adaReleases();
    expect(releaseOf(releases, 'ada-1-0-beta')?.name).toBe('ada-1-0');
    expect(releaseOf(releases, 'ada-9-9')).toBeUndefined();
    expect(isBeta(releases, 'ada-1-2-beta')).toBe(true);
    expect(isBeta(releases, 'ada-1-1')).toBe(false);
    expect(isBeta(undefined, 'ada-2-0-beta')).toBe(true);
  });

  it('says each status, a deprecated one with its end', () => {
    expect(statusText({ status: 'stable', ends: null })).toBe('Stable');
    expect(statusText({ status: 'beta', ends: null })).toBe('Beta');
    expect(statusText({ status: 'deprecated', ends: '2027-04-18' })).toBe('Deprecated, ends 18 Apr 2027');
    expect(statusText({ status: 'retired', ends: '2026-10-01' })).toBe('Retired');
  });

  it('offers as targets every stable and open beta but the one the model runs; never a deprecated, retired or closed one', () => {
    const releases = adaReleases();
    expect(targetsFor(releases, 'ada-1-0').map((r) => r.name)).toEqual(['ada-1-2-beta', 'ada-1-1']);
    expect(targetsFor(releases, 'ada-1-1').map((r) => r.name)).toEqual(['ada-1-2-beta']);
    // An alias is the version it names.
    expect(targetsFor(releases, 'ada-1-0-beta').map((r) => r.name)).toEqual(['ada-1-2-beta', 'ada-1-1']);
    releases.versions[0]!.open = false;
    expect(targetsFor(releases, 'ada-1-1')).toEqual([]);
    expect(defaultTarget(releases, 'ada-1-1')).toBe('');
  });

  it('allows a downgrade to an older stable, and offers the latest stable first', () => {
    const releases = {
      latest_stable: 'ada-2-0',
      contract: 5,
      versions: [made({ name: 'ada-2-1-beta', kernel: '4.1.0', status: 'beta', beta: true }), made({ name: 'ada-2-0', kernel: '4.0.0' }), made({ name: 'ada-1-9', kernel: '3.20.0' })],
    };
    expect(targetsFor(releases, 'ada-2-0').map((r) => r.name)).toEqual(['ada-2-1-beta', 'ada-1-9']);
    expect(defaultTarget(releases, 'ada-1-9')).toBe('ada-2-0');
    expect(defaultTarget(releases, 'ada-2-0')).toBe('ada-2-1-beta');
    expect(releases.versions.map((r) => optionText(r, releases))).toEqual(['ada-2-1-beta (Beta)', 'ada-2-0 (latest stable)', 'ada-1-9']);
    expect(choosable(adaReleases()).map((r) => r.name)).toEqual(['ada-1-2-beta', 'ada-1-1']);
  });

  it('links to a model’s upgrade flow, with or without a version chosen', () => {
    expect(upgradePath('my model')).toBe('/models/my%20model?tab=versions&upgrade=');
    expect(upgradePath('tickets', 'ada-1-1')).toBe('/models/tickets?tab=versions&upgrade=ada-1-1');
  });
});

describe('release notes', () => {
  it('reads paragraphs apart by blank lines, and lines starting "- " as a list', () => {
    const notes = 'First line\ncarried on.\n\n- one\n- two\n  more of two\nAfter the list.\n\nLast.';
    expect(notesBlocks(notes)).toEqual([
      { kind: 'p', text: 'First line carried on.' },
      { kind: 'list', items: ['one', 'two more of two'] },
      { kind: 'p', text: 'After the list.' },
      { kind: 'p', text: 'Last.' },
    ]);
    expect(notesBlocks('')).toEqual([]);
  });

  it('marks **bold** and `code` in a line', () => {
    expect(inlineParts('Now **how sure** it is, by `calibrate_by`.')).toEqual([
      { kind: 'text', text: 'Now ' },
      { kind: 'bold', text: 'how sure' },
      { kind: 'text', text: ' it is, by ' },
      { kind: 'code', text: 'calibrate_by' },
      { kind: 'text', text: '.' },
    ]);
    expect(inlineParts('plain')).toEqual([{ kind: 'text', text: 'plain' }]);
  });
});
