import type { Client } from "./gen/client/index.js";
import {
  addLimitEntries, addTeamMembers, changeTeam, createTeam, deleteTeam, exportAuditLog, getLimitImpact, getLimits, getMemberKeys,
  getMemberTeams, getTeam, inviteMany, listApiKeyMakers, listAuditLog, listMyApiKeys, listOrgApiKeys, listPeople, listTeams,
  makeApiKey, removeLimitEntries, removeTeamMember, revokeApiKey, setLimit, setMemberKeys, setMemberTeams,
} from "./gen/sdk.gen.js";
import type {
  AuditPage, ExportAuditLogData, GetLimitsData, Impact, InviteMany, InviteResult, KeysPage, KeyView, LimitView, ListAuditLogData,
  ListPeopleData, MadeKey, Maker, MemberKeys, MemberTeams, NewKey, PeoplePage, TeamChange, TeamView,
} from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type {
  AuditPage, Impact, InviteMany, InviteResult, KeysPage, KeyView, LimitView, MadeKey, Maker, MemberKeys, MemberTeams, NewKey,
  PeoplePage, TeamChange, TeamView,
};
export type PeopleQuery = NonNullable<ListPeopleData["query"]>;
export type AuditQuery = NonNullable<ListAuditLogData["query"]>;
export type AuditFilters = NonNullable<ExportAuditLogData["query"]>;
export type LimitKind = GetLimitsData["path"]["kind"];
export type LimitQuery = NonNullable<GetLimitsData["query"]>;

/** Org admin: people and open invites, teams, the org's and teams' limits, and the audit log. */
export class OrgAdminApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async people(query: PeopleQuery = {}): Promise<PeoplePage> { return unwrap(await listPeople({ client: this.#c, query })); }
  /** Each link to send, and each email that couldn't be invited with why; nothing is sent past the seats. */
  async inviteMany(body: InviteMany): Promise<InviteResult> { return unwrap(await inviteMany({ client: this.#c, body })); }
  async teams(): Promise<TeamView[]> { return unwrap(await listTeams({ client: this.#c })); }
  async team(id: string): Promise<TeamView> { return unwrap(await getTeam({ client: this.#c, path: { team_id: id } })); }
  async createTeam(name: string): Promise<TeamView> { return unwrap(await createTeam({ client: this.#c, body: { name } })); }
  async changeTeam(id: string, body: TeamChange): Promise<TeamView> {
    return unwrap(await changeTeam({ client: this.#c, path: { team_id: id }, body }));
  }
  async deleteTeam(id: string): Promise<void> { unwrap(await deleteTeam({ client: this.#c, path: { team_id: id } })); }
  async addToTeam(id: string, userIds: string[]): Promise<TeamView> {
    return unwrap(await addTeamMembers({ client: this.#c, path: { team_id: id }, body: { user_ids: userIds } }));
  }
  async removeFromTeam(id: string, userId: string): Promise<TeamView> {
    return unwrap(await removeTeamMember({ client: this.#c, path: { team_id: id, user_id: userId } }));
  }
  async memberTeams(userId: string): Promise<MemberTeams> {
    return unwrap(await getMemberTeams({ client: this.#c, path: { user_id: userId } }));
  }
  async setMemberTeams(userId: string, teamIds: string[]): Promise<MemberTeams> {
    return unwrap(await setMemberTeams({ client: this.#c, path: { user_id: userId }, body: { team_ids: teamIds } }));
  }
  /** The org's list (or a team's, with `team`), how many use each entry, and who it leaves out. */
  async limits(kind: LimitKind, query: LimitQuery = {}): Promise<LimitView> {
    return unwrap(await getLimits({ client: this.#c, path: { kind }, query }));
  }
  /** What turning the limit on would stop now. */
  async limitImpact(kind: LimitKind, team?: string): Promise<Impact> {
    return unwrap(await getLimitImpact({ client: this.#c, path: { kind }, query: { team } }));
  }
  async setLimit(kind: LimitKind, on: boolean, team?: string): Promise<LimitView> {
    return unwrap(await setLimit({ client: this.#c, path: { kind }, query: { team }, body: { on } }));
  }
  async addLimitEntries(kind: LimitKind, ids: string[], team?: string): Promise<LimitView> {
    return unwrap(await addLimitEntries({ client: this.#c, path: { kind }, query: { team }, body: { ids } }));
  }
  async removeLimitEntries(kind: LimitKind, ids: string[], team?: string): Promise<LimitView> {
    return unwrap(await removeLimitEntries({ client: this.#c, path: { kind }, query: { team }, body: { ids } }));
  }
  /** The audit log of admin actions, newest first, a page at a time. */
  async auditLog(query: AuditQuery = {}): Promise<AuditPage> { return unwrap(await listAuditLog({ client: this.#c, query })); }
  /** The same entries as CSV. */
  async exportAuditLog(query: AuditFilters = {}): Promise<string> {
    return unwrap(await exportAuditLog({ client: this.#c, query, parseAs: "text" })) as string;
  }
}

/** API keys: mine, made in the org I am in and shown once; for org admins, every key in the org and the member-keys switch. */
export class ApiKeysApi {
  readonly #c: Client;
  constructor(client: Client) { this.#c = client; }
  async mine(query: { page?: number; size?: number } = {}): Promise<KeysPage> { return unwrap(await listMyApiKeys({ client: this.#c, query })); }
  /** The whole key is in the answer's `secret`, this once; only its prefix is shown after. */
  async make(body: NewKey): Promise<MadeKey> { return unwrap(await makeApiKey({ client: this.#c, body })); }
  async revoke(id: string): Promise<KeyView> { return unwrap(await revokeApiKey({ client: this.#c, path: { key_id: id } })); }
  async org(query: { owner?: string; page?: number; size?: number } = {}): Promise<KeysPage> {
    return unwrap(await listOrgApiKeys({ client: this.#c, query }));
  }
  async makers(q = ""): Promise<Maker[]> { return unwrap(await listApiKeyMakers({ client: this.#c, query: { q } })); }
  async memberKeys(): Promise<MemberKeys> { return unwrap(await getMemberKeys({ client: this.#c })); }
  async setMemberKeys(on: boolean): Promise<MemberKeys> { return unwrap(await setMemberKeys({ client: this.#c, body: { on } })); }
}
