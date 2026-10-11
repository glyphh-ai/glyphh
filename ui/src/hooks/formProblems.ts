/** What a failed submit tells the person: a message on each field the server named, and anything else as
 *  one problem for the whole form, with its code and trace id. Anything unrecognised fails closed: a plain
 *  "try again", never the raw error. */

export interface FormProblem {
  message: string;
  code?: string;
  traceId?: string;
}

export interface Problems {
  fields: Record<string, string>;
  problem: FormProblem | null;
}

interface ServerError {
  status?: number;
  code?: string;
  traceId?: string;
  message?: string;
  body?: { error?: { problems?: Array<{ loc?: unknown[]; msg?: string }> } };
}

export const UNREACHABLE = "Can't reach Glyphh. Check your connection and try again.";
export const UNKNOWN = "Something went wrong. Try again.";

function fieldsOf(err: ServerError): Record<string, string> {
  const fields: Record<string, string> = {};
  for (const p of err.body?.error?.problems ?? []) {
    const name = p.loc?.at(-1);
    if (typeof name === "string" && p.msg && !(name in fields)) fields[name] = p.msg;
  }
  return fields;
}

export function problemsOf(error: unknown): Problems {
  if (typeof error !== "object" || error === null || !("status" in error)) {
    return { fields: {}, problem: { message: UNKNOWN } };
  }
  const err = error as ServerError;
  if (err.status === 0) return { fields: {}, problem: { message: UNREACHABLE } };
  const fields = fieldsOf(err);
  if (Object.keys(fields).length > 0) return { fields, problem: null };
  return { fields: {}, problem: { message: err.message || UNKNOWN, code: err.code, traceId: err.traceId } };
}
