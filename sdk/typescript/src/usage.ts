import type { Client } from "./gen/client/index.js";
import {
  exportUsageCalls, exportUsageUses, listingStats, usageBy, usageCall, usageCalls, usagePage, usagePeriods, usageRuns, usageUse,
  usageUses,
} from "./gen/sdk.gen.js";
import type {
  Call, CallPage, GroupPage, ListingStats, Period, RunPage, UsageByData, UsageCallsData, UsagePage, UsagePageData, UsageRunsData,
  Use, UsePage,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type { Call, CallPage, GroupPage, ListingStats, Period, RunPage, Use, UsePage, UsagePage };
export type UsageQuery = NonNullable<UsagePageData["query"]>;
export type UsageBy = UsageByData["path"]["by"];
export type GroupQuery = NonNullable<UsageByData["query"]>;
export type RunQuery = NonNullable<UsageRunsData["query"]>;
export type LogQuery = NonNullable<UsageCallsData["query"]>;
type Scope = "me" | "org";

/** Usage: a page's top, its breakdowns, runs, periods, the audit log's calls and uses, and a listing's stats. */
export class UsageApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  /** The days covered, the tiles, each day (today still counting) and the org's credit. */
  async page(query: UsageQuery = {}): Promise<UsagePage> { return unwrap(await usagePage({ client: this.#c, query })); }
  async by(by: UsageBy, query: GroupQuery = {}): Promise<GroupPage> { return unwrap(await usageBy({ client: this.#c, path: { by }, query })); }
  async runs(query: RunQuery = {}): Promise<RunPage> { return unwrap(await usageRuns({ client: this.#c, query })); }
  async periods(): Promise<Period[]> { return unwrap(await usagePeriods({ client: this.#c })); }
  /** Connector calls, newest first; pass the answer's `next` as `after` for the page after. */
  async calls(query: LogQuery = {}): Promise<CallPage> { return unwrap(await usageCalls({ client: this.#c, query })); }
  async call(id: string, scope: Scope = "me"): Promise<Call> {
    return unwrap(await usageCall({ client: this.#c, path: { call_id: id }, query: { scope } }));
  }
  async exportCalls(query: LogQuery = {}): Promise<string> {
    return unwrap(await exportUsageCalls({ client: this.#c, query, parseAs: "text" })) as string;
  }
  async uses(query: LogQuery = {}): Promise<UsePage> { return unwrap(await usageUses({ client: this.#c, query })); }
  async use(id: string, scope: Scope = "me"): Promise<Use> {
    return unwrap(await usageUse({ client: this.#c, path: { use_id: id }, query: { scope } }));
  }
  async exportUses(query: LogQuery = {}): Promise<string> {
    return unwrap(await exportUsageUses({ client: this.#c, query, parseAs: "text" })) as string;
  }
  /** A publisher's stats for their listing: installs, installs in use, runs, by day and by version. */
  async listingStats(listingId: string, days = 30): Promise<ListingStats> {
    return unwrap(await listingStats({ client: this.#c, path: { listing_id: listingId }, query: { days } }));
  }
}
