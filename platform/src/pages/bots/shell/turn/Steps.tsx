import { useState } from 'react';
import type { Bot, BotRun } from '@/api/bots';
import { BOOKKEEPING, flatFields, gateAnswer, gateCounts, isObj, itemLabel, itemLink, toolAnswer } from '@/bots/decisions/readable';
import { fieldName, topic } from '@/bots/decisions/words';
import { plural } from '@/lib/format';
import { rowsOf } from '../Decisions';
import { Icon, ICON } from '../icons';
import { plainWords, prose } from './answer';

const SHOWN = 20;

/** One step's answer, readable: a tool's summary and its items by their titles, a decision's counts, words, fields. */
function Found({ value }: { value: unknown }) {
  const tool = toolAnswer(value);
  if (tool)
    return (
      <>
        {tool.summary && <p className="rsum">{tool.summary}</p>}
        <Found value={tool.ret} />
      </>
    );
  if (gateAnswer(value)) return <p className="rsum">{gateCounts(value) || `${(value.decisions as unknown[]).length} decided`}</p>;
  if (typeof value === 'string') return <p className="rsum">{prose(value) ? (value.length > 400 ? `${value.slice(0, 399)}…` : value) : 'Data: see Raw.'}</p>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <p className="rnone">No items.</p>;
    return (
      <ol className="rlist">
        {value.slice(0, SHOWN).map((item, i) => {
          const link = itemLink(item);
          return <li key={i}>{link ? <a href={link} target="_blank" rel="noopener noreferrer">{itemLabel(item)}</a> : itemLabel(item)}</li>;
        })}
        {value.length > SHOWN && <li className="rnone">and {value.length - SHOWN} more</li>}
      </ol>
    );
  }
  if (isObj(value)) {
    // An answer that is one list in an envelope ({items: [...]}, {hits: [...]}): the list.
    const lists = Object.values(value).filter(Array.isArray);
    if (lists.length === 1) return <Found value={lists[0]} />;
    const fields = flatFields(value).slice(0, 12);
    if (fields.length === 0) return <p className="rnone">Nothing to show.</p>;
    return (
      <dl className="rfields">
        {fields.map(([k, v]) => (
          <div key={k}>
            <dt>{fieldName(k)}</dt>
            <dd>{v.length > 300 ? `${v.slice(0, 299)}…` : v}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return <p className="rnone">Nothing.</p>;
}

/**
 * The one line that folds a turn's workings away, as the Glyphh Bot app's: "Ran 4 steps, asked Ada 3 times". Open, it
 * lists what the run did line by line and what each step found, readable; the steps' raw data sits one toggle
 * further in (Raw), and nowhere else in the turn. While the run goes, the line shows what it is doing now.
 */
export function Steps({ run, bot, live }: { run: BotRun; bot: Bot; live?: boolean }) {
  const [open, setOpen] = useState(false);
  const [raw, setRaw] = useState(false);
  const lines = run.log.map(plainWords);
  const found = Object.entries(run.data ?? {}).filter(([k]) => k !== 'input' && !k.startsWith('_') && !BOOKKEEPING.has(k));
  if (lines.length === 0 && found.length === 0) return null;
  // "Ran 4 steps, Ada decided 3": only what was really decided is counted (a decision over no items decided nothing).
  const decided = rowsOf(run, bot).filter((r) => !r.sum).length;
  const summary = `Ran ${plural(lines.length, 'step')}${decided ? `, Ada decided ${decided}` : ''}`;
  return (
    <div className={`tgroup tsteps ${open ? 'open' : ''}`}>
      <button type="button" className="tsum" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon d={open ? ICON.collapse : ICON.expand} size={12} />
        {live && lines.length > 0 ? <span className="trun">{lines.at(-1)}</span> : <span>{summary}</span>}
      </button>
      {open && (
        <div className="tfold">
          <div className="tools" aria-label="Steps">
            {lines.map((line, i) => (
              <div key={i} className={`tool ${live && i === lines.length - 1 ? 'run' : 'ok'}`} title={line}>
                <span className="ti">•</span>
                <span className="td">{line}</span>
              </div>
            ))}
          </div>
          {found.map(([id, value]) => (
            <section key={id} className="rstep" aria-label={`What ${topic(id)} found`}>
              <b className="tfound">{topic(id)}</b>
              <Found value={value} />
            </section>
          ))}
          {found.length > 0 && (
            <button type="button" className="tsum traw" aria-pressed={raw} onClick={() => setRaw(!raw)}>
              <span>{raw ? 'Hide raw' : 'Raw'}</span>
            </button>
          )}
          {raw && <pre className="rraw" aria-label="Raw data">{JSON.stringify(Object.fromEntries(found), null, 2)}</pre>}
        </div>
      )}
    </div>
  );
}
