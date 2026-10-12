"""Publishing and the Marketplace, as calls: my listings, the version on its way and its pictures, submitting,
the review queues and decisions; the Marketplace's shelves, search, a listing's page, adding and updating my copy.
Answers are the server's JSON as plain dicts."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.listings import (
    change_listing,
    change_listing_version,
    comment_on_listing,
    create_listing,
    decide_review,
    get_listing,
    listing_comments,
    my_listings,
    order_listing_screenshots,
    remove_listing_screenshot,
    review_queue,
    submit_listing,
    unpublish_listing,
    withdraw_listing,
)
from glyphh._gen.api.marketplace import (
    add_from_marketplace,
    browse_marketplace,
    marketplace_home,
    marketplace_listing,
    update_from_marketplace,
)
from glyphh._gen.models import (
    BrowseMarketplaceKindType0,
    ListingChange,
    MarketplaceHomeKindType0,
    NewComment,
    NewListing,
    Order,
    ReviewDecision,
    ReviewQueueStep,
    VersionChange,
)
from glyphh._gen.types import UNSET
from glyphh._upload import ADD_SCREENSHOT, SET_ICON

Spec = tuple[Any, dict[str, Any]]


def _l(listing_id: str) -> dict[str, Any]:
    return {"listing_id": UUID(listing_id)}


def _picture(listing_id: str, data: bytes, content_type: str = "image/png", name: str = "picture") -> dict[str, Any]:
    return {"listing_id": listing_id, "data": data, "content_type": content_type, "name": name}


LISTING_SPECS: dict[str, Callable[..., Spec]] = {
    "mine": lambda: (_call(my_listings), {}),
    "create": lambda **body: (_call(create_listing), {"body": NewListing.from_dict(body)}),
    "get": lambda listing_id: (_call(get_listing), _l(listing_id)),
    "change": lambda listing_id, **body: (
        _call(change_listing),
        {**_l(listing_id), "body": ListingChange.from_dict(body)},
    ),
    "change_version": lambda listing_id, **body: (
        _call(change_listing_version),
        {**_l(listing_id), "body": VersionChange.from_dict(body)},
    ),
    "set_icon": lambda listing_id, data, **kw: (_call(SET_ICON), _picture(listing_id, data, **kw)),
    "add_screenshot": lambda listing_id, data, **kw: (_call(ADD_SCREENSHOT), _picture(listing_id, data, **kw)),
    "order_screenshots": lambda listing_id, screenshots: (
        _call(order_listing_screenshots),
        {**_l(listing_id), "body": Order(screenshots=[UUID(s) for s in screenshots])},
    ),
    "remove_screenshot": lambda listing_id, shot_id: (
        _call(remove_listing_screenshot),
        {**_l(listing_id), "shot_id": UUID(shot_id)},
    ),
    "submit": lambda listing_id: (_call(submit_listing), _l(listing_id)),
    "withdraw": lambda listing_id: (_call(withdraw_listing), _l(listing_id)),
    "unpublish": lambda listing_id: (_call(unpublish_listing), _l(listing_id)),
    "comments": lambda listing_id: (_call(listing_comments), _l(listing_id)),
    "comment": lambda listing_id, body: (_call(comment_on_listing), {**_l(listing_id), "body": NewComment(body=body)}),
    "queue": lambda step="org": (_call(review_queue), {"step": ReviewQueueStep(step)}),
    "decide": lambda version_id, decision, notes="": (
        _call(decide_review),
        {
            "listing_version_id": UUID(version_id),
            "body": ReviewDecision.from_dict({"decision": decision, "notes": notes}),
        },
    ),
}

MARKETPLACE_SPECS: dict[str, Callable[..., Spec]] = {
    "home": lambda kind=None: (_call(marketplace_home), {"kind": MarketplaceHomeKindType0(kind) if kind else UNSET}),
    "browse": lambda kind=None, type=None, category=None, q="", page=1, size=24: (
        _call(browse_marketplace),
        {
            "kind": BrowseMarketplaceKindType0(kind) if kind else UNSET,
            "type_": type or UNSET,
            "category": category or UNSET,
            "q": q,
            "page": page,
            "size": size,
        },
    ),
    "get": lambda listing_id: (_call(marketplace_listing), _l(listing_id)),
    "add": lambda listing_id: (_call(add_from_marketplace), _l(listing_id)),
    "update": lambda power_id: (_call(update_from_marketplace), {"power_id": UUID(power_id)}),
}
