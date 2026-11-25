import { screen, waitFor, within } from '@testing-library/react';
import { keys } from '@/api/queries';
import { adaFake } from '@/test/ada';
import { renderApp, stubLocation } from '@/test/render';
import { server, sessionHandler } from '@/test/server';

/**
 * A person new to Glyphh, from signing in to a first decision, as the platform walks them through it with Ada Cloud
 * on: log in, make a model from an example, load their history from a CSV, and ask.
 */
describe('from sign-in to a first decision', () => {
  it('logs in, makes a model, imports a CSV and decides a case', async () => {
    const fake = adaFake();
    server.use(sessionHandler(false), ...fake.handlers);
    const location = stubLocation();
    try {
      // Signed out: Home sends the person to log in, and back.
      const { user, router, client } = renderApp('/');
      await waitFor(() => expect(location.assign).toHaveBeenCalledWith('/login?returnTo=%2F'));
      await router.navigate('/login?returnTo=%2F');
      expect(await screen.findByRole('link', { name: 'Log in with GitHub' })).toHaveAttribute('href', '/auth/login?returnTo=%2F');

      // The provider and the server's OAuth round trip happen outside the page; the session comes back signed in.
      server.use(sessionHandler(true));
      await client.invalidateQueries({ queryKey: ['session'] });
      await waitFor(() => expect(location.replace).toHaveBeenCalledWith('/'));
      await client.invalidateQueries({ queryKey: keys.me });
      await router.navigate('/');

      // Home: the greeting, and the connector to add in Claude.
      expect(await screen.findByRole('heading', { name: /^Good (morning|afternoon|evening)/, level: 1 })).toBeInTheDocument();
      expect(await screen.findByRole('button', { name: 'Copy connector URL' })).toBeInTheDocument();
      await user.click(screen.getAllByRole('button', { name: 'New model' })[0]!);

      // A model from the support tickets example.
      await user.selectOptions(await screen.findByRole('combobox', { name: 'Start from' }), 'tickets');
      await user.click(screen.getByRole('button', { name: 'Make model' }));
      expect(await screen.findByRole('heading', { name: 'tickets', level: 1 })).toBeInTheDocument();

      // History in: a CSV whose header names the roles and the outcome.
      await user.click(await screen.findByRole('tab', { name: 'Import' }));
      const csv = 'subject,product,plan,outcome\nCannot pay,web,pro,billing\nLocked out,app,team,auth\nCharged twice,web,pro,billing\n';
      await user.upload(screen.getByLabelText('File'), new File([csv], 'tickets.csv', { type: 'text/csv' }));
      await user.click(await screen.findByRole('button', { name: 'Import' }));
      expect(await screen.findByText(/3 rows: 2 recorded/, {}, { timeout: 4000 })).toBeInTheDocument();

      // The first decision.
      await user.click(screen.getByRole('tab', { name: 'Try it' }));
      await user.type(await screen.findByRole('textbox', { name: 'subject' }), 'I was charged twice');
      await user.click(screen.getByRole('button', { name: 'Decide' }));
      const answer = await screen.findByRole('region', { name: 'Answer' });
      expect(within(answer).getAllByText('billing')[0]).toHaveClass('big');
      expect(within(answer).getByText('Confidence 82%')).toBeInTheDocument();
      expect(fake.state.seen.map((s) => `${s.method} ${s.path}`)).toEqual(
        expect.arrayContaining(['POST /models', 'POST /models/tickets/imports', 'PUT /uploads/job-2.signed', 'GET /jobs/job-2', 'POST /decide']),
      );
    } finally {
      location.restore();
    }
  });
});
