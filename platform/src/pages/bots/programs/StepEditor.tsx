// The right rail of the canvas: the selected step, in plain fields. Its name and short name, the bot that does it (a
// bot step "includes that bot": its cat and name, picked among the org's bots), and what its kind needs: the action
// (found by searching the org's apps), what it is given, the task, the question and its answers, what it chooses on,
// the function; then where it goes next.
import { useState } from 'react';
import type { Bot } from '@/api/bots';
import { useAddBotTool, useToolSearch, type FoundTool, type Next, type Program, type Step } from '@/api/programs';
import { BotCat } from '../shell/bits';
import { useToolName } from './useStepBits';
import { forks, goodId } from './flow';
import { KIND, stepTitle } from './words';

type Props = {
  step: Step;
  steps: Step[];
  program: Program;
  bots: Bot[];
  onChange: (patch: Partial<Omit<Step, 'id'>>) => void;
  onRename: (to: string) => void;
  onDelete: () => void;
  onClose: () => void;
};

const END = '';

/** Where a step can go: any other step, by its name on the canvas, or the end. */
function Target({ label, value, steps, self, onChange }: { label: string; value: string | null | undefined; steps: Step[]; self: string; onChange: (to: string | null) => void }) {
  return (
    <select aria-label={label} value={value ?? END} onChange={(e) => onChange(e.target.value || null)}>
      <option value={END}>End the program</option>
      {steps
        .filter((s) => s.id !== self)
        .map((s) => (
          <option key={s.id} value={s.id}>
            {stepTitle(s)}
          </option>
        ))}
    </select>
  );
}

/** Which bot does the step: the program's own (none chosen), or one of the org's, each with its cat. */
function BotPick({ step, program, bots, onChange }: { step: Step; program: Program; bots: Bot[]; onChange: (bot: string | null) => void }) {
  const own = bots.find((b) => b.slug === program.bot);
  const label = step.kind === 'bot' ? 'The bot it asks' : 'Done as';
  return (
    <div className="pfield">
      <span className="plabel" id={`who-${step.id}`}>
        {label}
      </span>
      <div className="pickcats" role="radiogroup" aria-labelledby={`who-${step.id}`}>
        <button type="button" role="radio" aria-checked={!step.bot} className={!step.bot ? 'pickcat on' : 'pickcat'} onClick={() => onChange(null)}>
          <span className="mini">{own ? <BotCat look={own.look} mascot={own.mascot} size={30} /> : null}</span>
          {own ? `${own.name} (the program’s)` : 'The program’s bot'}
        </button>
        {bots
          .filter((b) => b.slug !== program.bot)
          .map((b) => (
            <button key={b.id} type="button" role="radio" aria-checked={step.bot === b.slug} className={step.bot === b.slug ? 'pickcat on' : 'pickcat'} onClick={() => onChange(b.slug)}>
              <span className="mini">
                <BotCat look={b.look} mascot={b.mascot} size={30} />
              </span>
              {b.name}
            </button>
          ))}
      </div>
    </div>
  );
}

/** The action a tool step takes: found among the org's connected apps; one the bot has not got yet is added to it. */
function ToolPick({ step, bot, botName, onPick }: { step: Step; bot: string | null; botName: string; onPick: (tool: FoundTool) => void }) {
  const [q, setQ] = useState('');
  const current = useToolName(step, bot);
  const found = useToolSearch(q.trim(), bot, q.trim() !== '');
  const add = useAddBotTool();
  const use = (t: FoundTool) => {
    if (t.added || !bot) return onPick(t);
    add.mutate({ bot, connection_id: t.connection_id, tool: t.key }, { onSuccess: () => onPick(t) });
  };
  return (
    <div className="pfield">
      <span className="plabel">The action</span>
      <div className={current ? 'ptool on' : 'ptool'}>
        {current ? (
          <>
            <b>{current.title}</b>
            <small>
              {current.app}
              {current.read_only ? ' · reads only' : ' · makes changes'}
            </small>
          </>
        ) : (
          <small>{step.tool ? 'An action this bot cannot find any more. Pick another.' : 'None yet. Find one below.'}</small>
        )}
      </div>
      <input aria-label="Find an action" placeholder="Find an action: send a message, search email…" value={q} onChange={(e) => setQ(e.target.value)} />
      {q.trim() !== '' && (
        <ul className="ptools" aria-label="Actions found">
          {found.isPending && <li className="dim">Looking…</li>}
          {found.data?.length === 0 && <li className="dim">Nothing found. Connect the app under Connections first.</li>}
          {(found.data ?? []).map((t) => (
            <li key={`${t.connection_id ?? ''}:${t.key}`}>
              <div className="appname">
                <b>{t.title}</b>
                <small>
                  {t.app}
                  {t.read_only ? ' · reads only' : ''}
                  {t.description ? ` · ${t.description}` : ''}
                </small>
              </div>
              <button type="button" className="btn tiny" disabled={add.isPending || (!t.added && !bot)} aria-label={`Use ${t.title} (${t.app})`} onClick={() => use(t)}>
                {t.added ? 'Use' : `Add to ${botName}`}
              </button>
            </li>
          ))}
        </ul>
      )}
      {add.error && <small className="err">{add.error.message}</small>}
    </div>
  );
}

