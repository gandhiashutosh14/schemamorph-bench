"""
Two deterministic mappers. Neither is clever; that is the point of a baseline.

A mapping is {target column -> source column or None}. A mapper sees the base
schema and the target schema (names and types) and a sample of target rows.
It never sees the ground truth.

  StaticMapper       the mapping written for the base schema, applied blindly: every base column
                     maps to the target column of the same name; anything else is unmapped.
  NameBaselineMapper normalised-name matching (case, underscores, a short synonym list, a few
                     unit suffixes) with a type-compatibility check.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

Schema = List[Tuple[str, str]]
Mapping = Dict[str, Optional[str]]

SYNONYMS = {
    "email": "customer_email", "email_address": "customer_email", "e_mail": "customer_email",
    "order_date": "placed_at", "placed_on": "placed_at", "created_at": "placed_at",
    "item_count": "items", "quantity": "items", "n_items": "items",
}
UNIT_SUFFIXES = ("_cents", "_units", "_rounded", "_amount")
COMPATIBLE = {("int", "int"), ("float", "float"), ("str", "str"), ("int", "float"), ("float", "int"), ("int", "str"), ("float", "str")}


def _norm(name: str) -> str:
    n = name.strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in n:
        n = n.replace("__", "_")
    return n


class StaticMapper:
    name = "static"

    def map(self, base: Schema, target: Schema, sample: List[dict]) -> Mapping:
        base_names = {c for c, _ in base}
        return {t: (t if t in base_names else None) for t, _ in target}


class NameBaselineMapper:
    name = "name_baseline"

    def map(self, base: Schema, target: Schema, sample: List[dict]) -> Mapping:
        base_types = dict(base)
        by_norm = {_norm(c): c for c, _ in base}
        out: Mapping = {}
        for t, t_type in target:
            n = _norm(t)
            candidate = by_norm.get(n) or SYNONYMS.get(n)
            if candidate is None:
                stripped = n
                for suffix in UNIT_SUFFIXES:
                    if stripped.endswith(suffix):
                        stripped = stripped[: -len(suffix)]
                for b_norm, b in by_norm.items():
                    b_stripped = b_norm
                    for suffix in UNIT_SUFFIXES:
                        if b_stripped.endswith(suffix):
                            b_stripped = b_stripped[: -len(suffix)]
                    if stripped == b_stripped:
                        candidate = b
                        break
            if candidate is not None and (base_types[candidate], t_type) not in COMPATIBLE:
                candidate = None
            out[t] = candidate
        return out


MAPPERS = [StaticMapper(), NameBaselineMapper()]
