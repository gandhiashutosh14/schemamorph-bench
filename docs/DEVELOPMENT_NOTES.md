# Development notes

How this project was built. It was written from scratch on 2026-09-16; there is no earlier
history.

## Why this project exists

A schema-drift mechanism (calibrated mappings with round-trip verification) is a research
direction in the author's portfolio. The first public release ships the part that can be verified
today: a dataset generator with ground truth and a scoring harness, before any mapper that would be
scored on it. No employer code or data was used; the table and its transformations are invented.

## First release, 2026-09-16

The release was scoped as a small verified increment, with everything simulated or absent
labelled as such.

### Design decisions

- Three scores, not one. A mapping that round-trips must not be counted as correct on that basis,
  so the harness scores structural validity, round trip and semantic correctness separately and
  the `swap` case exists to show why.
- Round trip is "not defined", with the reason, whenever the mapping is not a bijection, the
  case is lossy, or types differ. Reporting "ok" there would be a claim the harness cannot back.
- Coercion is strict. Silently truncating `2489.77` to an integer would have turned a structural
  failure into a value-level semantic failure and hidden the fact that the mapping cannot apply.
- The mappers are baselines on purpose. Neither converts units; the report says so.

### What the tests caught

- The first version of the tests expected `unit_change` with the name baseline to be
  "structurally valid, semantically wrong at the value level". It is a structural failure: the
  baseline finds the right columns, and then fractional units cannot be coerced into an integer
  cents column, so the mapping never applies. The value-level failure the test was looking for is
  exhibited by `lossy_rounding` instead, where whole units are integers, the mapping applies, and
  every value is wrong. The test and the report text were corrected to say what actually happens.

### Verification

| Check | Result |
|---|---|
| `pytest -q` | 8 passed |
| `schemamorph-bench run --rows 200 --seed 7` | 16 runs: 8 correct, 1 structural failure, 7 structurally valid but semantically wrong; `swap` round-trips and fails semantics for both mappers (`reports/benchmark.md`) |

### What is and is not claimed

The fixtures are synthetic and the mappers are baselines. The numbers describe those two
baselines on those fixtures and nothing else. No matcher, calibration, drift detection or repair
is implemented.
