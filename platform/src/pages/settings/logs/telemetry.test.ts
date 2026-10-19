import { nodes } from '@/test/fixtures';
import { actorText, extraFields, levelBadge, linkText, nodeOptions, outcomeBadge, runtimeName, runtimeOptions, sourceText, targetText } from './telemetry';

describe('the telemetry words', () => {
  it('names the levels, tones the bad ones and shows one it does not know as it is', () => {
    expect(levelBadge('error')).toEqual({ tone: 'red', label: 'Error' });
    expect(levelBadge('WARN')).toEqual({ tone: 'amber', label: 'Warning' });
    expect(levelBadge('info')).toEqual({ tone: 'blue', label: 'Info' });
    expect(levelBadge('notice')).toEqual({ tone: 'neutral', label: 'Notice' });
    expect(levelBadge(undefined)).toBeNull();
  });

  it('tones an outcome: allowed green, denied amber, failed red, anything else plain', () => {
    expect(outcomeBadge('allowed')).toEqual({ tone: 'green', label: 'Allowed' });
    expect(outcomeBadge('denied')).toEqual({ tone: 'amber', label: 'Denied' });
    expect(outcomeBadge('error')).toEqual({ tone: 'red', label: 'Error' });
    expect(outcomeBadge('queued')).toEqual({ tone: 'neutral', label: 'Queued' });
    expect(outcomeBadge(null)).toBeNull();
  });

  it('says who did it, from as much as the event says', () => {
    expect(actorText({ kind: 'key', id: 'Production app' })).toBe('Production app (API key)');
    expect(actorText({ kind: 'user', id: 'chris@example.com' })).toBe('chris@example.com (member)');
    expect(actorText({ kind: 'robot', id: 'r2' })).toBe('r2 (robot)');
    expect(actorText({ kind: 'system' })).toBe('rrotor');
    expect(actorText({ id: 'x' })).toBe('x');
    expect(actorText(null)).toBe('Someone');
  });

  it('writes a target or a link however the server sends it', () => {
    expect(targetText('credit-risk')).toBe('credit-risk');
    expect(targetText({ model: 'm-1' })).toBe('{"model":"m-1"}');
    expect(targetText(null)).toBe('');
    expect(linkText(true)).toBe('Linked');
    expect(linkText(false)).toBe('Not linked');
    expect(linkText('up')).toBe('Up');
    expect(linkText(undefined)).toBe('Not said');
  });

  it('keeps the fields it does not show', () => {
    expect(extraFields({ at: 'x', message: 'm', region: 'eu', trace_id: 't', gone: undefined }, ['at', 'message'])).toEqual({ region: 'eu', trace_id: 't' });
  });

  it('names a runtime from the event, else the org’s nodes, else its id', () => {
    expect(runtimeName('rt-self-1', 'Named', nodes.nodes)).toBe('Named');
    expect(runtimeName('rt-self-1', null, nodes.nodes)).toBe('Acme production');
    expect(runtimeName('rt-gone', undefined, nodes.nodes)).toBe('rt-gone');
    expect(sourceText('Acme production', 'rrotor-1')).toBe('Acme production · rrotor-1');
    expect(sourceText('Main', null)).toBe('Main');
  });

  it('offers each runtime once, and the named nodes of the one chosen', () => {
    expect(runtimeOptions(nodes.nodes)).toEqual([
      { value: '', label: 'All runtimes' },
      { value: 'rt-self-1', label: 'Acme production' },
      { value: 'rt-7f3a9c', label: 'Main' },
    ]);
    expect(nodeOptions(nodes.nodes, '').map((o) => o.value)).toEqual(['', 'rrotor-1', 'rrotor-2']);
    expect(nodeOptions(nodes.nodes, 'rt-7f3a9c')).toEqual([{ value: '', label: 'All nodes' }]);
    expect(runtimeOptions(undefined)).toEqual([{ value: '', label: 'All runtimes' }]);
  });
});
