import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { digestFlow, program, programsFake } from '@/test/programs';
import { server } from '@/test/server';
import { ApiError } from './client';
import {
  joinEvents,
  questionOf,
  refusedProblems,
  useAddBotTool,
  useAnswerProgramRun,
  useCancelProgramRun,
  useCreateProgram,
  useDeleteProgram,
  useProgram,
  useProgramEvents,
  useProgramRun,
  useProgramRuns,
  usePrograms,
  useRunProgram,
  useToolSearch,
  useUpdateProgram,
  type ProgramEvent,
} from './programs';

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> };
}

const ev = (n: number): ProgramEvent => ({ n, at: '', kind: 'step', step: null, title: null, bot: null, ok: true, detail: null, by: null });

describe('the programs API', () => {
  it('lists, searches and reads the org’s programs', async () => {
    const fake = programsFake({ programs: [program(), program({ slug: 'tidy', name: 'Tidy files', summary: 'Files things.' })] });
    server.use(...fake.handlers);
    const { wrapper: w } = wrapper();
    const all = renderHook(() => usePrograms(), { wrapper: w });
    await waitFor(() => expect(all.result.current.data?.map((p) => p.slug)).toEqual(['pr-digest', 'tidy']));
    const found = renderHook(() => usePrograms('tidy'), { wrapper: w });
    await waitFor(() => expect(found.result.current.data?.map((p) => p.slug)).toEqual(['tidy']));
    const one = renderHook(() => useProgram('pr-digest'), { wrapper: w });
    await waitFor(() => expect(one.result.current.data?.flow).toHaveLength(4));
    expect(renderHook(() => useProgram(null), { wrapper: w }).result.current.fetchStatus).toBe('idle');
  });

  it('makes, changes (steps or file) and deletes a program, and keeps the server’s answer', async () => {
    const fake = programsFake();
    server.use(...fake.handlers);
    const { client, wrapper: w } = wrapper();
    const create = renderHook(() => useCreateProgram(), { wrapper: w });
    const made = await act(() => create.result.current.mutateAsync({ name: 'Morning check', summary: 'Checks.', bot: 'inbox-helper', flow: [] }));
    expect(made.slug).toBe('morning-check');
    expect(fake.state.bodies.at(-1)).toEqual({ method: 'POST', path: '/programs', body: { name: 'Morning check', summary: 'Checks.', bot: 'inbox-helper', flow: [] } });

    const update = renderHook(() => useUpdateProgram('pr-digest'), { wrapper: w });
    const flow = digestFlow().slice(0, 2);
    const saved = await act(() => update.result.current.mutateAsync({ flow }));
    expect(saved.flow).toEqual(flow);
    expect(saved.source).toContain('FLOW = [{"id":"find"');
    expect(client.getQueryData(['programs', 'pr-digest'])).toEqual(saved);
    const fromFile = await act(() => update.result.current.mutateAsync({ source: saved.source.replace('"pick"', '"choose"').replace('"id":"pick"', '"id":"choose"') }));
    expect(fromFile.flow[0]!.next).toBe('choose');

    const refused = await act(() => update.result.current.mutateAsync({ source: 'nothing here' }).catch((e: unknown) => e));
    expect(refusedProblems(refused)).toEqual(['FLOW is not a list of steps.']);

    const remove = renderHook(() => useDeleteProgram(), { wrapper: w });
    await act(() => remove.result.current.mutateAsync('pr-digest'));
    expect(fake.state.programs.map((p) => p.slug)).toEqual(['morning-check']);
  });

  it('runs a program and follows it: the run, its runs, its events read after the last one held', async () => {
    const fake = programsFake();
    server.use(...fake.handlers);
    const { wrapper: w } = wrapper();
    const start = renderHook(() => useRunProgram('pr-digest'), { wrapper: w });
    const r = await act(() => start.result.current.mutateAsync('today'));
    expect(r.status).toBe('queued');
    expect(fake.state.bodies.at(-1)?.body).toEqual({ input: 'today' });

    const runs = renderHook(() => useProgramRuns('pr-digest'), { wrapper: w });
    await waitFor(() => expect(runs.result.current.data?.[0]?.id).toBe(r.id));

    const run = renderHook(() => useProgramRun(r.id, 10), { wrapper: w });
    await waitFor(() => expect(run.result.current.data?.status).toBe('needs_input'));
    expect(questionOf(run.result.current.data)).toEqual({ question: 'Post the digest?', options: ['yes', 'no'], step: 'ok' });

    const events = renderHook(() => useProgramEvents(r.id, true, 10), { wrapper: w });
    await waitFor(() => expect(events.result.current.data?.map((e) => e.kind)).toEqual(['started', 'step', 'step', 'asked']));
    expect(fake.state.afters[0]).toBe(0);
    await waitFor(() => expect(fake.state.afters.at(-1)).toBe(4));

    const answer = renderHook(() => useAnswerProgramRun(), { wrapper: w });
    await act(() => answer.result.current.mutateAsync({ id: r.id, answer: 'yes' }));
    await waitFor(() => expect(run.result.current.data?.status).toBe('done'));
    await waitFor(() => expect(events.result.current.data?.map((e) => e.kind)).toEqual(['started', 'step', 'step', 'asked', 'answered', 'step', 'done']));
  });

  it('cancels a run', async () => {
    const fake = programsFake();
    server.use(...fake.handlers);
    const { wrapper: w } = wrapper();
    const start = renderHook(() => useRunProgram('pr-digest'), { wrapper: w });
    const r = await act(() => start.result.current.mutateAsync(''));
    const cancel = renderHook(() => useCancelProgramRun(), { wrapper: w });
    const stopped = await act(() => cancel.result.current.mutateAsync(r.id));
    expect(stopped.status).toBe('cancelled');
    expect(fake.state.events[r.id]?.at(-1)?.kind).toBe('cancelled');
  });

  it('finds tools for a bot and gives one to it', async () => {
    const fake = programsFake();
    server.use(...fake.handlers);
    const { wrapper: w } = wrapper();
    const found = renderHook(() => useToolSearch('email', 'inbox-helper'), { wrapper: w });
    await waitFor(() => expect(found.result.current.data?.map((t) => t.title)).toEqual(['Find email']));
    const add = renderHook(() => useAddBotTool(), { wrapper: w });
    await act(() => add.result.current.mutateAsync({ bot: 'inbox-helper', connection_id: 'c-gmail', tool: 'gmail-find-email' }));
    expect(fake.state.added).toEqual([{ bot: 'inbox-helper', connection_id: 'c-gmail', tool: 'gmail-find-email' }]);
  });

  it('joins events by their number, and reads a question either way it comes', () => {
    expect(joinEvents([ev(1), ev(2)], [ev(2), ev(3)]).map((e) => e.n)).toEqual([1, 2, 3]);
    expect(questionOf({ question: 'Go?' })).toEqual({ question: 'Go?' });
    expect(questionOf({ question: null })).toBeNull();
    expect(refusedProblems(new Error('x'))).toEqual([]);
    expect(refusedProblems(new ApiError(422, { code: 'E_INVALID', message: 'No.', trace_id: 't', problems: ['a'] } as never))).toEqual(['a']);
  });
});
