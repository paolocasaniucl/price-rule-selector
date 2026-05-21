# price-rule-selector

A Python module for selecting the most-specific applicable pricing rule from
a set of multi-dimensional rules.

## Background

Adapted from a pricing-rule selection component originally developed within a
commercial ticketing platform (TypeScript).  The Python version was rewritten
independently to demonstrate the rule-selection and testing approach without
exposing proprietary business logic or infrastructure.

## Problem

A product's price can vary across several independent dimensions:

- **Route** — departure and arrival location pair
- **Market** — regional sales market
- **Channel** — sales channel (direct web, API, travel-agent portal, etc.)
- **Ticket type** — adult, child, senior, etc.

Rules are stored flat, with `None` on a dimension meaning "applies to all
values of that dimension."  When pricing a specific booking, exactly one rule
should apply — the most-specific match available.

Explicit priority scores and nested conditionals become fragile as the number
of dimensions grows and are hard to debug when a price behaves unexpectedly.

## Approach

The selector runs a **specificity refinement pipeline**.  For each dimension
in priority order:

    route (location pair) → market → channel → ticket type

it asks: does any surviving rule carry an exact match for the current booking
value?  If so, only those rules pass through; otherwise rules that declare no
preference (`None`) are kept.  The pipeline converges on the single
most-specific applicable rule without a lookup table or scoring function.

Adding a new pricing dimension requires one extra `_refine` call.

## Testing

The test suite pre-builds a rule list with a unique `value` per rule, ordered
from least to most specific.  Each assertion is then made **twice**: once in
the original order and once with the list reversed.  If the same rule wins
both times, the result is determined by rule specificity alone — not by
accident of input ordering.

The suite covers:

- Specificity hierarchy (9 cases)
- No-match / noop fallback (4 cases)
- Cost rules using the same pipeline (2 cases)
- Ambiguous / equally-specific rules (2 cases)

## Usage

```python
from price_selector import get_applicable_price_adjustment

rules = [
    {
        "target": "price",
        "type":   "increment_percent",
        "value":  0.1,
        "all_ticket_types": True,
    },
    {
        "target":         "price",
        "type":           "set_fixed",
        "value":          25.00,
        "market_id":      "uk-market",
        "ticket_type_id": "adult",
    },
]

rule = get_applicable_price_adjustment(
    rules,
    "price",
    ticket_type_id="adult",
    market_id="uk-market",
    channel=1,
    location_id=None,
    end_location_id=None,
)
# → {"target": "price", "type": "set_fixed", "value": 25.0, ...}
```

## Running the tests

```
python3 -m pytest test_price_selector.py -v
```
