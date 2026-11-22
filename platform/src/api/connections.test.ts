import type { ConnectionTool } from './bots';
import { permissionChanges, toolKind } from './connections';

const tool = (key: string, more: Partial<ConnectionTool> = {}): ConnectionTool => ({ key, name: key, description: null, permission: 'ask', ...more });

describe('toolKind', () => {
  it('takes the tool’s MCP hints when it has them', () => {
    expect(toolKind(tool('gmail-send-email', { annotations: { readOnlyHint: true } }))).toBe('read');
    expect(toolKind(tool('gmail-list-labels', { annotations: { readOnlyHint: false } }))).toBe('write');
    expect(toolKind(tool('gmail-list-labels', { annotations: { destructiveHint: true } }))).toBe('write');
  });

  it('falls back on the verb in its key or name', () => {
    expect(toolKind(tool('gmail-find-email'))).toBe('read');
    expect(toolKind(tool('x', { name: 'List channels' }))).toBe('read');
    expect(toolKind(tool('gmail-send-email', { annotations: null }))).toBe('write');
    expect(toolKind(tool('slack-delete-message', { annotations: {} }))).toBe('write');
  });
});

describe('permissionChanges', () => {
  it('names only the tools whose permission changes', () => {
    const tools = [tool('a', { permission: 'allow' }), tool('b'), tool('c', { permission: 'deny' })];
    expect(permissionChanges(tools, ['a', 'b', 'c', 'gone'], (t) => (t.permission === 'deny' ? null : 'ask'))).toEqual({ a: 'ask' });
  });
});
