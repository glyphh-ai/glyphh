"""Each org call once: the generated operation, what success looks like, and what it becomes."""

from glyphh import _org_models as models
from glyphh._calls import Call
from glyphh._gen.api.org import (
    create_invite,
    get_org,
    list_invites,
    list_members,
    remove_member,
    rename_org,
    revoke_invite,
    update_member,
)
from glyphh._gen.models.created_invite import CreatedInvite
from glyphh._gen.models.member import Member
from glyphh._gen.models.org_view import OrgView


def _done(r) -> bool:
    return int(r.status_code) == 204


GET = Call(get_org, lambda r: isinstance(r.parsed, OrgView), models.org_of)
RENAME = Call(rename_org, lambda r: isinstance(r.parsed, OrgView), models.org_of)
MEMBERS = Call(list_members, lambda r: isinstance(r.parsed, list), lambda ms: [models.member_of(m) for m in ms])
UPDATE_MEMBER = Call(update_member, lambda r: isinstance(r.parsed, Member), models.member_of)
REMOVE_MEMBER = Call(remove_member, _done, lambda _: None)
INVITES = Call(list_invites, lambda r: isinstance(r.parsed, list), lambda xs: [models.invite_of(x) for x in xs])
INVITE = Call(create_invite, lambda r: isinstance(r.parsed, CreatedInvite), models.created_of)
REVOKE_INVITE = Call(revoke_invite, _done, lambda _: None)
