import { useState, type ReactNode } from 'react';
import type { BotRun, BotSpec } from '@/api/bots';
import { unescaped } from './Markdown';
import { BOOKKEEPING, flatFields, gateAnswer, gateCounts, isObj, itemLabel, itemLink, toolAnswer } from './readable';

/** The loop's steps by id, and which of them are Claude's (an `agent` step). */
const stepsOf = (spec: BotSpec) => new Map((spec.loop ?? []).filter((s) => typeof s.id === 'string').map((s) => [s.id as string, s]));

/**
 * Whether no Claude step ran in the run: it spent no tokens and none of its loop's agent steps left an answer. A run
 * a gate ended before its agent (no items: `empty:` ends it) costs nothing, rightly; the turn says so instead of $0.00.
 */
export function noClaudeStep(run: BotRun, spec: BotSpec): boolean {
  if (run.input_tokens + run.output_tokens > 0) return false;
  return ![...stepsOf(spec)].some(([id, s]) => typeof s.agent === 'string' && id in (run.data ?? {}));
}

/** A list of items, each by its title (a link when it has one), the first 20 and how many more. */
function Items({ items }: { items: unknown[] }) {
  if (items.length === 0) return <p className="rnone">No items.</p>;
  return (
    <ol className="rlist">
      {items.slice(0, 20).map((item, i) => {
        const link = itemLink(item);
        const text = itemLabel(item);
        return <li key={i}>{link ? <a href={link} target="_blank" rel="noreferrer">{text}</a> : text}</li>;
      })}
      {items.length > 20 && <li className="rnone">and {items.length - 20} more</li>}
    </ol>
  );
}

/** One step's answer, readable: a tool's summary and its list or fields, a gate's counts, Claude's words, or fields. */
function Answer({ value, markdown }: { value: unknown; markdown: (text: string) => ReactNode }) {
  const tool = toolAnswer(value);
  if (tool)
    return (
      <>
        {tool.summary && <p className="rsum">{tool.summary}</p>}
        <Answer value={tool.ret} markdown={markdown} />
      </>
    );
  if (gateAnswer(value)) return <p className="rsum">{gateCounts(value) || `${(value.decisions as unknown[]).length} decided`}</p>;
  if (typeof value === 'string') return value.trim() ? <>{markdown(unescaped(value))}</> : <p className="rnone">Nothing.</p>;
  if (Array.isArray(value)) return <Items items={value} />;
  if (isObj(value)) {
    const fields = flatFields(value);
    if (fields.length === 0) return <p className="rnone">Nothing to show.</p>;
    return (
      <dl className="rfields">
        {fields.map(([k, v]) => (
          <div key={k}>
            <dt>{k.replace(/[._]+/g, ' ')}</dt>
            <dd>{v.length > 300 ? `${v.slice(0, 299)}…` : v}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return <p className="rsum">{value === null || value === undefined ? 'Nothing.' : String(value)}</p>;
}

/**
 * What a run's steps found, readable, folded under a line like the steps': each step by its name with its answer (a
 * tool's list of items by their titles, Claude's words as markdown with no literal \n, a gate's counts), and the
 * raw JSON behind its own toggle. `markdown` renders words the way the chat does.
 */
export function RunData({ run, spec, markdown }: { run: BotRun; spec: BotSpec; markdown: (text: string) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const [raw, setRaw] = useState(false);
  const steps = stepsOf(spec);
  const shown = Object.entries(run.data ?? {}).filter(([k]) => !BOOKKEEPING.has(k));
  if (shown.length === 0) return null;
  return (
    <div className={`tgroup rdata ${open ? 'open' : ''}`}>
      <button type="button" className="tsum" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span>What its steps found</span>
      </button>
      {open && (
        <div className="rsteps" aria-label="What its steps found">
          {shown.map(([id, value]) => {
            const step = steps.get(id);
            const kind = step ? (typeof step.agent === 'string' ? 'Claude' : typeof step.run === 'string' ? step.run : typeof step.gate === 'string' ? `gate ${step.gate}` : '') : '';
            return (
              <section key={id} className="rstep" aria-label={`Step ${id}`}>
                <div className="rhead">
                  <b>{id}</b>
                  {kind && <span>{kind}</span>}
                </div>
                <Answer value={value} markdown={markdown} />
              </section>
            );
          })}
          <button type="button" className="tsum" aria-pressed={raw} onClick={() => setRaw(!raw)}>
            <span>{raw ? 'Hide raw' : 'Raw'}</span>
          </button>
          {raw && <pre className="rraw">{JSON.stringify(run.data, null, 2)}</pre>}
        </div>
      )}
    </div>
  );
}
