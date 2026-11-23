// What the Programs screens say: each kind of step, a run's state, who started it. Plain words only.
import type { FoundTool, ProgramEvent, ProgramRunStatus, Step, StepKind, Trigger } from '@/api/programs';
import { humanize } from './flow';

/** Each kind of step as the palette and a step's card name it, with its one-glyph mark and a line on what it does. */
export const KIND: Record<StepKind, { label: string; tag: string; mark: string; hint: string }> = {
  tool: { label: 'Use an app', tag: 'App', mark: '⌁', hint: 'One action in a connected app, done as the bot.' },
  bot: { label: 'Ask a bot', tag: 'Bot', mark: '◉', hint: 'A bot does a task its own way and answers.' },
  ask: { label: 'Ask a person', tag: 'Ask', mark: '?', hint: 'The run waits for your answer.' },
  branch: { label: 'Choose the way', tag: 'Choose', mark: '⑂', hint: 'Goes one way or another on an earlier result.' },
  code: { label: 'Run code', tag: 'Code', mark: '{ }', hint: 'A function of the program, on a rrotor.' },
};

/** A step's name on the canvas: its title, else made from what it does. */
export function stepTitle(step: Step, tool?: FoundTool | null): string {
  if (step.title?.trim()) return step.title.trim();
  switch (step.kind) {
    case 'tool':
      return tool?.title ?? (step.tool ? humanize(step.tool) : 'Pick an action');
    case 'bot':
      return step.task?.trim() ? firstLine(step.task) : 'Give the bot a task';
    case 'ask':
      return step.question?.trim() ? firstLine(step.question) : 'Ask a question';
    case 'branch':
      return step.on?.trim() ? `Choose on ${step.on.trim()}` : 'Choose the way';
    case 'code':
      return step.function ? humanize(step.function) : 'Pick a function';
  }
}

const firstLine = (text: string) => {
  const line = text.trim().split('\n')[0] ?? '';
  return line.length > 60 ? `${line.slice(0, 57)}…` : line;
};

export const RUN: Record<ProgramRunStatus, string> = {
  queued: 'Starting',
  running: 'Running',
  dispatched: 'Running on the rrotor',
  needs_input: 'Needs you',
  done: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled',
};
export const runWords = (status: string): string => RUN[status as ProgramRunStatus] ?? humanize(status);

/** Who or what started a run, or answered: a person (their email), the schedule, the connector in Claude. */
export function whoWords(by: string | null | undefined, trigger?: Trigger): string {
  const who = by ?? trigger ?? '';
  if (who === 'schedule') return 'the schedule';
  if (who === 'connector') return 'Claude';
  if (who === 'person' || who === '') return 'you';
  return who;
}
export const whoMark = (by: string | null | undefined): 'schedule' | 'connector' | 'person' => (by === 'schedule' ? 'schedule' : by === 'connector' ? 'connector' : 'person');

/** An event of the audit trail as a line: what happened. Who did it (the bot, the person) is drawn beside it. */
export function eventWords(e: ProgramEvent): string {
  const title = e.title ?? (e.step ? humanize(e.step) : '');
  switch (e.kind) {
    case 'started':
      return `Started by ${whoWords(e.by)}`;
    case 'step':
      return `${title}${e.ok === false ? ' did not work' : ''}${e.detail ? `: ${e.detail}` : ''}`;
    case 'asked':
      return `Asked: ${e.detail ?? title}`;
    case 'answered':
      return `${whoWords(e.by) === 'you' ? 'You' : whoWords(e.by)} answered${e.detail ? ` “${e.detail}”` : ''}`;
    case 'done':
      return 'Finished';
    case 'failed':
      return `Stopped: ${e.detail ?? 'something went wrong'}`;
    case 'cancelled':
      return `Cancelled${e.by ? ` by ${whoWords(e.by)}` : ''}`;
    default:
      return e.detail ?? humanize(String(e.kind));
  }
}

/** What the server found wrong, as a sentence. */
export function plainProblem(problem: string): string {
  const said = problem.trim();
  const sentence = said.charAt(0).toUpperCase() + said.slice(1);
  return /[.!?]$/.test(sentence) ? sentence : `${sentence}.`;
}
