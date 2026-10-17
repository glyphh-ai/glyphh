import { render, screen } from '@testing-library/react';
import { Select } from './Select';

const options = [
  { value: 'a', label: 'A' },
  { value: 'b', label: 'B' },
];

describe('Select', () => {
  it('labels the select and describes it with its hint', () => {
    render(<Select label="Expires after" hint="Every key expires." options={options} defaultValue="b" />);
    const select = screen.getByLabelText('Expires after');
    expect(select).toHaveValue('b');
    expect(select).toHaveAccessibleDescription('Every key expires.');
  });

  it('takes a given id, and has no description without a hint', () => {
    render(<Select id="plan" label="Plan" options={options} />);
    const select = screen.getByLabelText('Plan');
    expect(select).toHaveAttribute('id', 'plan');
    expect(select).not.toHaveAttribute('aria-describedby');
  });
});
