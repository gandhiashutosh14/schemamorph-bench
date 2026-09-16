"""
SCHEMAMORPH bench — a small, reproducible benchmark of how schema mappings
fail when the source changes.

A seeded generator produces a base table and a set of explicit transformations
(rename, drop, type change, unit change, lossy rounding, reorder, a swap of
two compatible columns, and a compound change), each with ground-truth
metadata. A harness applies mappers to each transformed schema and reports
structural validity, round-trip behaviour and semantic correctness
separately, because they are different things: a mapping can apply cleanly,
round-trip perfectly, and still put the wrong meaning in a column.

Benchmark artifact. There is no learned matcher, no confidence calibration
and no automatic repair in this repository.
"""
__version__ = "0.1.0a1"
