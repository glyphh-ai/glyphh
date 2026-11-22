import { useBotGates, useBotRuns, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago } from '@/lib/format';
import { EmptyState, Skeleton } from '@/ui';
import { byWords, decisionsOf, GateCard, gateNames } from './ada';
import look from './look.module.css';

const RECENT = 8;

/**
 * Each of the bot's gates in Ada, in full: what it decides between, its precedents, who decided (Ada, you, the
 * default), how often it asks you, how often its guess was right when it asked, how often it was corrected, and its
 * latest decisions from the bot's runs.
 */
export function GatesTab({ bot }: { bot: Bot }) {
  const gates = useBotGates(bot.slug);
  const runs = useBotRuns(bot.slug);
  if (gates.isPending)
    return (
      <ul className={look.gates} aria-busy="true" aria-label="Loading gates">
        {Array.from({ length: Math.max(1, bot.gate_models.length) }, (_, i) => (
          <li key={i} className={look.gate} aria-hidden="true">
            <Skeleton height={16} width="50%" />
            <Skeleton height={28} width="30%" />
            <Skeleton height={12} width="70%" />
          </li>
        ))}
      </ul>
    );
  if (gates.error) return <ApiErrorNotice error={gates.error} />;
  const names = Object.keys(gates.data).length ? Object.keys(gates.data) : gateNames(bot);
  if (names.length === 0)
    return (
      <EmptyState icon="flag" title="No gates">
        This bot’s loop has no gates, so it decides nothing in Ada and learns nothing from your answers.
      </EmptyState>
    );
  const all = (runs.data ?? []).flatMap((r) => decisionsOf(r, bot.spec).map((d) => ({ ...d, at: r.created_at, run: r.id })));
  return (
    <ul className={`${look.gates} ${look.gatesFull}`} aria-label="Gates">
      {names.map((name) => {
        const stat = gates.data[name] ?? {};
        const recent = all.filter((d) => d.gate === name).slice(0, RECENT);
        return (
          <li key={name} aria-label={name} className={look.gateRow}>
            <GateCard bot={bot} name={name} stat={stat} />
            <section aria-label={`${name}: latest decisions`}>
              <div className={look.labelRow}>
                <h3 className={look.label}>Latest decisions</h3>
              </div>
              {recent.length === 0 ? (
                <p className={look.empty}>No decisions in its recent runs.</p>
              ) : (
                <ul className={`${look.decisions} ${look.panel}`}>
                  {recent.map((r) => (
                    <li key={r.run} className={look.decision}>
                      <span className={look.by}>{ago(r.at)}</span>
                      <span className={look.outcome}>{r.outcome}</span>
                      <span className={look.by}>{r.each ? `Ada ${r.decided ?? 0} · you ${r.asked ?? 0}` : byWords(r)}</span>
                      <span />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </li>
        );
      })}
    </ul>
  );
}
