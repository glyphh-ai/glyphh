import { render, screen } from '@testing-library/react';
import { ProgressBar } from './ProgressBar';

const fill = () => screen.getByRole('progressbar').firstElementChild as HTMLElement;

describe('ProgressBar', () => {
  it('fills to the share used', () => {
    render(<ProgressBar value={12} max={50} label="Hours" />);
    expect(fill().style.width).toBe('24%');
  });

  it('never overfills', () => {
    render(<ProgressBar value={60} max={50} label="Hours" />);
    expect(fill().style.width).toBe('100%');
  });

  it('stays empty when nothing is allowed', () => {
    render(<ProgressBar value={3} max={0} label="Hours" />);
    expect(screen.getByRole('progressbar', { name: 'Hours' })).toHaveAttribute('aria-valuemax', '0');
    expect(fill().style.width).toBe('0%');
  });
});
