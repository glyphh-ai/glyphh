import type { Client } from "./gen/client/index.js";
import {
  addFunds, changePlan, checkAutoTopUp, getBilling, listInvoices, listLedger, listPlans, listTopUps, nextInvoice,
  openBillingPortal, orgCredit, previewPlanChange, setAutoTopUp, spendByDay, startCardSetup, syncBilling,
} from "./gen/sdk.gen.js";
import type {
  AutoTopUp, AutoTopUpChange, AutoTopUpCheck, Billing, CardSetup, Credit, DaySpend, InvoicePage, LedgerPage, NextInvoice,
  OrgCredit, PaymentStart, PlanChange, PlanPreview, PlanView, Portal, TopUpPage,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type {
  AutoTopUp, AutoTopUpChange, AutoTopUpCheck, Billing, CardSetup, Credit, DaySpend, InvoicePage, LedgerPage, NextInvoice,
  OrgCredit, PaymentStart, PlanChange, PlanPreview, PlanView, Portal, TopUpPage,
};

/** My org's billing: the plans, its credit, and (org admins) the Billing page, paying in Stripe's Payment Element. */
export class BillingApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** The plans on sale now, each its current version. */
  async plans(): Promise<PlanView[]> {
    return unwrap(await listPlans({ client: this.#client }));
  }

  /** My org's plan, when it renews, and its credit this period (any member). */
  async credit(): Promise<OrgCredit> {
    return unwrap(await orgCredit({ client: this.#client }));
  }

  /** The Billing page in one read (org admins). */
  async get(): Promise<Billing> {
    return unwrap(await getBilling({ client: this.#client }));
  }

  /** Start adding credit ($5 to $10,000); confirm the answer's client secret in Stripe's Payment Element. */
  async addFunds(amountCents: number): Promise<PaymentStart> {
    return unwrap(await addFunds({ client: this.#client, body: { amount_cents: amountCents } }));
  }

  /** Each top-up, newest first, with when its credit expires. */
  async topUps(page = 1, size = 25): Promise<TopUpPage> {
    return unwrap(await listTopUps({ client: this.#client, query: { page, size } }));
  }

  /** Turn auto top-up on or off: the trigger, the target and an optional monthly cap. */
  async setAutoTopUp(change: AutoTopUpChange): Promise<AutoTopUp> {
    return unwrap(await setAutoTopUp({ client: this.#client, body: change }));
  }

  /** Reload now if the balance is under the trigger. */
  async checkAutoTopUp(): Promise<AutoTopUpCheck> {
    return unwrap(await checkAutoTopUp({ client: this.#client }));
  }

  /** Save a new card: confirm the answer's client secret in Stripe's Payment Element. */
  async setUpCard(): Promise<CardSetup> {
    return unwrap(await startCardSetup({ client: this.#client }));
  }

  /** What switching to a plan would charge now and on the next invoice. */
  async previewPlan(planId: string): Promise<PlanPreview> {
    return unwrap(await previewPlanChange({ client: this.#client, body: { plan_id: planId } }));
  }

  /** Switch plan: pay (from Free), applying (an upgrade) or scheduled (a downgrade, at the period's end). */
  async changePlan(planId: string): Promise<PlanChange> {
    return unwrap(await changePlan({ client: this.#client, body: { plan_id: planId } }));
  }

  /** Ask Stripe directly what its webhooks would have said, then read the page again. */
  async sync(): Promise<Billing> {
    return unwrap(await syncBilling({ client: this.#client }));
  }

  /** The credit ledger, newest first. */
  async ledger(page = 1, size = 50): Promise<LedgerPage> {
    return unwrap(await listLedger({ client: this.#client, query: { page, size } }));
  }

  /** This period's spend, day by day. */
  async spendByDay(): Promise<DaySpend[]> {
    return unwrap(await spendByDay({ client: this.#client }));
  }

  /** Stripe's invoices, newest first, by cursor: pass the last invoice's id as `after`. */
  async invoices(after?: string, limit = 25): Promise<InvoicePage> {
    return unwrap(await listInvoices({ client: this.#client, query: { after, limit } }));
  }

  /** What Stripe will bill next; null without a paid plan. */
  async nextInvoice(): Promise<NextInvoice | null> {
    return unwrap(await nextInvoice({ client: this.#client })) ?? null;
  }

  /** A link into Stripe's portal: payment methods, invoices, cancelling to Free. */
  async portal(): Promise<Portal> {
    return unwrap(await openBillingPortal({ client: this.#client }));
  }
}
