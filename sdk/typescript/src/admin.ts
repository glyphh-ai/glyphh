import type { Client } from "./gen/client/index.js";
import {
  adminAddCatalogModel, adminAddCategory, adminAddProvider, adminAuditLog, adminBillingSettings, adminCatalogModels, adminCategories,
  adminChangeCatalogModel, adminChangeProvider, adminCompPlan, adminDeleteCategory, adminDisableOrg, adminEnableOrg, adminEndComp,
  adminExportAuditLog, adminGiftCredit, adminImportModels, adminListings, adminMovePlan, adminMoveOrgsToPlan, adminNextPlanVersion,
  adminOrderCategories, adminOrg, adminOrgLedger, adminOrgMachines, adminOrgMembers, adminOrgPowers, adminOrgs, adminOrgSuperPowers,
  adminPlans, adminProviders, adminRemoveCatalogModel, adminRemoveProvider, adminRenameCategory, adminSetBillingSettings,
  adminSetFeatured, adminSetProviderLogo, adminWriteReviewerReport,
} from "./gen/sdk.gen.js";
import type {
  AdminAuditLogData, AdminCatalogModelsData, AdminListing, AdminListingPage, AdminListingsData, AdminModel, AdminModelPage,
  AdminNextPlanVersionData, AdminOrgsData, AdminProvider, AdminProvidersData, AuditPage, BillingSettingsView, CategoryView, Imported,
  Ledger, ListingView, ModelChange, ModelIn, Moved, NextVersion, OrgMachines, OrgMembers, OrgOverview, OrgPage, OrgPowers,
  OrgSuperPowers, PlanVersion, ProviderChange, ProviderIn, SettingsIn,
} from "./gen/types.gen.js";
import type { Picture } from "./discover.js";
import { unwrap } from "./errors.js";

export type {
  AdminListing, AdminListingPage, AdminModel, AdminModelPage, AdminProvider, BillingSettingsView, CategoryView, Imported, Ledger,
  ModelChange, ModelIn, Moved, NextVersion, OrgMachines, OrgMembers, OrgOverview, OrgPage, OrgPowers, OrgSuperPowers, PlanVersion,
  ProviderChange, ProviderIn, SettingsIn,
};
export type AdminOrgQuery = NonNullable<AdminOrgsData["query"]>;
export type AdminModelQuery = NonNullable<AdminCatalogModelsData["query"]>;
export type AdminListingQuery = NonNullable<AdminListingsData["query"]>;
export type AdminAuditQuery = NonNullable<AdminAuditLogData["query"]>;
export type PlanFamily = AdminNextPlanVersionData["path"]["family"];
type Paging = { page?: number; size?: number };

