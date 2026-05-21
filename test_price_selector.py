"""Tests for price_selector.get_applicable_price_adjustment.

Testing strategy
----------------
The core property under test is that the algorithm selects the
*most-specific* rule regardless of the order in which rules appear in the
input list.  Every assertion is therefore made twice: once with the rule list
in its original order, and once with the list reversed.  If both pass, we
have strong evidence that the refinement pipeline — not accident of input
ordering — produced the correct winner.
"""

from __future__ import annotations

import uuid

import pytest

from pricing_rule import PriceRule
from price_selector import get_applicable_price_adjustment


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

MARKET_ID      = str(uuid.uuid4())
TICKET_TYPE_ID = str(uuid.uuid4())
LOCATION_ID_1  = str(uuid.uuid4())
LOCATION_ID_2  = str(uuid.uuid4())

# Shared base fields for price rules (target="price", specific ticket type)
_BASE: PriceRule = {
    "type":           "increment_percent",
    "target":         "price",
    "ticket_type_id": TICKET_TYPE_ID,
    "value":          0.0,  # overridden in every entry below
}

# Rules ordered from *least-specific* to *most-specific*.
# Every ``value`` is unique so assertions unambiguously identify which rule
# the algorithm chose.  The algorithm should return the same winner whether
# this list is traversed forwards or backwards.
RULES_BY_SPECIFICITY: list[PriceRule] = [
    # ── cost rules (target="cost") ─────────────────────────────────────────
    {
        "type": "set_fixed", "target": "cost", "value": -0.2,
        "all_ticket_types": True, "ticket_type_id": None,
    },
    {
        "type": "set_fixed", "target": "cost", "value": -0.1,
        "ticket_type_id": TICKET_TYPE_ID,
    },
    # ── price rules (target="price"), increasing specificity ───────────────
    # Least specific: applies to every ticket type
    {**_BASE, "value": 0.1, "all_ticket_types": True, "ticket_type_id": None},
    # Specific ticket type, no other constraints
    {**_BASE, "value": 0.2},
    # Specific ticket type + channel
    {**_BASE, "value": 0.3, "channel": 1},
    # Specific ticket type + market
    {**_BASE, "value": 0.4, "market_id": MARKET_ID},
    # Specific ticket type + market + channel
    {**_BASE, "value": 0.5, "market_id": MARKET_ID, "channel": 1},
    # Route match, any ticket type
    {
        **_BASE, "value": 0.6,
        "location_id": LOCATION_ID_1, "end_location_id": LOCATION_ID_2,
        "all_ticket_types": True, "ticket_type_id": None,
    },
    # Route match, specific ticket type
    {
        **_BASE, "value": 0.7,
        "location_id": LOCATION_ID_1, "end_location_id": LOCATION_ID_2,
    },
    # Most specific: route + market + channel + ticket type
    {
        **_BASE, "value": 0.8,
        "location_id": LOCATION_ID_1, "end_location_id": LOCATION_ID_2,
        "market_id": MARKET_ID, "channel": 1,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _price(rules: list[PriceRule], **criteria) -> float:
    """Call the selector for target='price' and return the matched value."""
    return get_applicable_price_adjustment(rules, "price", **criteria)["value"]


def assert_wins(
    expected: float,
    rules: list[PriceRule],
    **criteria,
) -> None:
    """Assert *expected* is chosen, then reverse *rules* and assert again.

    Reversing the list before the second call proves the result is determined
    by rule specificity, not by the rule's position in the input.
    """
    assert _price(rules, **criteria) == expected, \
        f"Forward pass: expected {expected}"
    rules.reverse()
    assert _price(rules, **criteria) == expected, \
        f"Reversed pass: expected {expected}"
    rules.reverse()  # restore original order for subsequent calls


# Criteria with no match in RULES_BY_SPECIFICITY — used as a starting point
# that we gradually make more specific in the tests below.
_BASE_CRITERIA = dict(
    ticket_type_id="UNKNOWN_TICKET",
    market_id="UNKNOWN_MARKET",
    channel=999,
    location_id=None,
    end_location_id=None,
)


# ---------------------------------------------------------------------------
# Specificity hierarchy
# ---------------------------------------------------------------------------

class TestSpecificityHierarchy:
    """The most-specific rule wins, regardless of list order."""

    def setup_method(self):
        self.rules = list(RULES_BY_SPECIFICITY)

    def test_all_ticket_types_fallback(self):
        """When nothing specific matches, the wildcard rule applies."""
        assert_wins(0.1, self.rules, **_BASE_CRITERIA)

    def test_specific_ticket_type(self):
        assert_wins(
            0.2, self.rules,
            **{**_BASE_CRITERIA, "ticket_type_id": TICKET_TYPE_ID},
        )

    def test_channel_refines_ticket_type(self):
        assert_wins(
            0.3, self.rules,
            **{**_BASE_CRITERIA, "ticket_type_id": TICKET_TYPE_ID, "channel": 1},
        )

    def test_market_refines_ticket_type(self):
        assert_wins(
            0.4, self.rules,
            **{**_BASE_CRITERIA, "ticket_type_id": TICKET_TYPE_ID, "market_id": MARKET_ID},
        )

    def test_market_and_channel(self):
        assert_wins(
            0.5, self.rules,
            **{**_BASE_CRITERIA,
               "ticket_type_id": TICKET_TYPE_ID,
               "market_id": MARKET_ID, "channel": 1},
        )

    def test_route_all_ticket_types(self):
        """A route match beats market/channel even without a specific ticket type."""
        assert_wins(
            0.6, self.rules,
            **{**_BASE_CRITERIA,
               "location_id": LOCATION_ID_1, "end_location_id": LOCATION_ID_2},
        )

    def test_route_with_ticket_type(self):
        assert_wins(
            0.7, self.rules,
            **{**_BASE_CRITERIA,
               "ticket_type_id": TICKET_TYPE_ID,
               "location_id": LOCATION_ID_1, "end_location_id": LOCATION_ID_2},
        )

    def test_route_market_channel_most_specific(self):
        """Route + market + channel + ticket type is the most specific combination."""
        assert_wins(
            0.8, self.rules,
            **{**_BASE_CRITERIA,
               "ticket_type_id": TICKET_TYPE_ID,
               "location_id": LOCATION_ID_1, "end_location_id": LOCATION_ID_2,
               "market_id": MARKET_ID, "channel": 1},
        )

    def test_all_values_in_fixture_are_unique(self):
        """Sanity check: unique values ensure test assertions are unambiguous."""
        price_values = [r["value"] for r in RULES_BY_SPECIFICITY]
        assert len(price_values) == len(set(price_values))


# ---------------------------------------------------------------------------
# No-match / fallback behaviour
# ---------------------------------------------------------------------------

class TestNoMatch:
    """When no rule is applicable, a no-op rule is returned."""

    _criteria = dict(
        ticket_type_id=TICKET_TYPE_ID,
        market_id=MARKET_ID,
        channel=1,
        location_id=None,
        end_location_id=None,
    )

    def test_empty_rule_list(self):
        result = get_applicable_price_adjustment([], "price", **self._criteria)
        assert result == {"type": "increment_percent", "target": "price", "value": 0.0}

    def test_no_op_target_field_matches_requested_target(self):
        result = get_applicable_price_adjustment([], "cost", **self._criteria)
        assert result["target"] == "cost"
        assert result["value"] == 0.0

    def test_irrelevant_rules_return_noop(self):
        irrelevant: list[PriceRule] = [
            {"target": "price", "type": "increment_percent", "value": 0.2,
             "ticket_type_id": "NOT_THIS_TICKET"},
            {"target": "price", "type": "increment_percent", "value": 0.3,
             "location_id": "WRONG", "end_location_id": "WRONG", "channel": 1},
        ]
        result = get_applicable_price_adjustment(irrelevant, "price", **self._criteria)
        assert result == {"type": "increment_percent", "target": "price", "value": 0.0}

    def test_zero_increment_percent_excluded(self):
        """A rule with value=0 and type='increment_percent' is a no-op and
        must not be selected — even if it would otherwise be the best match."""
        zero_rule: PriceRule = {
            "type": "increment_percent", "target": "price", "value": 0.0,
            "ticket_type_id": TICKET_TYPE_ID,
        }
        result = get_applicable_price_adjustment([zero_rule], "price", **self._criteria)
        assert result["value"] == 0.0
        # The returned rule should be the synthesised noop, not the stored one
        assert "ticket_type_id" not in result


# ---------------------------------------------------------------------------
# Cost rules
# ---------------------------------------------------------------------------

class TestCostRules:
    """target='cost' selects from cost rules using the same hierarchy."""

    _criteria = dict(
        market_id="UNKNOWN", channel=999,
        location_id=None, end_location_id=None,
    )

    def test_all_ticket_types_cost_fallback(self):
        result = get_applicable_price_adjustment(
            list(RULES_BY_SPECIFICITY), "cost",
            ticket_type_id="UNKNOWN_TICKET", **self._criteria,
        )
        assert result["value"] == -0.2

    def test_specific_ticket_type_cost_rule(self):
        result = get_applicable_price_adjustment(
            list(RULES_BY_SPECIFICITY), "cost",
            ticket_type_id=TICKET_TYPE_ID, **self._criteria,
        )
        assert result["value"] == -0.1


# ---------------------------------------------------------------------------
# Ambiguity / conflict handling
# ---------------------------------------------------------------------------

class TestAmbiguity:
    """Behaviour when two rules are equally specific (conflicting values).

    The refinement pipeline has no tiebreaker: when two rules survive all
    five refinement steps with identical dimension values, the first one in
    the input list is returned.  This is deterministic but arbitrary.

    In the original system, the admin UI was responsible for preventing
    overlapping rules with conflicting values.  These tests document the
    fallback behaviour so that it is explicit rather than accidental.
    """

    _criteria = dict(
        ticket_type_id=TICKET_TYPE_ID,
        market_id=MARKET_ID,
        channel=1,
        location_id=None,
        end_location_id=None,
    )

    def _make_rule(self, value: float) -> PriceRule:
        return {
            "target": "price", "type": "set_fixed", "value": value,
            "ticket_type_id": TICKET_TYPE_ID, "market_id": MARKET_ID, "channel": 1,
        }

    def test_first_in_list_wins_on_tie(self):
        rule_a = self._make_rule(10.0)
        rule_b = self._make_rule(20.0)
        result = get_applicable_price_adjustment(
            [rule_a, rule_b], "price", **self._criteria,
        )
        assert result["value"] == 10.0

    def test_order_determines_winner_on_tie(self):
        """Reversing the input changes the winner — confirming the tie is real."""
        rule_a = self._make_rule(10.0)
        rule_b = self._make_rule(20.0)
        result = get_applicable_price_adjustment(
            [rule_b, rule_a], "price", **self._criteria,
        )
        assert result["value"] == 20.0
