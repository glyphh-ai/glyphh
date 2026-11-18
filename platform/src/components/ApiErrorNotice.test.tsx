import { render, screen } from '@testing-library/react';
import { ApiError } from '@/api/client';
import { ApiErrorNotice } from './ApiErrorNotice';

describe('A refusal', () => {
  it('is shown in the server’s words, with its trace id', () => {
    render(<ApiErrorNotice error={new ApiError(403, { code: 'E_FORBIDDEN', message: 'Not yours.', trace_id: 't-1' })} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Not yours.');
    expect(screen.getByText('Trace t-1')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('gets a plain line when the server was not reached', () => {
    render(<ApiErrorNotice error={new TypeError('Failed to fetch')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Glyphh could not be reached. Check your connection and try again.');
  });

  it('is nothing when there is no error', () => {
    const { container } = render(<ApiErrorNotice error={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
