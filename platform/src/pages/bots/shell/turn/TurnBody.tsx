import type { ReactNode } from 'react';
import type { Bot, BotRun } from '@/api/bots';
import { unescaped } from '@/bots/decisions/Markdown';
import { TurnDecisions } from '@/bots/decisions/TurnDecisions';
import { DecisionRow, rowsOf } from '../Decisions';
import { Markdown } from '../Markdown';
import { filesOf, imagesOf, wordsOf } from './answer';
import { FileChips, LinkCards, Shots } from './Cards';
import { McpApp } from './McpApp';
import { Steps } from './Steps';
import './turn.css';

/** Words as the chat's markdown: headings, tables, checklists, code with Copy, real links, images inline. */
export function Rich({ text }: { text: string }) {
  return <Markdown text={unescaped(text)} />;
}

/**
 * A run's decisions from its own data, until the server has copied them: one row each, and nothing at all when it
 * decided nothing (a decision over many items with no items is not a row).
 */
function Decided({ run, bot }: { run: BotRun; bot: Bot }) {
  const rows = rowsOf(run, bot).filter((r) => !r.sum);
  if (rows.length === 0) return null;
  return (
    <div className="dtable" role="table" aria-label="Decisions">
      <div className="dhead2">
        <span>Ada decided</span>
        <span>{rows.length}</span>
      </div>
      {rows.map((r) => (
        <DecisionRow key={`${r.gate}:${r.item ?? ''}`} row={r} bot={bot} />
      ))}
    </div>
  );
}

/**
 * What a bot's turn shows, top to bottom: the one line that folds its steps (and, one toggle further, their raw data),
 * what Ada decided as rows to keep or correct, the bot's own words as markdown, what its steps brought back (images,
 * link cards for things with a page, files, MCP Apps in their frames), then what happened in a plain sentence when
 * the words do not already say it, what the bot takes when the task did not fit, and its question (`ask`), answered
 * in place. Never the run's raw data, its engine's log lines or its engine's reason.
 */
export function TurnBody({ run, bot, going, ask }: { run: BotRun; bot: Bot; going: boolean; ask?: ReactNode }) {
  const { answer, summary, hint } = wordsOf(run, bot.spec);
  const over = run.status === 'done' || run.status === 'failed';
  return (
    <>
      <Steps run={run} bot={bot} live={going} />
      <TurnDecisions slug={bot.slug} runId={run.id} over={over} fallback={<Decided run={run} bot={bot} />} />
      {answer && <Rich text={answer} />}
      {!going && (
        <>
          <Shots shots={imagesOf(run, answer)} />
          <LinkCards links={run.links ?? []} />
          <FileChips files={filesOf(run)} />
          {(run.apps ?? []).map((app) => (
            <McpApp key={`${app.step}:${app.uri}`} app={app} />
          ))}
        </>
      )}
      {summary && <p className={`tsaid ${run.status === 'failed' ? 'bad' : ''}`}>{summary}</p>}
      {hint && (
        <p className="tsaid thint" role="note">
          {hint}
        </p>
      )}
      {run.status === 'needs_input' && ask}
    </>
  );
}
