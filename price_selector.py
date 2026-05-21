"""Price rule selector: choose the most-specific applicable rule.

Design rationale
----------------
Each pricing rule carries optional dimensions — ticket type, channel, market,
and route (a location pair).  Rather than explicit priority scores, the
selector applies a *specificity refinement* pipeline.  For each dimension
(route → market → channel → ticket type), it asks: does any surviving rule
carry an exact match for the current value?  If so, only those rules survive
the step; otherwise rules that declare no preference for that dimension
(stored as ``None``) are kept.  This sequential narrowing converges on the
single most-specific applicable rule without a lookup table or scoring
function.  Adding a new pricing dimension requires one extra ``_refine``
call.
"""

from __future__ import annotations

from typing import Optional, Sequence

from pricing_rule import PriceRule, RuleTarget


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _refine(
    rules: list[PriceRule],
    key: str,
    value: object,
) -> list[PriceRule]:
    """Keep only the most-specific rules for *key*.

    If any rule carries an exact match for *value*, return those rules
    exclusively.  Otherwise fall back to rules where *key* is ``None``
    (meaning "applies to all values of this dimension").
    """
    specific = [r for r in rules if r.get(key) == value]
    if specific:
        return specific
    return [r for r in rules if r.get(key) is None]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_applicable_price_adjustment(
    rules: Sequence[PriceRule],
    target: RuleTarget,
    *,
    ticket_type_id: str,
    market_id: str,
    channel: int,
    location_id: Optional[str],
    end_location_id: Optional[str],
) -> PriceRule:
    """Return the single most-specific rule matching *target* and all criteria.

    Rules are refined along the hierarchy:

        route (location pair) → market → channel → ticket type

    This order reflects the pricing UI in the admin portal, where route-level
    pricing takes the highest precedence.

    If no rule matches, a no-op rule (``value=0``, ``type="increment_percent"``)
    is returned so callers can apply it unconditionally.

    Parameters
    ----------
    rules:
        All price-adjustment rules for the product.  May be in any order.
    target:
        ``"price"`` to select customer-facing adjustments; ``"cost"`` to
        select internal cost adjustments.
    ticket_type_id:
        The ticket type being priced (e.g. adult, child).
    market_id:
        The sales market (e.g. a UUID representing a regional market).
    channel:
        The sales channel integer (e.g. 1 = direct web, 2 = API).
    location_id:
        Departure location, or ``None`` when searching without a route.
    end_location_id:
        Arrival location, or ``None`` when searching without a route.
    """
    noop: PriceRule = {"type": "increment_percent", "target": target, "value": 0.0}

    # Step 1 — initial eligibility filter: correct target, applicable ticket
    # type, and non-trivial value (a zero increment_percent is a no-op rule
    # that should never override a real one).
    applicable: list[PriceRule] = [
        r for r in rules
        if r["target"] == target
        and (
            r.get("ticket_type_id") == ticket_type_id
            or r.get("all_ticket_types")
        )
        and (r["type"] != "increment_percent" or r["value"] != 0)
    ]

    # Step 2 — specificity refinement, dimension by dimension.
    # Order matters: each step narrows the set before the next one runs.
    applicable = _refine(applicable, "location_id",     location_id)
    applicable = _refine(applicable, "end_location_id", end_location_id)
    applicable = _refine(applicable, "market_id",       market_id)
    applicable = _refine(applicable, "channel",         channel)
    applicable = _refine(applicable, "ticket_type_id",  ticket_type_id)

    return applicable[0] if applicable else noop
