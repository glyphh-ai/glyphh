import { useState } from 'react';
import type { BotRun, RunStep } from '@/api/bots';
import { plural } from '@/lib/format';
import { Icon, ICON } from '../icons';

/** A step in plain words: the server's title for it; one that has none (it never should) is not listed. */
const worded = (steps: RunStep[] | undefined): RunStep[] => (steps ?? []).filter((s) => typeof s.title === 'string' && s.title.trim() !== '');

/**
 * The one line that folds a turn's workings away, as the Glyphh Bot app's: "Ran 4 steps". Open, it lists what the bot
 * used during the turn, one line each in the server's plain words ("Searched issues and pull requests"), with the
 * app's name where there is one and a quiet mark on a step that failed. Never a tool's own name or its data. While
 * the run goes, the line shows what it is doing now.
 */
export function Steps({ run, live }: { run: BotRun; live?: boolean }) {
  const [open, setOpen] = useState(false);
  const steps = worded(run.steps);
  if (steps.length === 0) return null;
  const now = steps.at(-1)!;
  return (
    <div className={`tgroup tsteps ${open ? 'open' : ''}`}>
      <button type="button" className="tsum" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon d={open ? ICON.collapse : ICON.expand} size={12} />
        {live ? <span className="trun">{now.title}</span> : <span>Ran {plural(steps.length, 'step')}</span>}
      </button>
      {open && (
        <ol className="tools tfold" aria-label="Steps">
          {steps.map((step, i) => {
            const going = live && i === steps.length - 1;
            const failed = !step.ok && !going;
            return (
              <li key={i} className={`tool ${going ? 'run' : failed ? 'err' : 'ok'}`}>
                <span className="ti" aria-hidden>
                  {failed ? '×' : '•'}
                </span>
                <span className="td">{step.title}</span>
                {(step.app || failed) && (
                  <span className="tstep-side">
                    {step.app && <span className="tstep-app">{step.app}</span>}
                    {failed && <span className="tstep-failed">did not work</span>}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
