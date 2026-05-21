"""Domain types for price and cost adjustment rules.

A PriceRule is a flat record stored in the database.  Optional dimensions
(market, channel, route, ticket type) are represented as ``None`` meaning
"applies to all values of this dimension".  ``all_ticket_types`` is a
separate boolean flag because it can coexist with a specific
``ticket_type_id`` in legacy data.
"""

from __future__ import annotations

from typing import Literal, Optional, TypedDict


RuleTarget = Literal["price", "cost"]
RuleType = Literal["increment_percent", "set_fixed"]


class _RequiredFields(TypedDict):
    target: RuleTarget
    type:   RuleType
    value:  float


class PriceRule(_RequiredFields, total=False):
    """A single price or cost adjustment rule.

    Required fields
    ---------------
    target : "price" | "cost"
        Whether this rule adjusts the customer-facing price or the internal
        cost basis.
    type : "increment_percent" | "set_fixed"
        How ``value`` is applied.  ``increment_percent`` treats ``value`` as
        a fractional multiplier (e.g. 0.1 → +10 %).  ``set_fixed`` replaces
        the base price entirely.
    value : float
        The adjustment magnitude.  An ``increment_percent`` rule with
        ``value == 0`` is considered a no-op and is excluded from selection.

    Optional fields (``None`` means "applies to all")
    --------------------------------------------------
    ticket_type_id : str | None
    all_ticket_types : bool
        When ``True``, the rule applies regardless of ticket type.  Takes
        precedence over ``ticket_type_id`` in the initial eligibility check.
    channel : int | None
    market_id : str | None
    location_id : str | None
    end_location_id : str | None
    """

    ticket_type_id:  Optional[str]
    all_ticket_types: bool
    channel:          Optional[int]
    market_id:        Optional[str]
    location_id:      Optional[str]
    end_location_id:  Optional[str]
