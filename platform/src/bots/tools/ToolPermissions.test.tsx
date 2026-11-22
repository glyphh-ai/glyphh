import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ConnectionTool } from '@/api/bots';
import { ToolPermissions } from './ToolPermissions';

const tools: ConnectionTool[] = [
  { key: 'gmail-find-email', name: 'Find email', description: 'Finds emails.', permission: 'allow' },
  { key: 'gmail-send-email', name: 'Send email', description: 'Sends an email.', permission: 'ask' },
  // Its name reads as a write, its MCP hint says it only reads: the hint wins.
  { key: 'gmail-create-report', name: 'Create report', description: null, permission: 'ask', annotations: { readOnlyHint: true } },
];

describe('ToolPermissions, on its own', () => {
  it('groups by MCP hints then verbs, one line per tool, and hands the keys back from its switches and approvals', async () => {
    const user = userEvent.setup();
    const onSwitch = vi.fn();
    const onApproval = vi.fn();
    render(<ToolPermissions label="Gmail tools" tools={tools} isOn={(t) => t.key !== 'gmail-send-email'} onSwitch={onSwitch} onApproval={onApproval} />);
    const reads = screen.getByRole('region', { name: 'Read-only tools' });
    const writes = screen.getByRole('region', { name: 'Write/delete tools' });
    expect(reads).toHaveTextContent('2');
    expect(writes).toHaveTextContent('0/1');
    await user.click(within(reads).getByRole('button', { name: /Read-only tools/ }));
    expect(within(reads).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Find email', 'Create report']);
    expect(within(reads).getByText('Find email')).toHaveAttribute('title', 'Finds emails.');
    expect(screen.queryByText('Finds emails.')).not.toBeInTheDocument();

    await user.click(within(reads).getByRole('switch', { name: 'Find email' }));
    expect(onSwitch).toHaveBeenLastCalledWith(['gmail-find-email'], false);
    await user.click(within(reads).getByRole('switch', { name: 'All read-only tools' }));
    expect(onSwitch).toHaveBeenLastCalledWith(['gmail-find-email', 'gmail-create-report'], false);
    await user.click(within(writes).getByRole('switch', { name: 'All write/delete tools' }));
    expect(onSwitch).toHaveBeenLastCalledWith(['gmail-send-email'], true);
    // One allowed and one asking: the section's approval is mixed, and a click asks for all of it.
    const all = within(reads).getByRole('button', { name: 'Approval for all read-only tools' });
    expect(all).toHaveAttribute('aria-pressed', 'mixed');
    await user.click(all);
    expect(onApproval).toHaveBeenLastCalledWith(['gmail-find-email', 'gmail-create-report'], true);
    await user.click(within(reads).getByRole('button', { name: 'Approval for Find email' }));
    expect(onApproval).toHaveBeenLastCalledWith(['gmail-find-email'], true);
    // A section with nothing on has no approval to set.
    expect(within(writes).getByRole('button', { name: 'Approval for all write/delete tools' })).toBeDisabled();
  });
});
