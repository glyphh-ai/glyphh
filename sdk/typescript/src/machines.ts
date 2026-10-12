import type { Client } from "./gen/client/index.js";
import { listInstalledSuperPowers, listMachines, openMachine } from "./gen/sdk.gen.js";
import type { Face, InstalledPage, Launch, MachineCard, MachinePage } from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type { Face, InstalledPage, Launch, MachineCard, MachinePage };
export type SuperPowerStatus = "working" | "thinking" | "needs_you" | "idle" | "stuck" | "done";

export interface InstalledQuery { q?: string; status?: SuperPowerStatus; page?: number; size?: number }

/** My machines: their cards, the super powers installed on each, and opening one. */
export class MachinesApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** My machines, connected first, each with its 8 most recently active super powers and their counts. */
  async list(page = 1, size = 12): Promise<MachinePage> {
    return unwrap(await listMachines({ client: this.#client, query: { page, size } }));
  }

  /** Every super power on one machine, searched by name or what it does, filtered by status, a page at a time. */
  async superPowers(machineId: string, query: InstalledQuery = {}): Promise<InstalledPage> {
    return unwrap(await listInstalledSuperPowers({ client: this.#client, path: { machine_id: machineId }, query }));
  }

  /** The machine's page on the platform, and a one-minute, one-time ticket for a Claude panel showing it. */
  async open(machineId: string, superPower?: string): Promise<Launch> {
    return unwrap(await openMachine({ client: this.#client, path: { machine_id: machineId }, body: { super_power: superPower ?? null } }));
  }
}
