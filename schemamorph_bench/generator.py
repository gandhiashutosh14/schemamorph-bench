"""
Synthetic source table and the explicit transformations, each with ground truth.

Ground truth for a transformation is, per target column: which source column
it derives from (or None if it is new / the source was dropped), how the value
was converted, and whether the conversion is lossy. It is metadata about how
the target was *made*; the mappers never see it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

Row = Dict[str, Any]

BASE_SCHEMA: List[Tuple[str, str]] = [           # (column, type) — types: int | float | str
    ("order_id", "int"),
    ("customer_email", "str"),
    ("order_total_cents", "int"),
    ("shipping_cost_cents", "int"),
    ("currency", "str"),
    ("placed_at", "str"),                         # ISO date
    ("status", "str"),
    ("items", "int"),
    ("region", "str"),
]
STATUSES = ("placed", "paid", "shipped", "returned")
REGIONS = ("north", "south", "east", "west")


def generate_base(n: int, seed: int) -> List[Row]:
    rng = random.Random(seed)
    rows: List[Row] = []
    for i in range(n):
        rows.append({
            "order_id": 1000 + i,
            "customer_email": f"user{rng.randint(1, 400)}@example.com",
            "order_total_cents": rng.randint(500, 250000),
            "shipping_cost_cents": rng.choice([0, 499, 999, 1499, 2999]),
            "currency": rng.choice(["USD", "EUR", "GBP"]),
            "placed_at": f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "status": rng.choice(STATUSES),
            "items": rng.randint(1, 12),
            "region": rng.choice(REGIONS),
        })
    return rows


@dataclass(frozen=True)
class Derivation:
    source: Optional[str]                 # None: no source column (dropped or brand new)
    conversion: str = "identity"          # identity | to_str | cents_to_units | round_units | value_swap
    lossy: bool = False


@dataclass
class Case:
    name: str
    description: str
    target_schema: List[Tuple[str, str]]
    target_rows: List[Row]
    truth: Dict[str, Derivation]          # target column -> how it was derived
    dropped: List[str] = field(default_factory=list)   # source columns with no target
    round_trip_defined: bool = True       # False when some conversion is lossy


def _schema_of(rows: List[Row], types: Dict[str, str]) -> List[Tuple[str, str]]:
    return [(c, types[c]) for c in rows[0].keys()] if rows else []


def _identity_truth(columns: List[str]) -> Dict[str, Derivation]:
    return {c: Derivation(c) for c in columns}


# ---------------------------------------------------------------------------
def case_rename(base: List[Row]) -> Case:
    mapping = {"customer_email": "email_address", "placed_at": "order_date", "items": "item_count"}
    rows = [{mapping.get(k, k): v for k, v in r.items()} for r in base]
    types = {mapping.get(c, c): t for c, t in BASE_SCHEMA}
    truth = {mapping.get(c, c): Derivation(c) for c, _ in BASE_SCHEMA}
    return Case("rename", "three columns renamed, values unchanged", _schema_of(rows, types), rows, truth)


def case_drop(base: List[Row]) -> Case:
    rows = [{k: v for k, v in r.items() if k != "region"} for r in base]
    types = {c: t for c, t in BASE_SCHEMA if c != "region"}
    truth = _identity_truth([c for c, _ in BASE_SCHEMA if c != "region"])
    return Case("drop_column", "the region column no longer exists in the source", _schema_of(rows, types), rows, truth, dropped=["region"])


def case_type_change(base: List[Row]) -> Case:
    rows = [{**r, "items": str(r["items"])} for r in base]
    types = {c: ("str" if c == "items" else t) for c, t in BASE_SCHEMA}
    truth = _identity_truth([c for c, _ in BASE_SCHEMA])
    truth["items"] = Derivation("items", "to_str")
    return Case("type_change", "items is now delivered as a string", _schema_of(rows, types), rows, truth)


def case_unit_change(base: List[Row]) -> Case:
    rows = []
    for r in base:
        row = {k: v for k, v in r.items() if k not in ("order_total_cents", "shipping_cost_cents")}
        row["order_total"] = round(r["order_total_cents"] / 100, 2)
        row["shipping_cost"] = round(r["shipping_cost_cents"] / 100, 2)
        rows.append(row)
    types = {c: t for c, t in BASE_SCHEMA if c not in ("order_total_cents", "shipping_cost_cents")}
    types.update({"order_total": "float", "shipping_cost": "float"})
    truth = _identity_truth([c for c in types if c not in ("order_total", "shipping_cost")])
    truth["order_total"] = Derivation("order_total_cents", "cents_to_units")
    truth["shipping_cost"] = Derivation("shipping_cost_cents", "cents_to_units")
    return Case("unit_change", "money columns renamed and converted from cents to units (exact at two decimals)",
                _schema_of(rows, types), rows, truth)


def case_lossy_rounding(base: List[Row]) -> Case:
    rows = []
    for r in base:
        row = {k: v for k, v in r.items() if k != "order_total_cents"}
        row["order_total_rounded"] = round(r["order_total_cents"] / 100)
        rows.append(row)
    types = {c: t for c, t in BASE_SCHEMA if c != "order_total_cents"}
    types["order_total_rounded"] = "int"
    truth = _identity_truth([c for c in types if c != "order_total_rounded"])
    truth["order_total_rounded"] = Derivation("order_total_cents", "round_units", lossy=True)
    return Case("lossy_rounding", "order total rounded to whole units: the cents are gone and cannot be reconstructed",
                _schema_of(rows, types), rows, truth, round_trip_defined=False)


def case_reorder(base: List[Row]) -> Case:
    order = [c for c, _ in reversed(BASE_SCHEMA)]
    rows = [{c: r[c] for c in order} for r in base]
    types = dict(BASE_SCHEMA)
    return Case("reorder", "columns delivered in a different order, names and values unchanged",
                _schema_of(rows, types), rows, _identity_truth(order))


def case_swap(base: List[Row]) -> Case:
    """The counterexample: order_total_cents and shipping_cost_cents keep their names but carry each other's values."""
    rows = [{**r, "order_total_cents": r["shipping_cost_cents"], "shipping_cost_cents": r["order_total_cents"]} for r in base]
    truth = _identity_truth([c for c, _ in BASE_SCHEMA])
    truth["order_total_cents"] = Derivation("shipping_cost_cents", "value_swap")
    truth["shipping_cost_cents"] = Derivation("order_total_cents", "value_swap")
    return Case("swap", "two compatible money columns exchanged their values but kept their names: every name-based "
                "mapping is structurally valid and round-trips, and puts the wrong meaning in both columns",
                _schema_of(rows, dict(BASE_SCHEMA)), rows, truth)


def case_compound(base: List[Row]) -> Case:
    rows = []
    for r in base:
        row = {("email_address" if k == "customer_email" else k): v for k, v in r.items() if k != "region"}
        row["items"] = str(row["items"])
        rows.append(row)
    types = {("email_address" if c == "customer_email" else c): ("str" if c == "items" else t) for c, t in BASE_SCHEMA if c != "region"}
    truth = {c: Derivation("customer_email" if c == "email_address" else c) for c in types}
    truth["items"] = Derivation("items", "to_str")
    return Case("compound", "a rename, a drop and a type change at once", _schema_of(rows, types), rows, truth, dropped=["region"])


CASES: List[Tuple[str, Callable[[List[Row]], Case]]] = [
    ("rename", case_rename), ("drop_column", case_drop), ("type_change", case_type_change),
    ("unit_change", case_unit_change), ("lossy_rounding", case_lossy_rounding), ("reorder", case_reorder),
    ("swap", case_swap), ("compound", case_compound),
]


def build_cases(n_rows: int, seed: int) -> Tuple[List[Row], List[Case]]:
    base = generate_base(n_rows, seed)
    return base, [make(base) for _, make in CASES]
