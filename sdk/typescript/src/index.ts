import { type Client, createClient } from "./gen/client/index.js";
import { health as healthOperation } from "./gen/sdk.gen.js";
import type { Health } from "./gen/types.gen.js";

export type { Health };

export interface GlyphhOptions {
  /** The Glyphh server, e.g. http://localhost:8080. Falls back to the GLYPHH_URL environment variable. */
  baseUrl?: string;
  /** A fetch to send requests with; defaults to the global fetch. */
  fetch?: typeof fetch;
}

/** A request the server refused or failed: its HTTP status (0 when the server was never reached) and its body. */
export class GlyphhError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    super(`Glyphh request failed with status ${status}`);
    this.name = "GlyphhError";
    this.status = status;
    this.body = body;
  }
}

function resolveBaseUrl(baseUrl: string | undefined): string {
  const url = baseUrl ?? process.env.GLYPHH_URL;
  if (!url) throw new Error("Glyphh needs a server: pass baseUrl or set GLYPHH_URL");
  return url;
}

/** The Glyphh SDK. Every server capability is a method here first. */
export class Glyphh {
  readonly #client: Client;

  constructor(options: GlyphhOptions = {}) {
    this.#client = createClient({ baseUrl: resolveBaseUrl(options.baseUrl), fetch: options.fetch });
  }

  /** Is the server up, and can it reach its database? */
  async health(): Promise<Health> {
    const { data, error, response } = await healthOperation({ client: this.#client });
    if (data === undefined) throw new GlyphhError(response?.status ?? 0, error);
    return data;
  }
}
