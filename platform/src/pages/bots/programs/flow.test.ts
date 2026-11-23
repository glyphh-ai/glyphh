import type { Step } from '@/api/programs';
import { connect, disconnect, edgesOf, freeId, freeKey, GAP, humanize, moveStep, newStep, removeStep, renameStep, sameFlow, toFlow, toGraph, toNodes, updateStep } from './flow';

/** The spec's example: PR review digest. */
const digest = (): Step[] => [
  { id: 'find', kind: 'tool', tool: 'github-search-issues-and-pull-requests', input: { q: 'is:pr is:open review-requested:@me' }, next: 'pick', at: [0, 0] },
  { id: 'pick', kind: 'bot', task: 'Which of these need my review today?\n\n{find}', next: 'ok', at: [0, 150] },
  { id: 'ok', kind: 'ask', question: 'Post the digest?', options: ['yes', 'no'], next: { yes: 'post', no: null }, at: [0, 300] },
  { id: 'post', kind: 'tool', tool: 'slack-send-message', input: { channel: '@me', text: '{pick}' }, at: [0, 450] },
];

describe('a program’s steps as the canvas', () => {
  it('makes a node per step (its kind its type) and an arrow per next, a labelled one per result of a fork', () => {
    const { nodes, edges } = toGraph(digest());
    expect(nodes.map((n) => [n.id, n.type, n.position])).toEqual([
      ['find', 'tool', { x: 0, y: 0 }],
      ['pick', 'bot', { x: 0, y: 150 }],
      ['ok', 'ask', { x: 0, y: 300 }],
      ['post', 'tool', { x: 0, y: 450 }],
    ]);
    expect(nodes[0]!.data.step).not.toHaveProperty('at');
    // `no` goes nowhere: it ends the program, and has no arrow.
    expect(edges.map((e) => [e.source, e.target, e.label ?? null])).toEqual([
      ['find', 'pick', null],
      ['pick', 'ok', null],
      ['ok', 'post', 'yes'],
    ]);
  });

  it('round-trips: the canvas read back is the flow it was given, both ways', () => {
    const flow = digest();
    expect(toFlow(toNodes(flow))).toEqual(flow);
    const nodes = toNodes(flow);
    expect(toNodes(toFlow(nodes))).toEqual(nodes);
    expect(sameFlow(toFlow(toNodes(flow)), flow)).toBe(true);
  });

  it('keeps every key it was given (title, bot, function, branch maps, an explicit end)', () => {
    const flow: Step[] = [
      { id: 'a', kind: 'code', title: 'Tidy', bot: 'filer', function: 'tidy', input: { n: 3, deep: { x: [1, 2] } }, next: null, at: [10, 20] },
      { id: 'b', kind: 'branch', on: '{a.kind}', next: { invoice: 'a', else: null }, at: [300, 20] },
    ];
    expect(toFlow(toNodes(flow))).toEqual(flow);
    expect(edgesOf(flow).map((e) => e.id)).toEqual(['b[invoice]->a']);
  });

  it('lays steps with no place down the canvas, below those that have one', () => {
    const nodes = toNodes([{ id: 'a', kind: 'bot', at: [40, 100] }, { id: 'b', kind: 'bot' }, { id: 'c', kind: 'ask' }]);
    expect(nodes.map((n) => n.position)).toEqual([{ x: 40, y: 100 }, { x: 0, y: 100 + GAP.y }, { x: 0, y: 100 + 2 * GAP.y }]);
    expect(toFlow(nodes).map((s) => s.at)).toEqual([[40, 100], [0, 250], [0, 400]]);
    expect(toNodes([{ id: 'x', kind: 'tool' }])[0]!.position).toEqual({ x: 0, y: 0 });
  });

  it('draws no arrow to a step that is not there', () => {
    expect(edgesOf([{ id: 'a', kind: 'bot', next: 'gone' }, { id: 'b', kind: 'ask', next: { yes: 'gone' } }])).toEqual([]);
  });
});

describe('what the canvas does to the steps', () => {
  it('connects: one next for a step, a free result of a fork for a fork', () => {
    let flow = digest();
    flow = connect(flow, 'post', 'find');
    expect(flow[3]!.next).toBe('find');
    flow = connect(flow, 'ok', 'find');
    expect(flow[2]!.next).toEqual({ yes: 'post', no: 'find' });
    flow = connect(flow, 'ok', 'pick');
    expect(flow[2]!.next).toEqual({ yes: 'post', no: 'find', else: 'pick' });
    expect(connect(flow, 'ok', 'ok')).toBe(flow);
    expect(connect(flow, 'ok', 'post', 'maybe')[2]!.next).toMatchObject({ maybe: 'post' });
  });

  it('picks the result a new arrow from a fork stands for', () => {
    expect(freeKey({ id: 'q', kind: 'ask', options: ['a', 'b'], next: { a: 'x' } })).toBe('b');
    expect(freeKey({ id: 'q', kind: 'branch', next: {} })).toBe('else');
    expect(freeKey({ id: 'q', kind: 'branch', next: { else: 'x' } })).toBe('case2');
  });

  it('disconnects: the step ends there, a fork keeps its result going nowhere', () => {
    const flow = digest();
    const [first, , third] = edgesOf(flow);
    expect(disconnect(flow, first!)[0]).not.toHaveProperty('next');
    expect(disconnect(flow, third!)[2]!.next).toEqual({ yes: null, no: null });
  });

  it('removes a step and every arrow to it', () => {
    const flow = removeStep(digest(), 'post');
    expect(flow.map((s) => s.id)).toEqual(['find', 'pick', 'ok']);
    expect(flow[2]!.next).toEqual({ yes: null, no: null });
    const gone = removeStep(digest(), 'pick');
    expect(gone[0]).not.toHaveProperty('next');
  });

  it('renames a step, the arrows to it and the results it is named by', () => {
    const flow = renameStep(digest(), 'pick', 'choose');
    expect(flow[1]!.id).toBe('choose');
    expect(flow[0]!.next).toBe('choose');
    expect(flow[3]!.input).toEqual({ channel: '@me', text: '{choose}' });
    const found = renameStep(digest(), 'find', 'search');
    expect(found[1]!.task).toBe('Which of these need my review today?\n\n{search}');
    // A bad or taken name changes nothing.
    expect(renameStep(digest(), 'pick', 'Not ok')).toEqual(digest());
    expect(renameStep(digest(), 'pick', 'ok')).toEqual(digest());
  });

  it('makes new steps with free ids and what each kind needs', () => {
    const flow = digest();
    expect(newStep('ask', flow, [10.4, 20.6])).toEqual({ id: 'ask', kind: 'ask', question: '', options: ['yes', 'no'], next: {}, at: [10, 21] });
    expect(newStep('tool', flow, [0, 0]).id).toBe('use');
    expect(newStep('branch', flow, [0, 0]).next).toEqual({ else: null });
    expect(freeId([{ id: 'ask', kind: 'ask' }, { id: 'ask2', kind: 'ask' }], 'ask')).toBe('ask3');
    expect(freeId([], '9 lives')).toBe('s_9_lives');
  });

  it('moves and changes a step in place', () => {
    expect(moveStep(digest(), 'ok', 12.6, -3.2)[2]!.at).toEqual([13, -3]);
    expect(updateStep(digest(), 'pick', { title: 'Choose' })[1]).toMatchObject({ id: 'pick', title: 'Choose' });
  });

  it('says a tool key in words when nothing better is known', () => {
    expect(humanize('slack-send-message')).toBe('Slack send message');
    expect(humanize('')).toBe('');
  });
});
