// Minimal types for Node's built-in SQLite (node:sqlite, Node >= 22.13).
// Kept local so the build needs no @types/node version that ships them.
declare module "node:sqlite" {
  type SQLValue = null | number | bigint | string | Uint8Array;
  export class StatementSync {
    run(...params: SQLValue[]): { changes: number | bigint; lastInsertRowid: number | bigint };
    get(...params: SQLValue[]): Record<string, SQLValue> | undefined;
    all(...params: SQLValue[]): Record<string, SQLValue>[];
  }
  export class DatabaseSync {
    constructor(path: string, options?: { open?: boolean; readOnly?: boolean; timeout?: number });
    exec(sql: string): void;
    prepare(sql: string): StatementSync;
    close(): void;
  }
}
