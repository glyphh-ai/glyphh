import { useEffect } from 'react';
import { useDecision, useForgetPrecedent } from '@/api/botDecisions';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { LoadingCard, useToast } from '@/ui';
import { Markdown } from './Markdown';
import { OutcomePill } from './OutcomePill';
import { RightWrong } from './RightWrong';
import { fieldName, modeWords, pct, topic, when, whoWords } from './words';
import styles from './decisions.module.css';

const LONG = 160; // a field longer than this, or with lines, reads as markdown

/** One decision read in full: its item's fields, who decided and why, Right and Wrong, and the earlier cases it
 * matched, nearest first (each one forgettable). Escape or Close shuts it. */
export function DecisionDrawer({ slug, id, onClose }: { slug: string; id: string; onClose: () => void }) {
  const found = useDecision(id);
  const forget = useForgetPrecedent(slug);
  const toast = useToast();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  const d = found.data;
  return (
    <aside className={styles.drawer} role="dialog" aria-modal="false" aria-label={d ? d.label : 'Decision'}>
      <div className={styles.drawerHead}>
        <div>
          <span className={styles.label}>{d ? `${topic(d.gate)} · ${when(d.at)}` : 'Decision'}</span>
          <h2>{d?.label ?? ' '}</h2>
        </div>
        <button type="button" className={styles.close} onClick={onClose}>
          Close
        </button>
      </div>
      {found.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={found.error ?? forget.error} />
      {d && (
        <>
          <div className={styles.facts}>
            <OutcomePill decision={d} />
            <span className={styles.mono}>
              {whoWords[d.who]}
              {d.who === 'ada' && ` · ${pct(d.confidence)} sure`}
              {d.who === 'you' && d.guess && ` · Ada guessed ${d.guess}`}
            </span>
            {d.mode && modeWords[d.mode] && <span className={styles.muted}>asked: {modeWords[d.mode]}</span>}
            {d.confirmed && <span className={styles.muted}>confirmed right</span>}
            {d.kind === 'case' && <span className={styles.muted}>added by hand</span>}
          </div>
          <RightWrong slug={slug} decision={d} />
          <div className={styles.step}>
            <span className={styles.label}>The item</span>
            {Object.keys(d.fields).length === 0 ? (
              <p className={styles.muted}>It has no fields.</p>
            ) : (
              <dl className={styles.fields}>
                {Object.entries(d.fields).map(([k, v]) => (
                  <div key={k} style={{ display: 'contents' }}>
                    <dt>{fieldName(k)}</dt>
                    <dd>{v.length > LONG || v.includes('\n') ? <Markdown text={v} /> : v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <div className={styles.step}>
            <span className={styles.label}>Cases it matched</span>
            {d.precedents.length === 0 ? (
              <p className={styles.muted}>None yet: nothing it has seen is close to this.</p>
            ) : (
              <ul className={styles.precedents} aria-label="Cases it matched">
                {d.precedents.map((p) => (
                  <li key={p.id}>
                    <span className={styles.itemText} title={p.id}>
                      {p.label ?? `An earlier case (${p.id})`}
                    </span>
                    <span className={styles.outcome}>{String(p.outcome ?? '—')}</span>
                    <span className={styles.sim} title={`${pct(p.similarity)} alike`} aria-label={`${pct(p.similarity)} alike`}>
                      <span style={{ width: `${Math.round((p.similarity ?? 0) * 100)}%` }} />
                    </span>
                    <button
                      type="button"
                      className={styles.wrong}
                      aria-label={`Forget ${p.label ?? p.id}`}
                      disabled={forget.isPending}
                      onClick={() => forget.mutate({ gate: d.gate, id: p.id }, { onSuccess: (r) => toast.show(`Forgotten. ${topic(r.gate)} now rests on ${r.precedents} ${r.precedents === 1 ? 'case' : 'cases'}.`) })}
                    >
                      Forget
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
