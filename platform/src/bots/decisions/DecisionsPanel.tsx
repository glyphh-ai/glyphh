import { useEffect, useState } from 'react';
import { useDecisions, useDecisionStats, useRelabel, useConfirm, type Decision, type DecisionQuery, type DecisionSort, type Who } from '@/api/botDecisions';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { Button, Skeleton, useToast } from '@/ui';
import { DecisionDrawer } from './DecisionDrawer';
import { OutcomePill } from './OutcomePill';
import { RightWrong } from './RightWrong';
import { pct, topic, when, whoWords } from './words';
import styles from './decisions.module.css';

const PAGE = 25;
type Filters = { gate?: string; outcome?: string; who?: Who; corrected?: boolean };
const columns: Array<{ id: DecisionSort | null; label: string }> = [
  { id: null, label: 'Item' },
  { id: 'gate', label: 'Deciding' },
  { id: 'outcome', label: 'Outcome' },
  { id: null, label: 'Who' },
  { id: 'confidence', label: 'Confidence' },
  { id: 'time', label: 'Time' },
];

/** The search words, settled: what was typed, once it has not changed for a moment. */
function useSettled(value: string, ms = 250) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

/** A chip that filters the list, pressed while it does. */
function FilterChip({ on, label, onToggle }: { on: boolean; label: string; onToggle: () => void }) {
  return (
    <button type="button" className={styles.chip} aria-pressed={on} onClick={onToggle}>
      {label}
    </button>
  );
}

function Chips({ filters, gates, set }: { filters: Filters; gates: Record<string, string[]>; set: (f: Filters) => void }) {
  const names = Object.keys(gates);
  const outcomes = [...new Set(filters.gate ? (gates[filters.gate] ?? []) : names.flatMap((g) => gates[g] ?? []))];
  const flip = <K extends keyof Filters>(key: K, value: Filters[K]) => set({ ...filters, [key]: filters[key] === value ? undefined : value });
  return (
    <div className={styles.chips} role="group" aria-label="Filters">
      {names.length > 1 && <span className={styles.label}>Deciding</span>}
      {names.length > 1 && names.map((g) => <FilterChip key={g} on={filters.gate === g} label={topic(g)} onToggle={() => set({ ...filters, gate: filters.gate === g ? undefined : g, outcome: undefined })} />)}
      <span className={styles.label}>Outcome</span>
      {outcomes.map((o) => (
        <FilterChip key={o} on={filters.outcome === o} label={o} onToggle={() => flip('outcome', o)} />
      ))}
      <span className={styles.label}>Who</span>
      {(['ada', 'you', 'default'] as const).map((w) => (
        <FilterChip key={w} on={filters.who === w} label={whoWords[w]} onToggle={() => flip('who', w)} />
      ))}
      <FilterChip on={filters.corrected === true} label="Corrected" onToggle={() => flip('corrected', true)} />
      <FilterChip on={filters.corrected === false} label="Not corrected" onToggle={() => flip('corrected', false)} />
    </div>
  );
}

/** What to do with the rows chosen: relabel them all as one outcome, or say they were right. */
function Bulk({ slug, chosen, outcomes, done }: { slug: string; chosen: Decision[]; outcomes: string[]; done: () => void }) {
  const toast = useToast();
  const relabel = useRelabel(slug);
  const confirm = useConfirm(slug);
  const ids = chosen.map((d) => d.id);
  // Said in the screen's own words: the server's sentence names its insides.
  const ok = (words: string) => () => {
    toast.show(words);
    done();
  };
  const oneGate = new Set(chosen.map((d) => d.gate)).size === 1;
  return (
    <div className={styles.bulk} role="region" aria-label="Chosen decisions">
      <strong>{chosen.length} chosen</strong>
      {oneGate ? (
        <>
          <span className={styles.label}>Relabel as</span>
          {outcomes.map((o) => (
            <Button key={o} size="sm" variant="secondary" loading={relabel.isPending && relabel.variables?.outcome === o} onClick={() => relabel.mutate({ ids, outcome: o }, { onSuccess: ok(`Ada learned ${plural(ids.length, 'decision')} as ${o}.`) })}>
              {o}
            </Button>
          ))}
          <Button size="sm" variant="secondary" loading={confirm.isPending} onClick={() => confirm.mutate(ids, { onSuccess: ok(`Kept ${plural(ids.length, 'decision')} as right.`) })}>
            All right
          </Button>
        </>
      ) : (
        <span className={styles.muted}>Choose decisions about one thing to relabel them together.</span>
      )}
      <Button size="sm" variant="ghost" onClick={done}>
        Clear
      </Button>
      <ApiErrorNotice error={relabel.error ?? confirm.error} />
    </div>
  );
}

/**
 * What the bot decides, a slim line each: "Urgency · decided 129 times · asks you 18% · right 87% when it asked".
 * Nothing when it has decided nothing yet.
 */
function Summary({ slug }: { slug: string }) {
  const stats = useDecisionStats(slug);
  const lines = (stats.data ?? []).filter((g) => g.decisions > 0);
  if (lines.length === 0) return null;
  return (
    <ul className={styles.summary} aria-label="What it decides">
      {lines.map((g) => (
        <li key={g.gate}>
          <b>{topic(g.gate)}</b>
          <span>decided {plural(g.decisions, 'time')}</span>
          {g.ask_rate !== null && <span>asks you {pct(g.ask_rate)}</span>}
          {g.agreement !== null && <span>right {pct(g.agreement)} when it asked</span>}
        </li>
      ))}
    </ul>
  );
}

