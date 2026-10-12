import { type Client, createClient } from "./gen/client/index.js";
import {
  acceptInvite, changeMySettings, declineInvite, disconnectHost, health, listHosts, listMyOrgs, me, mySettings,
} from "./gen/sdk.gen.js";
import type { Health, Host, Me, MeOrg, Settings, SettingsChange } from "./gen/types.gen.js";
import { GlyphhError, unwrap } from "./errors.js";
import { MachinesApi } from "./machines.js";
import { OrgApi } from "./org.js";

export type { Health, Host, Me, MeOrg, Settings, SettingsChange };
export { GlyphhError, MachinesApi, OrgApi };
export type { Face, InstalledPage, InstalledQuery, Launch, MachineCard, MachinePage, SuperPowerStatus } from "./machines.js";
export type { CreatedInvite, InviteView, Member, MemberChange, MemberRole, OrgView } from "./org.js";

export interface GlyphhOptions {
  /** The Glyphh server, e.g. http://localhost:8080. Falls back to the GLYPHH_URL environment variable. */
  baseUrl?: string;
  /** The member's access token, sent as a Bearer token. Falls back to GLYPHH_TOKEN. */
  token?: string;
  /** A fetch to send requests with; defaults to the global fetch. */
  fetch?: typeof fetch;
}

function resolveBaseUrl(baseUrl: string | undefined): string {
  const url = baseUrl ?? process.env.GLYPHH_URL;
  if (!url) throw new Error("Glyphh needs a server: pass baseUrl or set GLYPHH_URL");
  return url;
}

/** The Glyphh SDK. Every server capability is a method here first. */
export class Glyphh {
  readonly #client: Client;
  /** My org: plan and seats, members, invites. */
  readonly org: OrgApi;
  /** My machines and the super powers on them. */
  readonly machines: MachinesApi;

  constructor(options: GlyphhOptions = {}) {
    const token = options.token ?? process.env.GLYPHH_TOKEN;
    this.#client = createClient({
      baseUrl: resolveBaseUrl(options.baseUrl),
      fetch: options.fetch,
      headers: token ? { authorization: `Bearer ${token}` } : undefined,
    });
    this.org = new OrgApi(this.#client);
    this.machines = new MachinesApi(this.#client);
  }

  /** Is the server up, and can it reach its database? */
  async health(): Promise<Health> {
    return unwrap(await health({ client: this.#client }));
  }

  /** Who am I signed in as: my profile, and the org this token acts in (its plan, my role there). */
  async me(): Promise<Me> {
    return unwrap(await me({ client: this.#client }));
  }

  /** Every org I belong to, my Personal org first. */
  async listMyOrgs(): Promise<MeOrg[]> {
    return unwrap(await listMyOrgs({ client: this.#client }));
  }

  /** Accept an invite sent to me: I join its org and keep every other. Answers the org's name. */
  async acceptInvite(invite: string): Promise<string> {
    return unwrap(await acceptInvite({ client: this.#client, body: { invite } })).org;
  }

  /** Decline an invite sent to me: it closes, and its seat is free again. */
  async declineInvite(invite: string): Promise<void> {
    unwrap(await declineInvite({ client: this.#client, body: { invite } }));
  }

  /** What the platform remembers for me: the theme, the rail, each list's rows per page. */
  async settings(): Promise<Settings> {
    return unwrap(await mySettings({ client: this.#client }));
  }

  /** Change any of my settings; a list's rows per page are merged in by the list's name. */
  async changeSettings(change: SettingsChange): Promise<Settings> {
    return unwrap(await changeMySettings({ client: this.#client, body: change }));
  }

  /** The agent hosts (Claude, Codex, ...) connected to my Glyphh. */
  async listHosts(): Promise<Host[]> {
    return unwrap(await listHosts({ client: this.#client }));
  }

  /** Disconnect one host: its tokens stop working at once; the others are untouched. */
  async disconnectHost(hostId: string): Promise<void> {
    unwrap(await disconnectHost({ client: this.#client, path: { host_id: hostId } }));
  }
}
