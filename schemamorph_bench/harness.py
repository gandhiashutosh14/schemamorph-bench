"""
The harness: apply a mapper to a case and score three separate things.

  structural   the mapping names only columns that exist, every mapped value coerces to the base
               column's type, and the mapping applies to every row without an exception
  round trip   for a mapping that is a bijection between mapped columns, put(get(t)) == t on the
               rows (the lens laws for a rename/reorder mapping); "not defined" when the case is
               lossy or the mapping is not a bijection; a passing round trip says the mapping is
               self-consistent, nothing more
  semantic     column level: the mapper assigned each target column to the source column the
               ground truth says it derives from; value level: after the mapper's (non-)conversion
               the values equal the base values, so a unit change the mapper did not notice is a
               value-level failure even when the column assignment is right

Failures are reported per target column so the report can show *which* kind of failure happened.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .generator import BASE_SCHEMA, Case, Row
from .mappers import Mapping

BASE_TYPES = dict(BASE_SCHEMA)


def _coerce(value: Any, to_type: str) -> Any:
    if to_type == "int":
        if isinstance(value, bool):
            raise ValueError("bool is not int")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return int(str(value))
    if to_type == "float":
        return float(value)
    return str(value)


@dataclass
class CaseResult:
    case: str
    mapper: str
    mapping: Mapping
    structural_ok: bool
    structural_failures: List[str] = field(default_factory=list)
    round_trip: str = "not defined"           # ok | fail | not defined
    round_trip_note: str = ""
    semantic_columns_ok: bool = True
    semantic_values_ok: bool = True
    semantic_failures: List[str] = field(default_factory=list)
    unmapped_targets: List[str] = field(default_factory=list)
    lost_sources: List[str] = field(default_factory=list)   # base columns no target maps to

    @property
    def verdict(self) -> str:
        if not self.structural_ok:
            return "structural failure"
        if not (self.semantic_columns_ok and self.semantic_values_ok):
            return "structurally valid, semantically wrong"
        return "correct"

    def to_dict(self) -> Dict[str, Any]:
        return {**self.__dict__, "verdict": self.verdict}


def apply_mapping(mapping: Mapping, rows: List[Row]) -> List[Row]:
    """Rows in base-column terms: {source column: coerced value} for every mapped target column."""
    out = []
    for r in rows:
        mapped = {}
        for target, source in mapping.items():
            if source is None:
                continue
            mapped[source] = _coerce(r[target], BASE_TYPES[source])
        out.append(mapped)
    return out


def _round_trip(mapping: Mapping, rows: List[Row], case: Case) -> Tuple[str, str]:
    if not case.round_trip_defined:
        return "not defined", "the case is lossy: some values cannot be reconstructed from the target"
    pairs = {t: s for t, s in mapping.items() if s is not None}
    if len(set(pairs.values())) != len(pairs):
        return "not defined", "the mapping is not a bijection (two targets map to one source)"
    if any(BASE_TYPES[s] != dict(case.target_schema)[t] for t, s in pairs.items()):
        return "not defined", "types differ between target and base for a mapped column, so put() would need a conversion"
    inverse = {s: t for t, s in pairs.items()}
    for r in rows:
        got = {s: r[t] for t, s in pairs.items()}                 # get: target -> base terms
        back = {inverse[s]: v for s, v in got.items()}            # put: base terms -> target
        if any(back[t] != r[t] for t in pairs):
            return "fail", "put(get(t)) != t on a sampled row"
    return "ok", "put(get(t)) == t on every sampled row; this checks self-consistency of the mapping, not its meaning"


def score(case: Case, mapper_name: str, mapping: Mapping, base_rows: List[Row]) -> CaseResult:
    res = CaseResult(case=case.name, mapper=mapper_name, mapping=dict(mapping), structural_ok=True)
    target_names = {c for c, _ in case.target_schema}
    for t, s in mapping.items():
        if t not in target_names:
            res.structural_ok = False
            res.structural_failures.append(f"{t}: mapper named a target column that does not exist")
        if s is not None and s not in BASE_TYPES:
            res.structural_ok = False
            res.structural_failures.append(f"{t}: mapped to unknown base column {s!r}")
    try:
        mapped_rows = apply_mapping({t: s for t, s in mapping.items() if t in target_names}, case.target_rows)
    except Exception as e:  # noqa: BLE001
        res.structural_ok = False
        res.structural_failures.append(f"applying the mapping raised {type(e).__name__}: {e}")
        mapped_rows = []
    res.unmapped_targets = sorted(t for t, s in mapping.items() if s is None)
    res.lost_sources = sorted(set(BASE_TYPES) - {s for s in mapping.values() if s})

    res.round_trip, res.round_trip_note = _round_trip(mapping, case.target_rows[:50], case)

    # Semantic, column level: the assignment the mapper made vs the derivation that produced the target.
    for t, derivation in case.truth.items():
        assigned = mapping.get(t)
        if derivation.source is None:
            if assigned is not None:
                res.semantic_columns_ok = False
                res.semantic_failures.append(f"{t}: mapped to {assigned} but the target has no source")
        elif assigned != derivation.source:
            res.semantic_columns_ok = False
            res.semantic_failures.append(f"{t}: mapped to {assigned} but derives from {derivation.source}")
    # Semantic, value level: what the mapping produces vs the base values.
    if res.structural_ok and mapped_rows:
        for r_base, r_mapped in zip(base_rows, mapped_rows):
            for source, value in r_mapped.items():
                if r_base[source] != value:
                    res.semantic_values_ok = False
                    res.semantic_failures.append(f"{source}: value {value!r} after mapping, base has {r_base[source]!r}")
                    break
            if not res.semantic_values_ok:
                break
    return res


def run(cases: List[Case], base_rows: List[Row], mappers) -> List[CaseResult]:
    results = []
    base_schema = list(BASE_SCHEMA)
    for case in cases:
        for mapper in mappers:
            mapping = mapper.map(base_schema, case.target_schema, case.target_rows[:20])
            results.append(score(case, mapper.name, mapping, base_rows))
    return results
