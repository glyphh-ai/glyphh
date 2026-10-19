import { metrics, nodes } from '@/test/fixtures';
import { actorText, byNode, extraFields, levelBadge, linkText, nodeOptions, outcomeBadge, runtimeName, runtimeOptions, sourceText } from './telemetry';

describe('the telemetry words', () => {
  it('names the levels, tones the bad ones and shows one it does not know as it is', () => {
    expect(levelBadge('error')).toEqual({ tone: 'red', label: 'Error' });
    expect(levelBadge('WARN')).toEqual({ tone: 'amber', label: 'Warning' });
    expect(levelBadge('info')).toEqual({ tone: 'blue', label: 'Info' });
    expect(levelBadge('notice')).toEqual({ tone: 'neutral', label: 'Notice' });
    expect(levelBadge(undefined)).toBeNull();
  });

  it('tones an outcome from outcome.status: done green, failed red, an HTTP status refused, anything else plain', () => {
    expect(outcomeBadge({ 'outcome.status': 'done' })).toEqual({ tone: 'green', label: 'Done' });
    expect(outcomeBadge({ 'outcome.status': 'failed', 'outcome.code': 'E_MODEL' })).toEqual({ tone: 'red', label: 'Failed' });
    expect(outcomeBadge({ 'outcome.status': 403 })).toEqual({ tone: 'amber', label: 'Refused 403' });
    expect(outcomeBadge({ 'outcome.status': 'queued' })).toEqual({ tone: 'neutral', label: 'Queued' });
    expect(outcomeBadge({})).toBeNull();
    expect(outcomeBadge(null)).toBeNull();
  });

  it('says who did it from the flattened actor', () => {
    expect(actorText({ 'actor.type': 'key', 'actor.key_sha256': '9f86d081884c7d65' })).toBe('API key 9f86d081');
    expect(actorText({ 'actor.type': 'key' })).toBe('An API key');
    expect(actorText({ 'actor.type': 'sign-in', 'actor.sub': 'chris@example.com' })).toBe('chris@example.com (signed in)');
    expect(actorText({ 'actor.type': 'local' })).toBe('The local token');
    expect(actorText({ 'actor.type': 'server' })).toBe('Glyphh, over the link');
    expect(actorText({ 'actor.type': 'rrotor' })).toBe('rrotor');
    expect(actorText({ 'actor.type': 'anonymous' })).toBe('No credential');
    expect(actorText({ 'actor.type': 'robot' })).toBe('robot');
    expect(actorText({})).toBe('Not said');
  });

  it('writes a link state however it comes', () => {
    expect(linkText(true)).toBe('Linked');
    expect(linkText(false)).toBe('Not linked');
    expect(linkText('up')).toBe('Up');
    expect(linkText(null)).toBe('Not said');
  });

  it('gathers rrotor’s series by node: runs and those not done, run seconds, precedents across models against the cap, link, drops', () => {
    const [first, second] = byNode(metrics);
    expect(first).toMatchObject({ node_id: 'rrotor-1', runtime: 'Acme production', runs: 1_284, failed: 84, run_seconds: 5_400, precedents: 12_050, cap: 50_000, link: 'up', dropped: 0, at: '2026-10-16T13:58:00Z', other: [] });
    expect(second).toMatchObject({ node_id: 'rrotor-2', runs: 310, failed: 0, link: 'reconnecting', dropped: 12, at: '2026-10-16T13:57:00Z' });
  });

  it('keeps a series it has no column for, and leaves what a node did not send as null', () => {
    const odd = { runtime_id: 'rt-7f3a9c', node_id: null, name: 'rrotor.queue.depth', kind: 'gauge', value: 4 };
    const [node] = byNode([odd]);
    expect(node).toMatchObject({ runs: null, failed: null, run_seconds: null, precedents: null, cap: null, link: null, dropped: null, at: null, other: [odd] });
  });

  it('keeps the fields it does not show', () => {
    expect(extraFields({ at: 'x', body: 'm', region: 'eu', trace_id: 't', span_id: null, gone: undefined }, ['at', 'body'])).toEqual({ region: 'eu', trace_id: 't' });
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
