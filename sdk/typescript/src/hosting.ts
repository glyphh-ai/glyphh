import type { Client } from "./gen/client/index.js";
import {
  deployMachine, destroyHostedMachine, getHostAccount, getHostedMachine, listHostedMachines, removeHostAccount, saveHostAccount,
  startHostedMachine, updateHostedMachine,
} from "./gen/sdk.gen.js";
import type { HostAccountView, HostedView } from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type { HostAccountView, HostedView };
export type HostedState = HostedView["state"];

/** One-click hosting on my own Fly account: its deploy token, deploying a machine there, and keeping it. */
export class HostingApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** My Fly account: a deploy token for my Fly org (and its slug), checked with Fly, kept encrypted, never answered back. */
  async saveAccount(token: string, account = "personal"): Promise<HostAccountView> {
    return unwrap(await saveHostAccount({ client: this.#client, path: { host: "fly" }, body: { token, account } }));
  }

  /** Which Fly account I deploy to: its org and the token's last four characters. */
  async account(): Promise<HostAccountView> {
    return unwrap(await getHostAccount({ client: this.#client, path: { host: "fly" } }));
  }

  /** Forget my Fly token; my machines there keep running. */
  async removeAccount(): Promise<void> {
    unwrap(await removeHostAccount({ client: this.#client, path: { host: "fly" } }));
  }

  /** A new machine on my Fly account in one click: it signs itself in on first boot. */
  async deploy(name: string, region = "iad"): Promise<HostedView> {
    return unwrap(await deployMachine({ client: this.#client, body: { name, region } }));
  }

  /** My machines at a host, newest first, each with its state as the Deploy page shows it. */
  async list(): Promise<HostedView[]> {
    return unwrap(await listHostedMachines({ client: this.#client }));
  }

  /** One of them, with what Fly says of it now. */
  async get(hostedId: string): Promise<HostedView> {
    return unwrap(await getHostedMachine({ client: this.#client, path: { hosted_id: hostedId } }));
  }

  /** Wake one Fly stopped. */
  async start(hostedId: string): Promise<HostedView> {
    return unwrap(await startHostedMachine({ client: this.#client, path: { hosted_id: hostedId } }));
  }

  /** Move it to a new rrotor image (the server's own when none is named). */
  async update(hostedId: string, image?: string): Promise<HostedView> {
    return unwrap(await updateHostedMachine({ client: this.#client, path: { hosted_id: hostedId }, body: { image: image ?? null } }));
  }

  /** Destroy it at Fly (its app, VM and volume) and remove its machine. */
  async destroy(hostedId: string): Promise<void> {
    unwrap(await destroyHostedMachine({ client: this.#client, path: { hosted_id: hostedId } }));
  }
}
