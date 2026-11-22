import { machine, machineFake, PLACE, TEXT } from '@/pages/bots/shell/work/fake';
import { http, HttpResponse, server } from '@/test/server';
import { forgetTickets, NO_ANSWER, WorkError, workClient } from './work';

describe('the work panels’ reads of a rrotor', () => {
  beforeEach(forgetTickets);

  it('asks Glyphh for one ticket and then the machine itself, with no cookie', async () => {
    const fake = machineFake();
    server.use(...fake.handlers);
    const asked = vi.spyOn(globalThis, 'fetch');
    const client = workClient(PLACE);
    expect((await client.workspaces()).map((w) => w.name)).toEqual(['acme/site']);
    expect((await client.tree('acme__site', 'src')).entries.map((e) => e.path)).toEqual(['src/site.css', 'src/timer.js']);
    expect((await client.file('acme__site', 'README.md')).text).toBe(TEXT['README.md']);
    expect((await client.diff('acme__site', 'turn/2-dex')).files).toHaveLength(3);
    expect((await client.terminal('acme__site', 2)).lines.map((l) => l.n)).toEqual([2, 3]);
    expect((await client.raw('acme__site', 'attachments/sketch.png')).size).toBe(4);
    expect(fake.state.tickets).toBe(1);
    const toMachine = asked.mock.calls.filter(([url]) => String(url).startsWith(machine));
    expect(toMachine).toHaveLength(6);
    for (const [, init] of toMachine) expect(init).toMatchObject({ credentials: 'omit', headers: { authorization: `Bearer ticket-${PLACE}` } });
    // Glyphh is asked for the ticket alone: nothing the machine answered goes back to it.
    expect(asked.mock.calls.filter(([url]) => !String(url).startsWith(machine)).map(([url]) => String(url))).toEqual(['/api/v1/bots/places/rr-studio/ticket']);
    expect(fake.state.seen).toEqual(['workspaces', 'tree src', 'file README.md', 'diff turn/2-dex', 'terminal 2', 'raw attachments/sketch.png']);
    asked.mockRestore();
  });

  it('fetches a fresh ticket once when the machine says the one it has ended', async () => {
    const fake = machineFake();
    server.use(...fake.handlers);
    const client = workClient(PLACE);
    await client.workspaces();
    fake.state.stale = 1;
    expect((await client.tree('acme__site')).entries).toHaveLength(4);
    expect(fake.state.tickets).toBe(2);
    // Refused twice, it is the machine's refusal.
    fake.state.stale = 2;
    await expect(client.tree('acme__site')).rejects.toMatchObject({ status: 401, code: 'E_UNAUTHORIZED', message: 'That ticket has ended.' });
  });

  it('saves a file’s text to the machine, and says in plain words why a save was refused', async () => {
    const fake = machineFake();
    server.use(...fake.handlers);
    const client = workClient(PLACE);
    expect(await client.save('acme__site', 'README.md', '# New\n')).toEqual({ path: 'README.md', size: 6 });
    expect(fake.state.saved).toEqual([{ path: 'README.md', text: '# New\n' }]);
    fake.state.refuse = { status: 409, code: 'E_BUSY', message: 'held' };
    const busy = await client.save('acme__site', 'README.md', 'x').catch((e: unknown) => e);
    expect(busy).toBeInstanceOf(WorkError);
    expect((busy as WorkError).message).toBe('A bot is working in this repository right now. Save again when its turn ends.');
    fake.state.refuse = { status: 409, code: 'E_HEAD_ONLY', message: 'follower' };
    await expect(client.save('acme__site', 'README.md', 'x')).rejects.toThrow(/standby of its cluster/);
  });

  it('says so when the machine does not answer, or answers with no words', async () => {
    const fake = machineFake();
    server.use(...fake.handlers);
    server.use(http.get(`${machine}/v1/work`, () => HttpResponse.error()));
    await expect(workClient(PLACE).workspaces()).rejects.toMatchObject({ code: 'E_NO_ANSWER', message: NO_ANSWER });
    server.use(http.get(`${machine}/v1/work`, () => new HttpResponse('down', { status: 502 })));
    await expect(workClient(PLACE).workspaces()).rejects.toMatchObject({ status: 502, code: 'E_HTTP', message: 'That machine could not answer that.' });
    server.use(http.get(`${machine}/v1/work`, () => HttpResponse.json({})));
    expect(await workClient(PLACE).workspaces()).toEqual([]);
  });
});
