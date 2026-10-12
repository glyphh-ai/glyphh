import type { Client } from "./gen/client/index.js";
import { answerNeedsYou, changeThread, deleteThread, getThread, listNeedsYou, listThreads } from "./gen/sdk.gen.js";
import type {
  Answered, CrewCount, CrewFace, Question, QuestionPage, ThreadChange, ThreadDetail, ThreadMachine, ThreadPage, ThreadRow,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type { Answered, CrewCount, CrewFace, Question, QuestionPage, ThreadChange, ThreadDetail, ThreadMachine, ThreadPage, ThreadRow };

export interface ThreadQuery { q?: string; superPower?: string; archived?: boolean; page?: number; size?: number }

/** A machine's threads, by their record: their messages are on the machine, never here. */
export class ThreadsApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or not. */
  async list(machineId: string, query: ThreadQuery = {}): Promise<ThreadPage> {
    const { superPower, ...rest } = query;
    const q = superPower ? { ...rest, super_power: superPower } : rest;
    return unwrap(await listThreads({ client: this.#client, path: { machine_id: machineId }, query: q }));
  }

  /** One thread's record, its machine (online or not) and its open questions. */
  async get(threadId: string): Promise<ThreadDetail> {
    return unwrap(await getThread({ client: this.#client, path: { thread_id: threadId } }));
  }

  /** Rename it, pin it to the top of Recents or not, archive it or bring it back. */
  async change(threadId: string, change: ThreadChange): Promise<ThreadRow> {
    return unwrap(await changeThread({ client: this.#client, path: { thread_id: threadId }, body: change }));
  }

  /** Delete an archived thread for good. */
  async delete(threadId: string): Promise<void> {
    unwrap(await deleteThread({ client: this.#client, path: { thread_id: threadId } }));
  }
}

/** Needs you: every question my super powers are waiting on, and answering one. */
export class NeedsYouApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** Every open question across my machines, newest first, a page at a time. */
  async list(page = 1, size = 25): Promise<QuestionPage> {
    return unwrap(await listNeedsYou({ client: this.#client, query: { page, size } }));
  }

  /** Allow or deny, once: answered anywhere, it is closed everywhere. */
  async answer(questionId: string, allow: boolean): Promise<Answered> {
    return unwrap(await answerNeedsYou({ client: this.#client, path: { question_id: questionId }, body: { allow } }));
  }
}