/** Glyphh admin, for Glyphh's staff: every org and what staff do to one; plans, their versions and the billing settings. */
export class AdminApi {
  readonly #c: Client;
  /** The model catalog: providers and their models. */
  readonly catalog: AdminCatalogApi;
  /** The marketplace: listings, the featured shelf, the reviewer's report, categories; and Glyphh's audit log. */
  readonly market: AdminMarketApi;
  constructor(client: Client) {
    this.#c = client;
    this.catalog = new AdminCatalogApi(client);
    this.market = new AdminMarketApi(client);
  }
  async orgs(query: AdminOrgQuery = {}): Promise<OrgPage> { return unwrap(await adminOrgs({ client: this.#c, query })); }
  async org(id: string): Promise<OrgOverview> { return unwrap(await adminOrg({ client: this.#c, path: { org_id: id } })); }
  async members(id: string, query: Paging & { q?: string } = {}): Promise<OrgMembers> {
    return unwrap(await adminOrgMembers({ client: this.#c, path: { org_id: id }, query }));
  }
  async machines(id: string, query: Paging = {}): Promise<OrgMachines> {
    return unwrap(await adminOrgMachines({ client: this.#c, path: { org_id: id }, query }));
  }
  async powers(id: string, query: Paging & { kind?: string } = {}): Promise<OrgPowers> {
    return unwrap(await adminOrgPowers({ client: this.#c, path: { org_id: id }, query }));
  }
  async superPowers(id: string, query: Paging = {}): Promise<OrgSuperPowers> {
    return unwrap(await adminOrgSuperPowers({ client: this.#c, path: { org_id: id }, query }));
  }
  async ledger(id: string, query: Paging = {}): Promise<Ledger> {
    return unwrap(await adminOrgLedger({ client: this.#c, path: { org_id: id }, query }));
  }
  /** Credit in cents ($1 to $10,000) with a note. */
  async gift(id: string, cents: number, note: string): Promise<OrgOverview> {
    return unwrap(await adminGiftCredit({ client: this.#c, path: { org_id: id }, body: { cents, note } }));
  }
  async comp(id: string, planId: string): Promise<OrgOverview> {
    return unwrap(await adminCompPlan({ client: this.#c, path: { org_id: id }, body: { plan_id: planId } }));
  }
  async endComp(id: string): Promise<OrgOverview> { return unwrap(await adminEndComp({ client: this.#c, path: { org_id: id } })); }
  /** To its family's version on sale, in 30 days. */
  async move(id: string, planId: string): Promise<OrgOverview> {
    return unwrap(await adminMovePlan({ client: this.#c, path: { org_id: id }, body: { plan_id: planId } }));
  }
  async disable(id: string, reason: string): Promise<OrgOverview> {
    return unwrap(await adminDisableOrg({ client: this.#c, path: { org_id: id }, body: { reason } }));
  }
  async enable(id: string): Promise<OrgOverview> { return unwrap(await adminEnableOrg({ client: this.#c, path: { org_id: id } })); }
  async plans(): Promise<PlanVersion[]> { return unwrap(await adminPlans({ client: this.#c })); }
  async nextVersion(family: PlanFamily, body: NextVersion): Promise<PlanVersion> {
    return unwrap(await adminNextPlanVersion({ client: this.#c, path: { family }, body }));
  }
  /** Every org on an older version of this plan's family moves to it, in 30 days. */
  async moveOrgs(planId: string): Promise<Moved> { return unwrap(await adminMoveOrgsToPlan({ client: this.#c, path: { plan_id: planId } })); }
  async billingSettings(): Promise<BillingSettingsView> { return unwrap(await adminBillingSettings({ client: this.#c })); }
  async setBillingSettings(body: SettingsIn): Promise<BillingSettingsView> {
    return unwrap(await adminSetBillingSettings({ client: this.#c, body }));
  }
}

/** Glyphh admin → Models. */
export class AdminCatalogApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async providers(query: NonNullable<AdminProvidersData["query"]> = {}): Promise<AdminProvider[]> {
    return unwrap(await adminProviders({ client: this.#c, query }));
  }
  async addProvider(body: ProviderIn): Promise<AdminProvider> { return unwrap(await adminAddProvider({ client: this.#c, body })); }
  async changeProvider(id: string, body: ProviderChange): Promise<AdminProvider> {
    return unwrap(await adminChangeProvider({ client: this.#c, path: { provider_id: id }, body }));
  }
  async removeProvider(id: string): Promise<AdminProvider> {
    return unwrap(await adminRemoveProvider({ client: this.#c, path: { provider_id: id } }));
  }
  /** The provider's own list of models, read with this key (never kept). */
  async importModels(id: string, apiKey: string): Promise<Imported> {
    return unwrap(await adminImportModels({ client: this.#c, path: { provider_id: id }, body: { api_key: apiKey } }));
  }
  async setLogo(id: string, logo: Picture, dark = false): Promise<AdminProvider> {
    return unwrap(await adminSetProviderLogo({
      client: this.#c, path: { provider_id: id }, query: { dark }, body: logo.data,
      headers: { "Content-Type": logo.type, "x-file-name": logo.name ?? "logo.png" },
    }));
  }
  async models(query: AdminModelQuery = {}): Promise<AdminModelPage> { return unwrap(await adminCatalogModels({ client: this.#c, query })); }
  async addModel(body: ModelIn): Promise<AdminModel> { return unwrap(await adminAddCatalogModel({ client: this.#c, body })); }
  async changeModel(id: string, body: ModelChange): Promise<AdminModel> {
    return unwrap(await adminChangeCatalogModel({ client: this.#c, path: { model_id: id }, body }));
  }
  async removeModel(id: string): Promise<AdminModel> { return unwrap(await adminRemoveCatalogModel({ client: this.#c, path: { model_id: id } })); }
}

/** Glyphh admin → Marketplace and Audit log. */
export class AdminMarketApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async listings(query: AdminListingQuery = {}): Promise<AdminListingPage> { return unwrap(await adminListings({ client: this.#c, query })); }
  /** The featured shelf, in this order. */
  async setFeatured(listingIds: string[]): Promise<AdminListing[]> {
    return unwrap(await adminSetFeatured({ client: this.#c, body: { listing_ids: listingIds } }));
  }
  async report(listingVersionId: string, report: Record<string, unknown>): Promise<ListingView> {
    return unwrap(await adminWriteReviewerReport({ client: this.#c, path: { listing_version_id: listingVersionId }, body: { report } }));
  }
  async categories(): Promise<CategoryView[]> { return unwrap(await adminCategories({ client: this.#c })); }
  async addCategory(name: string): Promise<CategoryView> { return unwrap(await adminAddCategory({ client: this.#c, body: { name } })); }
  async renameCategory(id: string, name: string): Promise<CategoryView> {
    return unwrap(await adminRenameCategory({ client: this.#c, path: { category_id: id }, body: { name } }));
  }
  async deleteCategory(id: string): Promise<void> { unwrap(await adminDeleteCategory({ client: this.#c, path: { category_id: id } })); }
  async orderCategories(ids: string[]): Promise<CategoryView[]> {
    return unwrap(await adminOrderCategories({ client: this.#c, body: { category_ids: ids } }));
  }
  async audit(query: AdminAuditQuery = {}): Promise<AuditPage> { return unwrap(await adminAuditLog({ client: this.#c, query })); }
  async exportAudit(query: AdminAuditQuery = {}): Promise<string> {
    return unwrap(await adminExportAuditLog({ client: this.#c, query, parseAs: "text" })) as string;
  }
}
