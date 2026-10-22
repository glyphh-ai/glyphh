import type { RolePath } from './spec';

/** A CSV file's header: its first record's fields, quotes and doubled quotes read as CSV has them. */
export function csvHeader(text: string): string[] {
  const fields: string[] = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]!;
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') {
      fields.push(field);
      field = '';
    } else if (ch === '\n' || ch === '\r') break;
    else field += ch;
  }
  fields.push(field);
  return fields.map((f) => f.trim()).filter((f, i, all) => f !== '' || i < all.length - 1);
}

/** Where a column goes: a role's path, `outcome`, `outcome.<output>`, `ts`, `id`, or nowhere (null). */
export type Target = string | null;

/** Each header's likely target: its own name when it is a role's path or a role's only name, an outcome, ts or id. */
export function guessMapping(headers: string[], roles: RolePath[], outputs: string[]): Record<string, Target> {
  const byName = new Map<string, string[]>();
  for (const { path, role } of roles) byName.set(role.name, [...(byName.get(role.name) ?? []), path]);
  const paths = new Set(roles.map((r) => r.path));
  const named = new Set(outputs.filter((o) => o !== 'default').map((o) => `outcome.${o}`));
  return Object.fromEntries(
    headers.map((header) => {
      const h = header.trim();
      if (paths.has(h) || named.has(h) || ['outcome', 'ts', 'id'].includes(h)) return [header, h];
      const only = byName.get(h);
      return [header, only?.length === 1 ? only[0]! : null];
    }),
  );
}
