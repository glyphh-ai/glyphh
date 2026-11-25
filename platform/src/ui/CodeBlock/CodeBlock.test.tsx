import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CodeBlock } from './CodeBlock';

describe('CodeBlock', () => {
  it('shows every line and copies them all at once', async () => {
    const user = userEvent.setup();
    render(<CodeBlock code={'cd deploy/compose\ndocker compose up -d'} label="commands" />);
    expect(screen.getByText(/docker compose up -d/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Copy commands' }));
    expect(await navigator.clipboard.readText()).toBe('cd deploy/compose\ndocker compose up -d');
    expect(screen.getByRole('button', { name: 'Copy commands' })).toHaveTextContent('Copied');
  });
});
