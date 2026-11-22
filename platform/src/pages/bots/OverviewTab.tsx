import { Link } from 'react-router';
import { useBotGates, useBotRuns, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, stamp } from '@/lib/format';
import { Skeleton } from '@/ui';
import { DecisionLines, GateCard, gateNames, InClaude, Watches } from './ada';
import { botPath, QuestionForm, RunChip } from './parts';
import look from './look.module.css';

const LATEST = 4;

/**
 * The bot at a glance, built around Ada: what waits on you (answered here), its latest runs and what each decided
 * (corrected in place), and beside them its gates in Ada, what it watches, and its tools in the person's Glyphh
 * connection.
 */
export function OverviewTab({ bot }: { bot: Bot }) {
  const runs = useBotRuns(bot.slug);
  const gates = useBotGates(bot.slug);
  const waiting = (runs.data ?? []).filter((r) => r.status === 'needs_input');
  const latest = (runs.data ?? []).filter((r) => r.status !== 'needs_input').slice(0, LATEST);
  const names = gateNames(bot);

  return (
    <div className={look.columns}>
      <div className={look.stack}>
        {waiting.length > 0 && (
          <section className={look.section} aria-label="Waiting on you">
            <div className={look.labelRow}>
              <h2 className={look.label}>Waiting on you · {waiting.length}</h2>
            </div>
            <div className={look.waitingList}>
              {waiting.map((r) => (
                <article key={r.id} className={look.ask} aria-label={r.question?.question ?? 'Waiting'}>
                  <div className={look.runHead}>
                    <span className={look.muted} title={stamp(r.created_at)}>
                      {r.input ? `“${r.input}” · ` : ''}
                      {ago(r.created_at)}
                    </span>
                    <RunChip status={r.status} small />
                  </div>
                  <DecisionLines run={r} bot={bot} />
                  <QuestionForm run={r} />
                </article>
              ))}
            </div>
          </section>
        )}
        <section className={look.section} aria-label="Latest decisions">
          <div className={look.labelRow}>
            <h2 className={look.label}>Latest decisions</h2>
            <Link to="?tab=runs">All decisions →</Link>
          </div>
          <ApiErrorNotice error={runs.error} />
          {runs.isPending ? (
            <div className={look.panel}>
              <div className={look.panelBody}>
                <Skeleton height={14} width="60%" />
              </div>
            </div>
          ) : latest.length === 0 ? (
            <p className={look.empty}>
              Nothing decided yet. <Link to="?tab=runs">Run it</Link> and each gate’s decision shows here, to keep or correct.
            </p>
          ) : (
            <ul className={`${look.panel} ${look.feed}`} aria-label="Latest runs">
              {latest.map((r) => (
                <li key={r.id} className={look.run}>
                  <div className={look.runHead}>
                    <Link to={`${botPath(bot.slug)}?tab=runs&run=${encodeURIComponent(r.id)}`} className={look.runTitle}>
                      <span>{r.input || 'Run'}</span>
                    </Link>
                    <span className={look.facts}>
                      <span className={look.muted} title={stamp(r.created_at)}>
                        {ago(r.created_at)}
                      </span>
                      <RunChip status={r.status} small />
                    </span>
                  </div>
                  <DecisionLines run={r} bot={bot} limit={3} />
                  {r.output && <p className={look.sub}>{r.output}</p>}
                  {r.error && <p className={look.sub}>{r.error}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <aside className={look.stack} aria-label="About this bot">
        <section className={look.section} aria-label="Ada gates">
          <div className={look.labelRow}>
            <h2 className={look.label}>Ada gates · {names.length}</h2>
            {names.length > 0 && <Link to="?tab=gates">Details →</Link>}
          </div>
          <ApiErrorNotice error={gates.error} />
          {names.length === 0 ? (
            <p className={look.empty}>No gates: it decides nothing in Ada, so it learns nothing from your answers.</p>
          ) : (
            <div className={look.gates}>
              {names.map((n) =>
                gates.data ? (
                  <GateCard key={n} bot={bot} name={n} stat={gates.data[n] ?? {}} compact />
                ) : (
                  <div key={n} className={look.gate} aria-hidden="true">
                    <Skeleton height={16} width="40%" />
                    <Skeleton height={6} width="100%" />
                  </div>
                ),
              )}
            </div>
          )}
        </section>
        <section className={look.section} aria-label="Watches">
          <div className={look.labelRow}>
            <h2 className={look.label}>What it watches</h2>
            <Link to="?tab=settings">Change →</Link>
          </div>
          <div className={look.panel}>
            <Watches bot={bot} />
          </div>
        </section>
        <section className={look.section} aria-label="In Claude">
          <div className={look.labelRow}>
            <h2 className={look.label}>In Claude</h2>
          </div>
          <div className={look.panel}>
            <InClaude bot={bot} />
          </div>
        </section>
      </aside>
    </div>
  );
}
