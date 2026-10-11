import type { ReactNode } from "react";
import styles from "./Table.module.css";

export interface Column<R> {
  key: string;
  header: string;
  cell: (row: R) => ReactNode;
  align?: "start" | "end";
}

export interface TableProps<R> {
  caption: string;
  columns: Column<R>[];
  rows: R[];
  rowKey: (row: R) => string;
  /** Shown in place of the table when there are no rows. */
  empty: ReactNode;
}

/** Rows of one kind: usage, members, runs. Named by its caption for screen readers. */
export function Table<R>({ caption, columns, rows, rowKey, empty }: TableProps<R>) {
  if (rows.length === 0) return <>{empty}</>;
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <caption className={styles.caption}>{caption}</caption>
        <thead><tr>{columns.map((c) => <th key={c.key} scope="col" data-align={c.align}>{c.header}</th>)}</tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>{columns.map((c) => <td key={c.key} data-align={c.align}>{c.cell(row)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
