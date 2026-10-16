import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { Dialog } from './Dialog';

function Harness({ description }: { description?: string }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <p>{open ? 'Open' : 'Closed'}</p>
      <Dialog open={open} onClose={() => setOpen(false)} title="Rename" description={description} actions={<button type="button">Save</button>}>
        <p>Body</p>
      </Dialog>
    </>
  );
}

describe('Dialog', () => {
  it('opens as a modal named by its title and described by its description', () => {
    render(<Harness description="Pick a new name." />);
    const dialog = screen.getByRole('dialog', { name: 'Rename' });
    expect(dialog).toHaveAttribute('open');
    expect(dialog).toHaveAccessibleDescription('Pick a new name.');
  });

  it('has no description when given none', () => {
    render(<Harness />);
    expect(screen.getByRole('dialog', { name: 'Rename' })).not.toHaveAttribute('aria-describedby');
  });

  it('closes on a click on the backdrop, but not on a click inside', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByText('Body'));
    expect(screen.getByText('Open')).toBeInTheDocument();
    await user.click(screen.getByRole('dialog'));
    expect(screen.getByText('Closed')).toBeInTheDocument();
    expect(screen.queryByText('Body')).not.toBeInTheDocument();
  });

  it('closes on Escape, through its own state rather than the browser’s', () => {
    render(<Harness />);
    const cancel = new Event('cancel', { cancelable: true });
    fireEvent(screen.getByRole('dialog'), cancel);
    expect(cancel.defaultPrevented).toBe(true);
    expect(screen.getByText('Closed')).toBeInTheDocument();
  });
});
