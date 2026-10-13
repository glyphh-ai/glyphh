import type { Client } from "./gen/client/index.js";
import {
  addSchedule, cancelRun, changeCustomPower, changeSchedule, changeSuperPower, createCustomPower, createSuperPower, deleteCustomFile,
  deleteCustomPower, deleteSchedule, deleteSuperPower, getCustomPower, getRun, getSuperPower, listCustomPowers, listRuns,
  listSchedules, listSuperPowers, myGlyphh, runScheduleNow, superPowerNeeds, readCustomFile, saveTaskFlow, setGrant, setLoop, setTaskSlots, taskSlots, writeCustomFile,
} from "./gen/sdk.gen.js";
import type {
  CustomChange, CustomPage, CustomPower, FileText, Flow, GrantChange, ListRunsData, LoopChoice, NewCustom, NewSuperPower,
  Readiness, RunList, RunView, ScheduleIn, ScheduleView, Slots, SuperPowerChange, SuperPowerPage, SuperPowerView,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type {
  CustomChange, CustomPage, CustomPower, FileText, Flow, GrantChange, LoopChoice, NewCustom, NewSuperPower, RunList,
  Readiness, RunView, ScheduleIn, ScheduleView, Slots, SuperPowerChange, SuperPowerPage, SuperPowerView,
};
export type RunsQuery = NonNullable<ListRunsData["query"]>;
export interface SuperPowerQuery { q?: string; status?: "all" | "working" | "needs_you" | "idle"; machine?: string; page?: number; size?: number }
export interface CustomQuery { kind?: "skill" | "plugin" | "task" | "app"; q?: string; page?: number; size?: number }

/** My super powers: the Super powers page and the editor (configuration, loop, grants, my Glyphh). */
export class SuperPowersApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async list(query: SuperPowerQuery = {}): Promise<SuperPowerPage> { return unwrap(await listSuperPowers({ client: this.#c, query })); }
  async create(body: NewSuperPower): Promise<SuperPowerView> { return unwrap(await createSuperPower({ client: this.#c, body })); }
  /** My Glyphh, the main assistant: it has everything except what I take away. */
  async glyphh(): Promise<SuperPowerView> { return unwrap(await myGlyphh({ client: this.#c })); }
  async get(id: string): Promise<SuperPowerView> { return unwrap(await getSuperPower({ client: this.#c, path: { sp_id: id } })); }
  async change(id: string, body: SuperPowerChange): Promise<SuperPowerView> {
    return unwrap(await changeSuperPower({ client: this.#c, path: { sp_id: id }, body }));
  }
  async delete(id: string): Promise<void> { unwrap(await deleteSuperPower({ client: this.#c, path: { sp_id: id } })); }
  /** Give it a power, a machine or a super power (granted), or take one away. */
  async grant(id: string, body: GrantChange): Promise<SuperPowerView> {
    return unwrap(await setGrant({ client: this.#c, path: { sp_id: id }, body }));
  }
  /** Its loop: claude_code or codex, on my subscription (no model_id) or one of my models; or glyphh, the Glyphh
   *  loop, which always names one of my models. */
  async setLoop(id: string, body: LoopChoice): Promise<SuperPowerView> {
    return unwrap(await setLoop({ client: this.#c, path: { sp_id: id }, body }));
  }
  /** Whether it can run: what it needs that is still missing (a service to connect or give it, a slot to fill). */
  async needs(id: string): Promise<Readiness> { return unwrap(await superPowerNeeds({ client: this.#c, path: { sp_id: id } })); }
}

/** My skills, plugins, tasks and apps: their files, a task's flow and slots. */
export class CustomPowersApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async list(query: CustomQuery = {}): Promise<CustomPage> { return unwrap(await listCustomPowers({ client: this.#c, query })); }
  async create(body: NewCustom): Promise<CustomPower> { return unwrap(await createCustomPower({ client: this.#c, body })); }
  async get(id: string): Promise<CustomPower> { return unwrap(await getCustomPower({ client: this.#c, path: { power_id: id } })); }
  async change(id: string, body: CustomChange): Promise<CustomPower> {
    return unwrap(await changeCustomPower({ client: this.#c, path: { power_id: id }, body }));
  }
  async delete(id: string): Promise<void> { unwrap(await deleteCustomPower({ client: this.#c, path: { power_id: id } })); }
  async readFile(id: string, path: string): Promise<FileText> {
    return unwrap(await readCustomFile({ client: this.#c, path: { power_id: id }, query: { path } }));
  }
  async writeFile(id: string, file: FileText): Promise<FileText> {
    return unwrap(await writeCustomFile({ client: this.#c, path: { power_id: id }, body: file }));
  }
  async deleteFile(id: string, path: string): Promise<void> {
    unwrap(await deleteCustomFile({ client: this.#c, path: { power_id: id }, query: { path } }));
  }
  /** Save a task's flow; a step that needs attention stops the save and is named. */
  async saveFlow(id: string, flow: Flow): Promise<Flow> {
    return unwrap(await saveTaskFlow({ client: this.#c, path: { power_id: id }, body: flow }));
  }
  async slots(id: string): Promise<Slots> { return unwrap(await taskSlots({ client: this.#c, path: { power_id: id } })); }
  async setSlots(id: string, slots: Slots): Promise<Slots> {
    return unwrap(await setTaskSlots({ client: this.#c, path: { power_id: id }, body: slots }));
  }
}

/** Super powers and tasks on the server's clock. */
export class SchedulesApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async list(target?: string): Promise<ScheduleView[]> { return unwrap(await listSchedules({ client: this.#c, query: { target } })); }
  async add(body: ScheduleIn): Promise<ScheduleView> { return unwrap(await addSchedule({ client: this.#c, body })); }
  async change(id: string, body: ScheduleIn): Promise<ScheduleView> {
    return unwrap(await changeSchedule({ client: this.#c, path: { schedule_id: id }, body }));
  }
  async delete(id: string): Promise<void> { unwrap(await deleteSchedule({ client: this.#c, path: { schedule_id: id } })); }
  /** Run it now, on its machine (which must be connected), as the clock would. */
  async runNow(id: string): Promise<RunView> { return unwrap(await runScheduleNow({ client: this.#c, path: { schedule_id: id } })); }
  /** Runs, newest first (mine, or the org's with scope org): by the clock, by hand or by an agent, with what each cost. */
  async runs(query: RunsQuery = {}): Promise<RunList> { return unwrap(await listRuns({ client: this.#c, query })); }
  async run(id: string, scope: "me" | "org" = "me"): Promise<RunView> {
    return unwrap(await getRun({ client: this.#c, path: { run_id: id }, query: { scope } }));
  }
  async cancelRun(id: string): Promise<RunView> { return unwrap(await cancelRun({ client: this.#c, path: { run_id: id } })); }
}
