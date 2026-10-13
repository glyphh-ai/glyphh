import { type Client, createClient } from "./gen/client/index.js";
import {
  acceptInvite, changeMe, changeMySettings, declineInvite, disconnectHost, health, listHosts, listMyOrgs, me, mySettings,
  signOutEverywhere,
} from "./gen/sdk.gen.js";
import type { Health, Host, Me, MeOrg, ProfileChange, Settings, SettingsChange } from "./gen/types.gen.js";
import { AdminApi, AdminCatalogApi, AdminMarketApi } from "./admin.js";
import { BillingApi } from "./billing.js";
import { ListingsApi, MarketplaceApi } from "./discover.js";
import { CustomPowersApi, SchedulesApi, SuperPowersApi } from "./editors.js";
import { GlyphhError, unwrap } from "./errors.js";
import { MachinesApi } from "./machines.js";
import { OrgApi } from "./org.js";
import { ApiKeysApi, OrgAdminApi } from "./orgadmin.js";
export type {
  Call, CallPage, GroupPage, GroupQuery, ListingStats, LogQuery, Period, RunPage, RunQuery, UsageBy, UsagePage, UsageQuery, Use, UsePage,
} from "./usage.js";
import { UsageApi } from "./usage.js";
import { PowersApi } from "./powers.js";
import { NeedsYouApi, ThreadsApi } from "./threads.js";

export type { Health, Host, Me, MeOrg, ProfileChange, Settings, SettingsChange };
export { AdminApi, AdminCatalogApi, AdminMarketApi, ApiKeysApi, BillingApi, CustomPowersApi, GlyphhError, ListingsApi, MachinesApi, MarketplaceApi, NeedsYouApi, OrgAdminApi, OrgApi, PowersApi, SchedulesApi, SuperPowersApi, ThreadsApi, UsageApi };
export type {
  AutoTopUp, AutoTopUpChange, AutoTopUpCheck, Billing, CardSetup, Credit, DaySpend, InvoicePage, LedgerPage, NextInvoice,
  OrgCredit, PaymentStart, PlanChange, PlanPreview, PlanView, Portal, TopUpPage,
} from "./billing.js";
export type {
  CanAdd, CatalogPage, CatalogQuery, ConnectionView, ConnectLink, LoopState, MachineLoops, ModelView, NewBrowser, NewFolder, NewModel, Place, ProviderView,
  ServicePage, ToolChange, ToolPage,
} from "./powers.js";
export type {
  CustomChange, CustomPage, CustomPower, CustomQuery, FileText, Flow, GrantChange, LoopChoice, NewCustom, NewSuperPower, RunList,
  RunsQuery, RunView, ScheduleIn, ScheduleView, Slots, SuperPowerChange, SuperPowerPage, SuperPowerQuery, SuperPowerView,
} from "./editors.js";
export type {
  Added, Comment, Home, InReview, ListingChange, ListingView, MarketDetail, MarketPage, MarketQuery, NewListing, Picture,
  ReviewDecision, VersionChange, Waiting,
} from "./discover.js";
export type * from "./admin.js";
export type { Face, InstalledPage, InstalledQuery, Launch, MachineCard, MachinePage, SuperPowerStatus } from "./machines.js";
export type { CreatedInvite, InviteView, Member, MemberChange, MemberRole, OrgView } from "./org.js";
export type {
  AuditFilters, AuditPage, AuditQuery, Impact, InviteMany, InviteResult, KeysPage, KeyView, LimitKind, LimitQuery, LimitView, MadeKey,
  Maker, MemberKeys, MemberTeams, NewKey, PeopleQuery, PeoplePage, TeamChange, TeamView,
} from "./orgadmin.js";
export type {
  Answered, CrewCount, CrewFace, Question, QuestionPage, ThreadChange, ThreadDetail, ThreadMachine, ThreadPage, ThreadQuery, ThreadRow,
} from "./threads.js";

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
  /** My machines' threads, by their record (their messages are on the machine). */
  readonly threads: ThreadsApi;
  /** The questions my super powers are waiting on. */
  readonly needsYou: NeedsYouApi;
  /** My org's plans, credit and billing. */
  readonly billing: BillingApi;
  /** My powers: models, connections and their tools, folders, browsers. */
  readonly powers: PowersApi;
  /** My super powers and their editor. */
  readonly superPowers: SuperPowersApi;
  /** My skills, plugins, tasks and apps. */
  readonly custom: CustomPowersApi;
  /** Super powers and tasks on the clock. */
  readonly schedules: SchedulesApi;
  /** Publishing my powers and reviewing listings. */
  readonly listings: ListingsApi;
  /** The Marketplace. */
  readonly marketplace: MarketplaceApi;
  /** Org admin: people, teams, limits and the audit log. */
  readonly orgAdmin: OrgAdminApi;
  /** API keys: mine, and the org's for org admins. */
  readonly apiKeys: ApiKeysApi;
  /** Usage: runs, uses, tokens, connection calls and credit, and its audit log. */
  readonly usage: UsageApi;
  /** Glyphh admin, for Glyphh's staff: orgs, plans, the catalog, the marketplace and Glyphh's audit log. */
  readonly admin: AdminApi;

  constructor(options: GlyphhOptions = {}) {
    const token = options.token ?? process.env.GLYPHH_TOKEN;
    this.#client = createClient({
      baseUrl: resolveBaseUrl(options.baseUrl),
      fetch: options.fetch,
      headers: token ? { authorization: `Bearer ${token}` } : undefined,
    });
    this.org = new OrgApi(this.#client);
    this.machines = new MachinesApi(this.#client);
    this.threads = new ThreadsApi(this.#client);
    this.needsYou = new NeedsYouApi(this.#client);
    this.billing = new BillingApi(this.#client);
    this.powers = new PowersApi(this.#client);
    this.superPowers = new SuperPowersApi(this.#client);
    this.custom = new CustomPowersApi(this.#client);
    this.schedules = new SchedulesApi(this.#client);
    this.listings = new ListingsApi(this.#client);
    this.marketplace = new MarketplaceApi(this.#client);
    this.orgAdmin = new OrgAdminApi(this.#client);
    this.apiKeys = new ApiKeysApi(this.#client);
    this.usage = new UsageApi(this.#client);
    this.admin = new AdminApi(this.#client);
  }

  /** Is the server up, and can it reach its database? */
  async health(): Promise<Health> {
    return unwrap(await health({ client: this.#client }));
  }

  /** Who am I signed in as: my profile, and the org this token acts in (its plan, my role there). */
  async me(): Promise<Me> {
    return unwrap(await me({ client: this.#client }));
  }

  /** Change my first or last name (an empty one clears it); answers me as I am now. */
  async changeMe(change: ProfileChange): Promise<Me> {
    return unwrap(await changeMe({ client: this.#client, body: change }));
  }

  /** Sign me out of the platform everywhere: every browser and org; connected AI hosts stay connected. */
  async signOutEverywhere(): Promise<void> {
    unwrap(await signOutEverywhere({ client: this.#client }));
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
