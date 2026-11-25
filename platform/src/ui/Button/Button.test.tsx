import { render, screen } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('draws its icon to fit its size', () => {
    render(
      <>
        <Button icon="plus">Large</Button>
        <Button icon="plus" size="sm">
          Small
        </Button>
      </>,
    );
    expect(screen.getByRole('button', { name: 'Large' }).querySelector('svg')).toHaveAttribute('width', '16');
    expect(screen.getByRole('button', { name: 'Small' }).querySelector('svg')).toHaveAttribute('width', '14');
  });

  it('is busy and cannot be pressed while loading', () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('aria-busy', 'true');
  });
});
