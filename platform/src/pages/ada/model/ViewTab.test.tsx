import { fireEvent, screen } from '@testing-library/react';
import { adaFake, modelMap, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

function on(map = modelMap) {
  const fake = adaFake({ models: [tickets()], map });
  server.use(...fake.handlers);
  return fake;
}

describe('a model’s 3D view', () => {
  it('shows the sample with its outcomes’ colours, and says when the browser cannot draw it', async () => {
    on();
    renderApp('/models/tickets?tab=view');
    expect(await screen.findByText(/A sample of 4 of 1,240 precedents/)).toBeInTheDocument();
    expect(await screen.findByText('This browser cannot draw the 3D view: WebGL is off or not supported.')).toBeInTheDocument();
    expect(screen.getByText(/^billing/)).toHaveTextContent('billing 2');
    expect(screen.getByText(/^Ungraded/)).toHaveTextContent('Ungraded 1');
    expect(screen.getByRole('checkbox', { name: 'Same outcome' })).toBeChecked();
    expect(screen.getByText('0 · Whole case')).toHaveClass('on');
  });

  it('changes layer, explodes, freezes and hides labels from the keyboard', async () => {
    const fake = on();
    renderApp('/models/tickets?tab=view');
    const view = await screen.findByLabelText(/^3D view: 0 to 9 change the layer/);
    fireEvent.keyDown(view, { key: 'e' });
    fireEvent.keyDown(view, { key: 'f' });
    expect(screen.getByText(/E explode on · F freeze on/)).toBeInTheDocument();
    fireEvent.keyDown(view, { key: 'l' });
    expect(screen.getByRole('checkbox', { name: 'Labels' })).not.toBeChecked();
    fireEvent.keyDown(view, { key: 'x' });
    fireEvent.keyDown(view, { key: '1' });
    expect(await screen.findByText('1 · ticket')).toHaveClass('on');
    expect(fake.state.seen.some((s) => s.path === '/models/tickets/map')).toBe(true);
    fireEvent.keyDown(screen.getByLabelText(/^3D view: 0 to 9/), { key: '0' });
    expect(await screen.findByText('0 · Whole case')).toHaveClass('on');
  });

  it('finds a precedent by the start of its id and shows its case', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=view');
    await user.type(await screen.findByRole('textbox', { name: 'Find a precedent' }), 'a9b{Enter}');
    expect(await screen.findByText('a9b8c7')).toBeInTheDocument();
    expect(screen.getByText('ticket.about.subject')).toBeInTheDocument();
    expect(screen.getByText('refund twice')).toBeInTheDocument();
    expect(screen.getByText(/Recorded 19 Oct 2026 by/)).toBeInTheDocument();
    fireEvent.keyDown(screen.getByLabelText(/^3D view: 0 to 9/), { key: 'Escape' });
    expect(screen.queryByText('ticket.about.subject')).not.toBeInTheDocument();
  });

  it('says there is nothing to show before the model holds precedents', async () => {
    on(() => ({ ...modelMap(null), total: 0, points: [], edges: [] }));
    renderApp('/models/tickets?tab=view');
    expect(await screen.findByText('Nothing to show yet')).toBeInTheDocument();
  });

  it('shows the server’s refusal', async () => {
    on();
    server.use(http.get('*/api/ada/v1/models/tickets/map', () => apiError(422, 'E_SPEC', 'this model is above the reader’s clearance')));
    renderApp('/models/tickets?tab=view');
    expect(await screen.findByText('this model is above the reader’s clearance')).toBeInTheDocument();
  });
});
