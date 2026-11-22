import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { botsFake, inbox, weekdays } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';
import { browserZone, clock, scheduleOf, sentence, summary, zones } from './schedule';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

describe('a bot’s schedule, in plain words', () => {
  it('says each schedule in one line, in the person’s time', () => {
    const s = weekdays();
    expect(summary({ ...s, every: 'off' })).toBe('Off');
    expect(summary({ ...s, every: 'hour' })).toBe('Every hour');
    expect(summary({ ...s, every: 'day', at: '07:05' })).toBe('Every day at 7:05');
    expect(summary(s)).toBe('Weekdays at 9:00');
    expect(summary({ ...s, every: 'week', weekday: 4, at: '17:30' })).toBe('Every Friday at 17:30');
    expect(summary({ ...s, every: 'month', day: 15 })).toBe('Every month on day 15 at 9:00');
    expect(sentence(s, 'Mon 9:00')).toBe('Runs on weekdays at 9:00 (America/Chicago time). Next run Mon 9:00.');
    expect(sentence({ ...s, every: 'hour' })).toBe('Runs every hour, on the hour.');
    expect(sentence({ ...s, every: 'month', day: 31, timezone: 'America/New_York' })).toBe(
      'Runs every month on day 31 at 9:00 (America/New York time). In shorter months, on their last day.',
    );
    expect(sentence({ ...s, every: 'off' })).toBe('It runs only when you run it.');
    expect(clock('10:00')).toBe('10:00');
  });

  it('starts off in the browser’s time zone, and keeps a saved one', () => {
    expect(scheduleOf(undefined)).toEqual({ every: 'off', at: '09:00', weekday: 0, day: 1, timezone: browserZone(), input: '' });
    expect(scheduleOf({ ...weekdays(), every: 'off', timezone: 'UTC' }).timezone).toBe(browserZone());
    expect(scheduleOf(weekdays()).timezone).toBe('America/Chicago');
    const listed = zones('Mars/Olympus');
    expect(listed[0]).toBe('UTC');
    expect(listed).toContain('Mars/Olympus');
    expect(listed).toContain('Europe/London');
  });

  it('is chosen from dropdowns and a time picker, said back, saved, and its next run shown', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper');
    const runs = await screen.findByRole('combobox', { name: 'Runs' });
    expect(runs).toHaveValue('off');
    expect(screen.getByText('It runs only when you run it.')).toBeInTheDocument();
    expect(screen.queryByLabelText('At')).not.toBeInTheDocument();
    await user.selectOptions(runs, 'weekdays');
    expect(screen.getByRole('combobox', { name: 'Time zone' })).toHaveValue(browserZone());
    await user.selectOptions(screen.getByRole('combobox', { name: 'Time zone' }), 'America/Chicago');
    const time = screen.getByLabelText('At');
    expect(time).toHaveAttribute('type', 'time');
    fireEvent.change(time, { target: { value: '' } }); // a cleared picker keeps its time
    fireEvent.change(time, { target: { value: '07:30' } });
    await user.type(screen.getByLabelText('What each run is given'), 'is:unread');
    expect(screen.getByText('Runs on weekdays at 7:30 (America/Chicago time).')).toBeInTheDocument();

    await user.selectOptions(runs, 'week');
    await user.selectOptions(screen.getByRole('combobox', { name: 'On' }), '4');
    expect(screen.getByText('Runs every Friday at 7:30 (America/Chicago time).')).toBeInTheDocument();
    await user.selectOptions(runs, 'month');
    await user.selectOptions(screen.getByRole('combobox', { name: 'On day' }), '31');
    expect(screen.getByText(/In shorter months, on their last day\./)).toBeInTheDocument();
    await user.selectOptions(runs, 'weekdays');

    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Inbox helper is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toMatchObject({
      schedule: { every: 'weekdays', at: '07:30', weekday: 4, day: 31, timezone: 'America/Chicago', input: 'is:unread' },
      runs_on: null,
    });
    expect(await screen.findByText('Runs on weekdays at 7:30 (America/Chicago time). Next run Mon 9:00.')).toBeInTheDocument();
  });
});

describe('where a bot runs', () => {
  it('is chosen beside the model: Glyphh cloud by default, an offline machine greyed', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper');
    const where = await screen.findByRole('combobox', { name: 'Runs on' });
    expect(where).toHaveValue('');
    await waitFor(() => expect(within(where).getAllByRole('option')).toHaveLength(3));
    const [cloud, studio, acme] = within(where).getAllByRole('option') as HTMLOptionElement[];
    expect([cloud!.textContent, studio!.textContent, acme!.textContent]).toEqual(['Glyphh cloud', 'Studio Mac', 'Acme (offline)']);
    expect(acme).toBeDisabled();
    expect(studio).toBeEnabled();
    await user.selectOptions(where, 'rr-studio');
    expect(screen.getByText(/It runs on that machine, on the Claude key set there/)).toBeInTheDocument();
    expect(screen.queryByText(/coming/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(fake.state.bodies[0]).toMatchObject({ runs_on: 'rr-studio' }));
  });

  it('runs a bot on its machine and says where each run ran', async () => {
    const fake = on({ bots: [inbox({ runs_on: 'rr-studio' })] });
    const { user } = renderApp('/bots/inbox-helper?tab=runs');
    expect(await screen.findByText('It runs on Studio Mac, on the Claude key set there.')).toBeInTheDocument();
    await user.type(screen.getByLabelText('What to do'), 'Clear the inbox.');
    await user.click(screen.getByRole('button', { name: 'Run' }));
    const run = await screen.findByRole('region', { name: 'Run' });
    expect(await within(run).findByText('Running there')).toBeInTheDocument();
    expect(within(run).getByText(/· on Studio Mac/)).toBeInTheDocument();
    expect(within(run).getByText(/the Claude key on Studio Mac/)).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Runs' })).getByText(/· on Studio Mac/)).toBeInTheDocument();
    expect(await within(run).findByRole('region', { name: 'Question' }, { timeout: 4000 })).toBeInTheDocument(); // its result came back
    expect(fake.state.seen).toContain('run inbox-helper');
  });

  it('says so when the bot’s machine is offline, and the server’s refusal', async () => {
    on({ bots: [inbox({ runs_on: 'rr-acme' })] });
    const { user } = renderApp('/bots/inbox-helper?tab=runs');
    expect(await screen.findByText(/It runs on Acme, which is offline/)).toBeInTheDocument();
    await user.type(screen.getByLabelText('What to do'), 'Clear the inbox.');
    await user.click(screen.getByRole('button', { name: 'Run' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Acme is not linked to Glyphh right now');
  });

  it('shows on the Bots list with the next run', async () => {
    on({ bots: [inbox({ runs_on: 'rr-acme', schedule: weekdays(), next_run: 'Mon 9:00' }), inbox({ id: 'b-2', slug: 'quiet', name: 'Quiet' })] });
    renderApp('/bots');
    const card = (await screen.findByRole('link', { name: 'Inbox helper' })) as HTMLElement;
    expect(within(card).getByText('Next run Mon 9:00')).toBeInTheDocument();
    expect(await within(card).findByText('On Acme')).toBeInTheDocument();
    const quiet = screen.getByRole('link', { name: 'Quiet' });
    expect(within(quiet).queryByText(/Next run/)).not.toBeInTheDocument();
    expect(within(quiet).queryByText(/^On /)).not.toBeInTheDocument();
  });
});