/** What a step is given: names and values, each value able to name earlier results. */
function Given({ value, onChange }: { value: Record<string, unknown> | undefined; onChange: (input: Record<string, unknown>) => void }) {
  const [rows, setRows] = useState<{ k: string; v: string; raw: unknown }[]>(() =>
    Object.entries(value ?? {}).map(([k, v]) => ({ k, v: typeof v === 'string' ? v : JSON.stringify(v), raw: v })),
  );
  const emit = (next: typeof rows) => {
    setRows(next);
    onChange(
      Object.fromEntries(
        next
          .filter((r) => r.k.trim())
          .map((r) => {
            if (typeof r.raw !== 'string' && r.raw !== undefined && r.v === JSON.stringify(r.raw)) return [r.k.trim(), r.raw];
            return [r.k.trim(), r.v];
          }),
      ),
    );
  };
  return (
    <div className="pfield">
      <span className="plabel">What it is given</span>
      <div className="pkv" role="group" aria-label="What it is given">
        {rows.map((r, i) => (
          <div className="pkv-row" key={i}>
            <input aria-label={`Name ${i + 1}`} placeholder="name" value={r.k} onChange={(e) => emit(rows.map((x, j) => (j === i ? { ...x, k: e.target.value } : x)))} />
            <input aria-label={`Value ${i + 1}`} placeholder="value, or {an earlier step}" value={r.v} onChange={(e) => emit(rows.map((x, j) => (j === i ? { ...x, v: e.target.value, raw: undefined } : x)))} />
            <button type="button" className="icon" aria-label={`Remove ${r.k || `row ${i + 1}`}`} onClick={() => emit(rows.filter((_, j) => j !== i))}>
              ×
            </button>
          </div>
        ))}
        <button type="button" className="btn ghost tiny" onClick={() => setRows([...rows, { k: '', v: '', raw: undefined }])}>
          + Add a value
        </button>
      </div>
    </div>
  );
}

