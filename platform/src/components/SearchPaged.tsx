import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { Button, EmptyState, TextField } from '@/ui';
import styles from './SearchPaged.module.css';

export const PER_PAGE = 24;
const SEARCH_DELAY_MS = 300;

/**
 * The search and the page a list is on, kept in the URL (`?q=`, `?page=`) so a link lands on the same view: what is
 * typed reaches the URL once typing pauses, and a new search starts at the first page. Artifacts sends both to the
 * server; the lists the server answers whole (models, keys) filter and page here with `useSearchPaging`.
 */
export function useUrlSearch() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);

  const setParam = (changes: Record<string, string | null>, replace = false) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '') next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace },
    );

  const [typed, setTyped] = useState(q);
  useEffect(() => setTyped(q), [q]);
  useEffect(() => {
    if (typed === q) return;
    const timer = setTimeout(() => setParam({ q: typed, page: null }, true), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [typed, q]); // eslint-disable-line react-hooks/exhaustive-deps

  return { q, page, typed, setTyped, setParam, setPage: (next: number) => setParam({ page: String(next) }) };
}

/** Where a page of `total` items starts and ends, and the last page. */
export function pageBounds(page: number, total: number, perPage = PER_PAGE) {
  return {
    from: total === 0 ? 0 : (page - 1) * perPage + 1,
    to: Math.min(page * perPage, total),
    last: Math.max(1, Math.ceil(total / perPage)),
  };
}

/**
 * A whole list the server answered, searched and paged here: `matches` says whether an item fits what was typed
 * (lower-cased, trimmed); `shown` is the page of the ones that do.
 */
export function useSearchPaging<T>(items: T[] | undefined, matches: (item: T, q: string) => boolean) {
  const search = useUrlSearch();
  const needle = search.q.trim().toLowerCase();
  const found = useMemo(() => (items ?? []).filter((item) => !needle || matches(item, needle)), [items, needle, matches]);
  const total = found.length;
  const bounds = pageBounds(search.page, total);
  const shown = found.slice((search.page - 1) * PER_PAGE, search.page * PER_PAGE);
  return { ...search, ...bounds, shown, total, searching: needle !== '' };
}

export function SearchField({ typed, onChange, placeholder }: { typed: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <div className={styles.toolbar}>
      <TextField className={styles.search} label="Search" type="search" value={typed} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  );
}

type PagerProps = { page: number; total: number; from: number; to: number; last: number; onPage: (page: number) => void };

/** Previous and Next, with where the page sits; nothing when one page holds everything. */
export function Pager({ page, total, from, to, last, onPage }: PagerProps) {
  if (total <= PER_PAGE) return null;
  return (
    <nav className={styles.pager} aria-label="Pages">
      <span>
        {from}–{to} of {total}
      </span>
      <div className={styles.pagerButtons}>
        <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button size="sm" disabled={page >= last} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}

/** What a search that found nothing says: the noun is what the list holds ("model", "key"). */
export function NoMatch({ q, noun }: { q: string; noun: string }) {
  return (
    <EmptyState icon="search" title="Nothing matches">
      No {noun} matches “{q}”.
    </EmptyState>
  );
}