/**
 * A bot's decisions to read and train it from, the one place for them beside the chat's own turns: a slim line per
 * thing it decides, then one row per decision (its readable label, what it was deciding, the outcome, who decided,
 * Ada's confidence and when) with Right and Wrong on each; searched, filtered by chips, sorted by its column heads,
 * paged, and chosen many at once to relabel together. A row's item opens it in a drawer with its fields and the
 * cases it matched. `runId` shows one run's alone.
 */
export function DecisionsPanel({ slug, runId }: { slug: string; runId?: string }) {
  const [words, setWords] = useState('');
  const q = useSettled(words.trim());
  const [filters, setFilters] = useState<Filters>({});
  const [sort, setSort] = useState<{ by: DecisionSort; order: 'asc' | 'desc' }>({ by: 'time', order: 'desc' });
  const [cursors, setCursors] = useState<string[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);
  const query: DecisionQuery = { q: q || undefined, ...filters, run_id: runId, sort: sort.by, order: sort.order, cursor: cursors.at(-1), limit: PAGE };
  const page = useDecisions(slug, query);
  const reset = () => {
    setCursors([]);
    setChosen(new Set());
  };
  useEffect(reset, [q, filters, sort.by, sort.order]);
  const rows = page.data?.decisions ?? [];
  const gates = page.data?.gates ?? {};
  const picked = rows.filter((d) => chosen.has(d.id));
  const toggle = (id: string) => setChosen((was) => (was.has(id) ? new Set([...was].filter((x) => x !== id)) : new Set([...was, id])));
  const sortBy = (by: DecisionSort) => setSort((was) => ({ by, order: was.by === by && was.order === 'desc' ? 'asc' : 'desc' }));
  const first = cursors.length * PAGE + 1;
  return (
    <div className={styles.panel}>
      {!runId && <Summary slug={slug} />}
      <label className={styles.search}>
        <span className={styles.label}>Search</span>
        <input type="search" value={words} placeholder="A title, a sender, a word in it…" aria-label="Search decisions" onChange={(e) => setWords(e.target.value)} />
      </label>
      <Chips filters={filters} gates={gates} set={setFilters} />
      {picked[0] && <Bulk slug={slug} chosen={picked} outcomes={gates[picked[0].gate] ?? []} done={() => setChosen(new Set())} />}
      <ApiErrorNotice error={page.error} />
      <div className={styles.tableWrap}>
        <table className={styles.table} aria-label="Every decision" aria-busy={page.isFetching}>
          <thead>
            <tr>
              <th className={styles.check}>
                <input
                  type="checkbox"
                  aria-label="Choose every decision on this page"
                  checked={rows.length > 0 && picked.length === rows.length}
                  onChange={(e) => setChosen(new Set(e.target.checked ? rows.map((d) => d.id) : []))}
                />
              </th>
              {/* What it was deciding is a column only when the bot decides more than one thing. */}
              {columns.filter((c) => c.id !== 'gate' || Object.keys(gates).length > 1).map((c) => (
                <th key={c.label} aria-sort={c.id && sort.by === c.id ? (sort.order === 'asc' ? 'ascending' : 'descending') : undefined}>
                  {c.id ? (
                    <button type="button" className={styles.sort} data-on={sort.by === c.id} onClick={() => sortBy(c.id!)}>
                      {c.label}
                      {sort.by === c.id && <span aria-hidden="true">{sort.order === 'asc' ? '↑' : '↓'}</span>}
                    </button>
                  ) : (
                    c.label
                  )}
                </th>
              ))}
              <th>Train</th>
            </tr>
          </thead>
          <tbody>
            {page.isPending &&
              Array.from({ length: 4 }, (_, i) => (
                <tr key={i} aria-hidden="true">
                  <td colSpan={8}>
                    <Skeleton height={14} width="70%" />
                  </td>
                </tr>
              ))}
            {rows.map((d) => (
              <tr key={d.id} aria-selected={chosen.has(d.id)}>
                <td className={styles.check}>
                  <input type="checkbox" aria-label={`Choose ${d.label}`} checked={chosen.has(d.id)} onChange={() => toggle(d.id)} />
                </td>
                <td>
                  <button type="button" className={styles.item} title={d.label} onClick={() => setOpen(d.id)}>
                    {d.label}
                  </button>
                </td>
                {Object.keys(gates).length > 1 && <td className={styles.mono}>{topic(d.gate)}</td>}
                <td>
                  <OutcomePill decision={d} />
                </td>
                <td className={styles.mono}>{whoWords[d.who]}</td>
                <td className={styles.mono}>{pct(d.confidence)}</td>
                <td className={styles.mono}>{when(d.at)}</td>
                <td>
                  <RightWrong slug={slug} decision={d} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {page.data && rows.length === 0 && (
          <p className={styles.empty}>{q || Object.values(filters).some((v) => v !== undefined) ? 'No decision matches.' : 'No decisions yet: they show here once it has run.'}</p>
        )}
      </div>
      {page.data && page.data.total > 0 && (
        <nav className={styles.pages} aria-label="Pages">
          <span>
            {first}–{first + rows.length - 1} of {page.data.total}
          </span>
          <div>
            <Button size="sm" variant="ghost" disabled={cursors.length === 0} onClick={() => setCursors((c) => c.slice(0, -1))}>
              Previous
            </Button>
            <Button size="sm" variant="ghost" disabled={!page.data.next_cursor} onClick={() => setCursors((c) => [...c, page.data!.next_cursor!])}>
              Next
            </Button>
          </div>
        </nav>
      )}
      {open && <DecisionDrawer slug={slug} id={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
