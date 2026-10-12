import type { Client } from "./gen/client/index.js";
import {
  addFromMarketplace, addListingScreenshot, browseMarketplace, changeListing, changeListingVersion, commentOnListing,
  createListing, decideReview, getListing, listingComments, marketplaceHome, marketplaceListing, myListings,
  orderListingScreenshots, removeListingScreenshot, reviewQueue, setListingIcon, submitListing, unpublishListing,
  updateFromMarketplace, withdrawListing,
} from "./gen/sdk.gen.js";
import type {
  Added, Comment, Home, InReview, ListingChange, ListingView, MarketDetail, MarketPage, NewListing, ReviewDecision, VersionChange,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type {
  Added, Comment, Home, InReview, ListingChange, ListingView, MarketDetail, MarketPage, NewListing, ReviewDecision, VersionChange,
};
/** A version waiting for review (the name the SDK first gave it). */
export type Waiting = InReview;
export interface MarketQuery { kind?: "custom" | "super_power"; type?: string; category?: string; q?: string; page?: number; size?: number }
export type Picture = { data: Blob; type: "image/png" | "image/jpeg"; name?: string };

/** Publishing: my listings, the version on its way, its pictures, submitting, and the review queues. */
export class ListingsApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async mine(): Promise<ListingView[]> { return unwrap(await myListings({ client: this.#c })); }
  async create(body: NewListing): Promise<ListingView> { return unwrap(await createListing({ client: this.#c, body })); }
  async get(id: string): Promise<ListingView> { return unwrap(await getListing({ client: this.#c, path: { listing_id: id } })); }
  async change(id: string, body: ListingChange): Promise<ListingView> {
    return unwrap(await changeListing({ client: this.#c, path: { listing_id: id }, body }));
  }
  /** The version on its way: its number and release notes (starting one when none is). */
  async changeVersion(id: string, body: VersionChange): Promise<ListingView> {
    return unwrap(await changeListingVersion({ client: this.#c, path: { listing_id: id }, body }));
  }
  async setIcon(id: string, icon: Picture): Promise<ListingView> {
    return unwrap(await setListingIcon({
      client: this.#c, path: { listing_id: id }, body: icon.data, headers: { "Content-Type": icon.type, "x-file-name": icon.name },
    }));
  }
  async addScreenshot(id: string, shot: Picture): Promise<ListingView> {
    return unwrap(await addListingScreenshot({
      client: this.#c, path: { listing_id: id }, body: shot.data, headers: { "Content-Type": shot.type, "x-file-name": shot.name },
    }));
  }
  async orderScreenshots(id: string, screenshots: string[]): Promise<ListingView> {
    return unwrap(await orderListingScreenshots({ client: this.#c, path: { listing_id: id }, body: { screenshots } }));
  }
  async removeScreenshot(id: string, shotId: string): Promise<ListingView> {
    return unwrap(await removeListingScreenshot({ client: this.#c, path: { listing_id: id, shot_id: shotId } }));
  }
  /** Check everything (each thing to fix is named), freeze the version and send it for review. */
  async submit(id: string): Promise<ListingView> { return unwrap(await submitListing({ client: this.#c, path: { listing_id: id } })); }
  async withdraw(id: string): Promise<ListingView> { return unwrap(await withdrawListing({ client: this.#c, path: { listing_id: id } })); }
  async unpublish(id: string): Promise<ListingView> { return unwrap(await unpublishListing({ client: this.#c, path: { listing_id: id } })); }
  async comments(id: string): Promise<Comment[]> { return unwrap(await listingComments({ client: this.#c, path: { listing_id: id } })); }
  async comment(id: string, body: string): Promise<Comment[]> {
    return unwrap(await commentOnListing({ client: this.#c, path: { listing_id: id }, body: { body } }));
  }
  /** What waits for me to review: my org's (org admins) or the marketplace's (super admins). */
  async queue(step: "org" | "glyphh" = "org"): Promise<Waiting[]> { return unwrap(await reviewQueue({ client: this.#c, query: { step } })); }
  async decide(versionId: string, body: ReviewDecision): Promise<ListingView> {
    return unwrap(await decideReview({ client: this.#c, path: { listing_version_id: versionId }, body }));
  }
}

/** The Marketplace: shelves, search, a listing's page, adding, and updating my copy. */
export class MarketplaceApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async home(kind?: "custom" | "super_power"): Promise<Home> { return unwrap(await marketplaceHome({ client: this.#c, query: { kind } })); }
  async browse(query: MarketQuery = {}): Promise<MarketPage> { return unwrap(await browseMarketplace({ client: this.#c, query })); }
  async get(id: string): Promise<MarketDetail> { return unwrap(await marketplaceListing({ client: this.#c, path: { listing_id: id } })); }
  async add(id: string): Promise<Added> { return unwrap(await addFromMarketplace({ client: this.#c, path: { listing_id: id } })); }
  async update(powerId: string): Promise<Added> { return unwrap(await updateFromMarketplace({ client: this.#c, path: { power_id: powerId } })); }
}
