# SCHEMAMORPH bench

**A reproducible schema-drift benchmark.** A seeded generator makes a source table change in eight explicit ways, keeps the ground truth of how each target column was derived, and a harness scores mappers on three different things: does the mapping apply, does it round-trip, and does it put the right meaning in each column.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) [![tests](https://github.com/gandhiashutosh14/schemamorph-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/gandhiashutosh14/schemamorph-bench/actions/workflows/ci.yml) ![Status](https://img.shields.io/badge/status-benchmark%20artifact-orange)

---

## The problem, and what is implemented

Every integration breaks the day the other side renames a column, changes a type, or moves from cents to units. The dangerous failures are not the ones that throw: they are the mappings that still apply, still round-trip, and quietly carry the wrong meaning. This repository is the test bed for that distinction, not a mapper.

Implemented:

- **Generator** (`schemamorph_bench/generator.py`): a synthetic orders table (seeded) and eight transformations, each producing a target schema, target rows and a ground-truth derivation per target column (source column, conversion, lossy or not): `rename`, `drop_column`, `type_change`, `unit_change` (cents to units, exact at two decimals), `lossy_rounding` (whole units, cents gone), `reorder`, `swap` (two compatible money columns exchange values but keep their names), `compound`.
- **Two deterministic mappers** (`mappers.py`): `static` (the base mapping applied blindly by column name) and `name_baseline` (normalised names, a short synonym list, unit suffixes, a type-compatibility check). Neither sees the ground truth; neither converts units.
- **Harness** (`harness.py`): per mapper and case, *structural validity* (columns exist, values coerce, the mapping applies to every row), *round trip* (`put(get(t)) == t` on sampled rows where the mapping is a bijection and the case is not lossy; otherwise "not defined" with the reason), and *semantic correctness* at column level (assignment equals the derivation) and value level (mapped values equal the base values).

**Status: benchmark artifact.** There is no learned matcher, no confidence calibration, no drift detector and no automatic repair here; those are the things this benchmark exists to test, and they are listed as unimplemented rather than implied.

## Result summary

`schemamorph-bench run --rows 200 --seed 7` ([`reports/benchmark.md`](reports/benchmark.md), revision stamped in the file):

| Case | static | name_baseline |
|---|---|---|
| rename | semantically wrong (three targets unmapped) | correct |
| drop_column | correct (region reported lost) | correct |
| type_change | correct | correct |
| unit_change | semantically wrong (money targets unmapped) | **structural failure**: right columns, fractional units cannot become integer cents |
| lossy_rounding | semantically wrong (target unmapped) | **structurally valid, semantically wrong**: right column, every value off by the rounding and the scale |
| reorder | correct | correct |
| swap | **round trip ok, semantics wrong** | **round trip ok, semantics wrong** |
| compound | semantically wrong | correct |

16 runs: 8 correct, 1 structural failure, 7 structurally valid but semantically wrong. The `swap` row is the reason the harness scores three things instead of one: both mappers apply cleanly and satisfy `put(get(t)) == t` on every row, and both put each money column's meaning in the other column. A round-trip law is a self-consistency check on a mapping, not evidence that the mapping is right; the ground-truth fixtures are what tell the two apart.

## Quickstart

```bash
git clone https://github.com/gandhiashutosh14/schemamorph-bench.git
cd schemamorph-bench
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                            # 8 tests, no network, no model
schemamorph-bench run --rows 200 --seed 7 --out reports/benchmark.md --json reports/benchmark.json
```

To score your own mapper, implement `map(base_schema, target_schema, sample_rows) -> {target column: source column or None}` and pass it to `harness.run`; the tests show the call.

## Boundaries and assumptions

- Round trips are checked only where they are defined: the mapping is a bijection between mapped columns, the case is not lossy, and types agree. A type change makes the round trip "not defined" because `put()` would need a conversion the mapping does not carry; a lossy case has no round trip because the information no longer exists. The report says which applies.
- Coercion is strict: `"3"` becomes `3`, `2489.77` does not become an integer. A mapper that finds the right column but cannot make the values fit is reported as a structural failure with a correct column assignment, not as a success.
- The ground truth is metadata about how the target was made. Nothing in the harness infers it from the data, and no mapper sees it.
- One synthetic table, eight transformations, two baselines. Nothing here says how any real mapper performs on real schemas.

## Prior work this sits next to

Schema-matching benchmarks and matchers (Valentine, and the LLM-era matchers built on it), the bidirectional-lens literature (Foster et al.) for the round-trip laws, and data-contract and data-observability tools for the structural checks. This repository contributes fixtures and a scoring split, not a new matcher, and claims no novelty.

## Roadmap

None of it promised: more transformations (split and merge columns, encoding changes, nested JSON), a matcher that reports a confidence so the harness can score calibration honestly against these fixtures, and a drift detector scored on time-to-detect across successive transformations.

## Project layout

```
schemamorph_bench/generator.py   base table, eight transformations, ground truth
schemamorph_bench/mappers.py     static and name-baseline mappers
schemamorph_bench/harness.py     structural, round-trip and semantic scoring
schemamorph_bench/cli.py         run -> Markdown and JSON report
tests/test_bench.py              generator determinism, every transformation's truth, the swap counterexample, the lossy flag, CLI
reports/                         the committed run with the revision that produced it
docs/DEVELOPMENT_NOTES.md        how this was built, including what the tests caught
```

## License

MIT. See [LICENSE](LICENSE).
