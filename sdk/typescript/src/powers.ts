import type { Client } from "./gen/client/index.js";
import {
  addBrowser, addFolder, addModel, checkConnection, checkModelKey, connect, deleteBrowser, deleteModel, disconnect,
  listBrowsers, listCatalogModels, listConnections, listFolders, listLoops, listModels, listProviders, listServices, listTools,
  reconnect, removeFolder, replaceModelKey, setTools, whatICanAdd,
} from "./gen/sdk.gen.js";
import type {
  CanAdd, CatalogPage, ConnectionView, ConnectLink, LoopState, MachineLoops, ModelView, NewBrowser, NewFolder, NewModel,
  Place, ProviderView, ServicePage, ToolChange, ToolPage,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type {
  CanAdd, CatalogPage, ConnectionView, ConnectLink, LoopState, MachineLoops, ModelView, NewBrowser, NewFolder, NewModel,
  Place, ProviderView, ServicePage, ToolChange, ToolPage,
};

export interface CatalogQuery { provider?: string; q?: string; page?: number; size?: number }

/** My powers: the model catalog, my models on my own keys, connections through Pipedream and their tools'
 *  permissions, folders and browser profiles, and what my teams let me add. */
export class PowersApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** The catalog's providers, each with its model count and, when a limit leaves all out, why. */
  async providers(q = ""): Promise<ProviderView[]> {
    return unwrap(await listProviders({ client: this.#client, query: { q } }));
  }

  /** The catalog's models (one provider's, or all), searched, each saying whether I may add it. */
  async catalogModels(query: CatalogQuery = {}): Promise<CatalogPage> {
    return unwrap(await listCatalogModels({ client: this.#client, query }));
  }

  /** Each of my machines' loops: Claude Code and Codex as it says of them, and the Glyphh loop (ready wherever I
   *  have a model that is on). */
  async loops(): Promise<MachineLoops[]> {
    return unwrap(await listLoops({ client: this.#client }));
  }

  async models(): Promise<ModelView[]> {
    return unwrap(await listModels({ client: this.#client }));
  }

  /** Add a model on my own key: tried with its provider first; a refused key saves nothing. */
  async addModel(model: NewModel): Promise<ModelView> {
    return unwrap(await addModel({ client: this.#client, body: model }));
  }

  async replaceKey(powerId: string, apiKey: string): Promise<ModelView> {
    return unwrap(await replaceModelKey({ client: this.#client, path: { power_id: powerId }, body: { api_key: apiKey } }));
  }

  async checkKey(powerId: string): Promise<ModelView> {
    return unwrap(await checkModelKey({ client: this.#client, path: { power_id: powerId } }));
  }

  async deleteModel(powerId: string): Promise<void> {
    unwrap(await deleteModel({ client: this.#client, path: { power_id: powerId } }));
  }

  /** Services to connect (Pipedream's apps), by cursor. */
  async services(q = "", after?: string, limit = 25): Promise<ServicePage> {
    return unwrap(await listServices({ client: this.#client, query: { q, after, limit } }));
  }

  async connections(): Promise<ConnectionView[]> {
    return unwrap(await listConnections({ client: this.#client }));
  }

  /** Start connecting my account at a service: open the answer's `url`, then `checkConnection`. */
  async connect(service: string): Promise<ConnectLink> {
    return unwrap(await connect({ client: this.#client, body: { service } }));
  }

  async reconnect(powerId: string): Promise<ConnectLink> {
    return unwrap(await reconnect({ client: this.#client, path: { power_id: powerId } }));
  }

  async checkConnection(powerId: string): Promise<ConnectionView> {
    return unwrap(await checkConnection({ client: this.#client, path: { power_id: powerId } }));
  }

  async disconnect(powerId: string): Promise<void> {
    unwrap(await disconnect({ client: this.#client, path: { power_id: powerId } }));
  }

  /** A connection's tools by risk, with my permission and any super power's own. */
  async tools(powerId: string, query: { q?: string; page?: number; size?: number } = {}): Promise<ToolPage> {
    return unwrap(await listTools({ client: this.#client, path: { power_id: powerId }, query }));
  }

  async setTools(powerId: string, changes: ToolChange[]): Promise<void> {
    unwrap(await setTools({ client: this.#client, path: { power_id: powerId }, body: { changes } }));
  }

  async folders(): Promise<Place[]> {
    return unwrap(await listFolders({ client: this.#client }));
  }

  async addFolder(folder: NewFolder): Promise<Place> {
    return unwrap(await addFolder({ client: this.#client, body: folder }));
  }

  async removeFolder(powerId: string): Promise<void> {
    unwrap(await removeFolder({ client: this.#client, path: { power_id: powerId } }));
  }

  async browsers(): Promise<Place[]> {
    return unwrap(await listBrowsers({ client: this.#client }));
  }

  async addBrowser(browser: NewBrowser): Promise<Place> {
    return unwrap(await addBrowser({ client: this.#client, body: browser }));
  }

  async deleteBrowser(powerId: string): Promise<void> {
    unwrap(await deleteBrowser({ client: this.#client, path: { power_id: powerId } }));
  }

  /** What my teams let me add, inside my org's list. */
  async canAdd(): Promise<CanAdd> {
    return unwrap(await whatICanAdd({ client: this.#client }));
  }
}