/** The answers a person can pick, as chips; a free answer when there are none. */
function Options({ options, onChange }: { options: string[]; onChange: (options: string[]) => void }) {
  const [typed, setTyped] = useState('');
  const put = () => {
    const o = typed.trim();
    if (o && !options.includes(o)) onChange([...options, o]);
    setTyped('');
  };
  return (
    <div className="pfield">
      <span className="plabel">Answers to pick from</span>
      <div className="pchips" role="list" aria-label="Answers to pick from">
        {options.length === 0 && <small className="dim">None: they answer in their own words.</small>}
        {options.map((o) => (
          <span key={o} className="pill on" role="listitem">
            {o}
            <button type="button" aria-label={`Remove the answer ${o}`} onClick={() => onChange(options.filter((x) => x !== o))}>
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="row">
        <input aria-label="Add an answer" placeholder="Add an answer" value={typed} onChange={(e) => setTyped(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && put()} />
        <button type="button" className="btn tiny" disabled={!typed.trim()} onClick={put}>
          Add
        </button>
      </div>
    </div>
  );
}

/** Where it goes next: one step, or for a question or a choice, a step for each result. */
function NextPick({ step, steps, onChange }: { step: Step; steps: Step[]; onChange: (next: Next | undefined) => void }) {
  const [key, setKey] = useState('');
  if (!forks(step.kind))
    return (
      <div className="pfield">
        <span className="plabel">Then</span>
        <Target label="Then" value={typeof step.next === 'string' ? step.next : null} steps={steps} self={step.id} onChange={(to) => onChange(to ?? undefined)} />
      </div>
    );
  const map = step.next && typeof step.next === 'object' ? step.next : {};
  const keys = step.kind === 'ask' ? [...new Set([...(step.options ?? []), ...Object.keys(map).filter((k) => k !== 'else'), 'else'])] : [...new Set([...Object.keys(map)])];
  const set = (k: string, to: string | null) => onChange({ ...map, [k]: to });
  return (
    <div className="pfield">
      <span className="plabel">Then</span>
      <div className="pways">
        {keys.map((k) => (
          <div className="pway" key={k}>
            <span className="pway-when">{k === 'else' ? 'Anything else' : step.kind === 'ask' ? `“${k}”` : `When ${k}`}</span>
            <span className="pway-arrow" aria-hidden>
              →
            </span>
            <Target label={k === 'else' ? 'Then, for anything else' : `Then, for ${k}`} value={map[k]} steps={steps} self={step.id} onChange={(to) => set(k, to)} />
            {step.kind === 'branch' && (
              <button
                type="button"
                className="icon"
                aria-label={`Remove the way for ${k}`}
                onClick={() => onChange(Object.fromEntries(Object.entries(map).filter(([x]) => x !== k)))}
              >
                ×
              </button>
            )}
          </div>
        ))}
        {step.kind === 'branch' && (
          <div className="row">
            <input aria-label="A value to choose on" placeholder="a value, like invoice" value={key} onChange={(e) => setKey(e.target.value)} />
            <button
              type="button"
              className="btn tiny"
              disabled={!key.trim() || key.trim() in map}
              onClick={() => {
                set(key.trim(), null);
                setKey('');
              }}
            >
              + Add a way
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function StepEditor({ step, steps, program, bots, onChange, onRename, onDelete, onClose }: Props) {
  const [id, setId] = useState(step.id);
  const kind = KIND[step.kind];
  const bot = step.bot || program.bot;
  const botName = bots.find((b) => b.slug === bot)?.name ?? 'its bot';
  const idProblem = id === step.id ? '' : !goodId(id) ? 'Lowercase letters, digits and _ only, starting with a letter.' : steps.some((s) => s.id === id) ? 'Another step has that name.' : '';
  const rename = () => {
    if (id !== step.id && !idProblem) onRename(id);
  };
  const others = steps.filter((s) => s.id !== step.id);
  return (
    <aside className="prail" aria-label="Step">
      <div className="prail-head">
        <span className={`sn-mark k-${step.kind}`} aria-hidden>
          {kind.mark}
        </span>
        <div className="prail-title">
          <b>{kind.label}</b>
          <small>{kind.hint}</small>
        </div>
        <button type="button" className="icon" aria-label="Close the step" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="prail-body form">
        <label>
          Its name on the canvas
          <input value={step.title ?? ''} placeholder={stepTitle({ ...step, title: '' })} onChange={(e) => onChange({ title: e.target.value || undefined })} />
        </label>
        <label>
          Short name
          <input aria-label="Short name" value={id} onChange={(e) => setId(e.target.value.toLowerCase())} onBlur={rename} onKeyDown={(e) => e.key === 'Enter' && rename()} />
          <small className={idProblem ? 'err' : undefined}>{idProblem || `Later steps use its result as {${step.id}}.`}</small>
        </label>

        <BotPick step={step} program={program} bots={bots} onChange={(b) => onChange({ bot: b ?? undefined })} />

        {step.kind === 'tool' && <ToolPick step={step} bot={bot} botName={botName} onPick={(t) => onChange({ tool: t.key, title: step.title || t.title })} />}
        {step.kind === 'bot' && (
          <label>
            The task
            <textarea rows={5} value={step.task ?? ''} placeholder="Which of these need my review today?&#10;&#10;{find}" onChange={(e) => onChange({ task: e.target.value })} />
            <small>What {botName} is told. Its answer is this step’s result.</small>
          </label>
        )}
        {step.kind === 'ask' && (
          <>
            <label>
              The question
              <textarea rows={3} value={step.question ?? ''} placeholder="Post the digest?" onChange={(e) => onChange({ question: e.target.value })} />
              <small>The run waits here for an answer, in Needs you.</small>
            </label>
            <Options
              options={step.options ?? []}
              onChange={(options) => {
                const map = step.next && typeof step.next === 'object' ? step.next : {};
                const kept = Object.fromEntries(Object.entries(map).filter(([k]) => k === 'else' || options.includes(k)));
                onChange({ options, next: kept });
              }}
            />
          </>
        )}
        {step.kind === 'branch' && (
          <label>
            Choose on
            <input value={step.on ?? ''} placeholder="{pick.kind}" onChange={(e) => onChange({ on: e.target.value })} />
            <small>An earlier result. The way for its value is taken, else the way for anything else.</small>
          </label>
        )}
        {step.kind === 'code' && (
          <label>
            The function
            {program.functions.length > 0 ? (
              <select value={step.function ?? ''} onChange={(e) => onChange({ function: e.target.value })}>
                <option value="">Pick a function</option>
                {[...new Set([...program.functions, ...(step.function ? [step.function] : [])])].map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            ) : (
              <input value={step.function ?? ''} placeholder="tidy" onChange={(e) => onChange({ function: e.target.value })} />
            )}
            <small>{program.runs_on ? 'Runs in the rrotor’s sandbox, with the folders its bot was given there.' : 'Code runs on a rrotor: choose one under Where it runs.'}</small>
          </label>
        )}
        {(step.kind === 'tool' || step.kind === 'code') && <Given value={step.input} onChange={(input) => onChange({ input })} />}

        <NextPick step={step} steps={steps} onChange={(next) => onChange({ next })} />
        <small className="dim">
          Put an earlier result in any words with its short name in braces{others[0] ? `, like {${others[0].id}}` : ''}, and what the run was given with {'{input}'}.
        </small>

        <div className="row end">
          <button type="button" className="btn ghost danger" onClick={onDelete}>
            Delete step
          </button>
        </div>
      </div>
    </aside>
  );
}
