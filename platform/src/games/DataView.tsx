import type { ReactNode } from 'react';
import { stamp } from '@/lib/format';
import { Card } from '@/ui';
import type { Row } from './catalog';
import styles from './games.module.css';

/**
 * A game's answer, shown as it came: numbers and words as facts, lists as tables. Each game words its own answers;
 * what a player wrote comes marked `{quoted: …}` and is shown as plain text, never as markup.
 */

const timeKey = /(^|_)(at|created|updated|first|last|since|joined|when|started|ended|opened|made)$/;
/** Yes-or-no columns the games keep as 0 and 1. */
const flagKey = /^(banned|hidden|paid|pass|live|off|shared|disputed|checked)$/;

export function label(key: string): string {
  const words = key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/(\D)(24)$/, '$1, 24h')
    .replace(/(\D)(7)$/, '$1, 7 days')
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const isQuoted = (v: unknown): v is { quoted: unknown } => Boolean(v) && typeof v === 'object' && !Array.isArray(v) && Object.keys(v as object).length === 1 && 'quoted' in (v as object);
const isPlain = (v: unknown): v is Row => Boolean(v) && typeof v === 'object' && !Array.isArray(v) && !isQuoted(v);
const isRows = (v: unknown): v is Row[] => Array.isArray(v) && v.length > 0 && v.every(isPlain);

function compact(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (isQuoted(value)) return compact(value.quoted);
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return value.map(compact).filter(Boolean).join(', ');
  return Object.entries(value)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${label(k)}: ${compact(v)}`)
    .join(' · ');
}

/** One value in a table cell or beside its label. */
export function Value({ value, field = '' }: { value: unknown; field?: string }): ReactNode {
  if (value === null || value === undefined || value === '') return <span className={styles.none}>–</span>;
  if (isQuoted(value)) return <Value value={value.quoted} field={field} />;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') {
    if (flagKey.test(field) && (value === 0 || value === 1)) return value ? 'Yes' : 'No';
    if (timeKey.test(field) && value > 1e11) return <span className={styles.num}>{stamp(new Date(value).toISOString())}</span>;
    return <span className={styles.num}>{value.toLocaleString('en-GB')}</span>;
  }
  if (typeof value === 'string') {
    if (/^https?:\/\//.test(value)) {
      return (
        <a href={value} target="_blank" rel="noreferrer" className={styles.link}>
          {value.replace(/^https?:\/\//, '')}
        </a>
      );
    }
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) return <span className={styles.num}>{stamp(value)}</span>;
    return value;
  }
  const text = compact(value);
  return <span className={styles.compact} title={text.length > 140 ? text : undefined}>{text.length > 140 ? `${text.slice(0, 140)}…` : text || '–'}</span>;
}

/** The columns a list shows: those asked for, else the first rows' simple ones, eight at most. */
export function columnsOf(rows: Row[], wanted?: readonly string[]): string[] {
  if (wanted) return [...wanted];
  const keys: string[] = [];
  for (const row of rows.slice(0, 20)) {
    for (const [k, v] of Object.entries(row)) {
      if (keys.includes(k) || k === 'about_this_answer') continue;
      if (Array.isArray(v) && v.length > 3) continue;
      keys.push(k);
    }
  }
  return keys.slice(0, 8);
}

export function Table({ rows, columns, name, extra }: { rows: Row[]; columns: string[]; name: string; extra?: (row: Row) => ReactNode }) {
  return (
    <div className={styles.tableBox}>
      <table className={styles.table} aria-label={name}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{label(c)}</th>
            ))}
            {extra && <th aria-label="Actions" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={String(row.id ?? row.did ?? row.code ?? i)}>
              {columns.map((c) => (
                <td key={c} data-label={label(c)}>
                  <Value value={row[c]} field={c} />
                </td>
              ))}
              {extra && <td className={styles.rowActions}>{extra(row)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A whole answer: its facts first, then each part under its own heading. */
export function Facts({ data, depth = 0 }: { data: unknown; depth?: number }) {
  if (isRows(data)) return <Table rows={data} columns={columnsOf(data)} name="List" />;
  if (!isPlain(data)) {
    return (
      <p className={styles.text}>
        <Value value={data} />
      </p>
    );
  }
  const entries = Object.entries(data).filter(([k]) => k !== 'about_this_answer');
  const simple = entries.filter(([, v]) => !isPlain(v) && !isRows(v) && !(typeof v === 'string' && v.length > 160));
  const long = entries.filter(([, v]) => typeof v === 'string' && v.length > 160);
  const parts = entries.filter(([, v]) => isPlain(v) || isRows(v));
  return (
    <div className={styles.facts}>
      {simple.length > 0 && (
        <dl className={styles.dl}>
          {simple.map(([k, v]) => (
            <div key={k}>
              <dt>{label(k)}</dt>
              <dd>
                <Value value={v} field={k} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      {long.map(([k, v]) => (
        <div key={k}>
          <h3 className={styles.partTitle}>{label(k)}</h3>
          <p className={styles.text}>{String(v)}</p>
        </div>
      ))}
      {parts.map(([k, v]) =>
        depth >= 2 ? (
          <div key={k}>
            <h3 className={styles.partTitle}>{label(k)}</h3>
            <Value value={v} />
          </div>
        ) : depth === 0 ? (
          <Card key={k}>
            <h2 className={styles.cardTitle}>{label(k)}</h2>
            {isRows(v) ? <Table rows={v} columns={columnsOf(v)} name={label(k)} /> : <Facts data={v} depth={depth + 1} />}
          </Card>
        ) : (
          <div key={k}>
            <h3 className={styles.partTitle}>{label(k)}</h3>
            {isRows(v) ? <Table rows={v} columns={columnsOf(v)} name={label(k)} /> : <Facts data={v} depth={depth + 1} />}
          </div>
        ),
      )}
    </div>
  );
}

/** Where a list's rows are in an answer: the list named, `items`, or the answer itself. */
export function rowsOf(data: unknown, list?: string): Row[] | null {
  if (Array.isArray(data)) return data.filter(isPlain);
  if (!isPlain(data)) return null;
  const found = list ? data[list] : data.items;
  return Array.isArray(found) ? found.filter(isPlain) : null;
}
