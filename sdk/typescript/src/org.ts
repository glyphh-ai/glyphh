import type { Client } from "./gen/client/index.js";
import {
  createInvite, getOrg, listInvites, listMembers, removeMember, renameOrg, revokeInvite, updateMember,
} from "./gen/sdk.gen.js";
import type { CreatedInvite, InviteView, Member, MemberChange, OrgView } from "./gen/types.gen.js";
import { unwrap } from "./errors.js";

export type { CreatedInvite, InviteView, Member, MemberChange, OrgView };
export type MemberRole = "org_admin" | "user";

/** My org: its plan and seats, its members and its invites. Changes are for org admins. */
export class OrgApi {
  readonly #client: Client;

  constructor(client: Client) {
    this.#client = client;
  }

  /** The org's name, plan, and how many seats are taken. */
  async get(): Promise<OrgView> {
    return unwrap(await getOrg({ client: this.#client }));
  }

  async rename(name: string): Promise<OrgView> {
    return unwrap(await renameOrg({ client: this.#client, body: { name } }));
  }

  async listMembers(): Promise<Member[]> {
    return unwrap(await listMembers({ client: this.#client }));
  }

  /** Change a member's role, or disable or re-enable them. Never your own. */
  async updateMember(memberId: string, change: MemberChange): Promise<Member> {
    return unwrap(await updateMember({ client: this.#client, path: { member_id: memberId }, body: change }));
  }

  async removeMember(memberId: string): Promise<void> {
    unwrap(await removeMember({ client: this.#client, path: { member_id: memberId } }));
  }

  /** The open invites. */
  async listInvites(): Promise<InviteView[]> {
    return unwrap(await listInvites({ client: this.#client }));
  }

  /** Invite someone by email. The answer's link is shown once: send it to them. */
  async invite(email: string, role: MemberRole = "user"): Promise<CreatedInvite> {
    return unwrap(await createInvite({ client: this.#client, body: { email, role } }));
  }

  async revokeInvite(inviteId: string): Promise<void> {
    unwrap(await revokeInvite({ client: this.#client, path: { invite_id: inviteId } }));
  }
}
