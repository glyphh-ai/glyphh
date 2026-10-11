/** A request the server refused or failed: its HTTP status (0 when the server was never reached), its body,
 *  and, when the server sent one, its error code and trace id (quote the trace id to find the request). */
export class GlyphhError extends Error {
  readonly status: number;
  readonly body: unknown;
  readonly code: string | undefined;
  readonly traceId: string | undefined;

  constructor(status: number, body: unknown) {
    const detail = errorOf(body);
    super(detail?.message ?? `Glyphh request failed with status ${status}`);
    this.name = "GlyphhError";
    this.status = status;
    this.body = body;
    this.code = detail?.code;
    this.traceId = detail?.trace_id;
  }
}

interface ServerError {
  code?: string;
  message?: string;
  trace_id?: string;
}

function errorOf(body: unknown): ServerError | undefined {
  if (typeof body !== "object" || body === null || !("error" in body)) return undefined;
  const error = (body as { error: unknown }).error;
  return typeof error === "object" && error !== null ? (error as ServerError) : undefined;
}

/** Every generated call answers { data, error, response }: a value, or a GlyphhError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response?: Response }): T {
  if (!result.response?.ok) throw new GlyphhError(result.response?.status ?? 0, result.error);
  return result.data as T;
}
