# Schema-drift benchmark

Generated 2026-09-16 18:20 UTC at revision fc1bd94 with `schemamorph-bench run --rows 200 --seed 7 --out reports/benchmark.md`. 200 synthetic rows (seed 7), 8 transformations, 2 deterministic mappers. Structural validity, round-trip behaviour and semantic correctness are scored separately; a round trip that passes proves self-consistency of the mapping, not that a column carries the right meaning.

| Case | What changed | Mapper | Structural | Round trip | Semantic (columns / values) | Verdict | Unmapped targets | Lost sources |
|---|---|---|---|---|---|---|---|---|
| rename | three columns renamed, values unchanged | static | ok | ok | FAIL / ok | **structurally valid, semantically wrong** | email_address, item_count, order_date | customer_email, items, placed_at |
| rename | three columns renamed, values unchanged | name_baseline | ok | ok | ok / ok | **correct** | - | - |
| drop_column | the region column no longer exists in the source | static | ok | ok | ok / ok | **correct** | - | region |
| drop_column | the region column no longer exists in the source | name_baseline | ok | ok | ok / ok | **correct** | - | region |
| type_change | items is now delivered as a string | static | ok | not defined | ok / ok | **correct** | - | - |
| type_change | items is now delivered as a string | name_baseline | ok | not defined | ok / ok | **correct** | - | - |
| unit_change | money columns renamed and converted from cents to units (exact at two decimals) | static | ok | ok | FAIL / ok | **structurally valid, semantically wrong** | order_total, shipping_cost | order_total_cents, shipping_cost_cents |
| unit_change | money columns renamed and converted from cents to units (exact at two decimals) | name_baseline | FAIL | not defined | ok / ok | **structural failure** | - | - |
| lossy_rounding | order total rounded to whole units: the cents are gone and cannot be reconstructed | static | ok | not defined | FAIL / ok | **structurally valid, semantically wrong** | order_total_rounded | order_total_cents |
| lossy_rounding | order total rounded to whole units: the cents are gone and cannot be reconstructed | name_baseline | ok | not defined | ok / FAIL | **structurally valid, semantically wrong** | - | - |
| reorder | columns delivered in a different order, names and values unchanged | static | ok | ok | ok / ok | **correct** | - | - |
| reorder | columns delivered in a different order, names and values unchanged | name_baseline | ok | ok | ok / ok | **correct** | - | - |
| swap | two compatible money columns exchanged their values but kept their names: every name-based mapping is structurally valid and round-trips, and puts the wrong meaning in both columns | static | ok | ok | FAIL / FAIL | **structurally valid, semantically wrong** | - | - |
| swap | two compatible money columns exchanged their values but kept their names: every name-based mapping is structurally valid and round-trips, and puts the wrong meaning in both columns | name_baseline | ok | ok | FAIL / FAIL | **structurally valid, semantically wrong** | - | - |
| compound | a rename, a drop and a type change at once | static | ok | not defined | FAIL / ok | **structurally valid, semantically wrong** | email_address | customer_email, region |
| compound | a rename, a drop and a type change at once | name_baseline | ok | not defined | ok / ok | **correct** | - | region |

## Failure detail

### rename / static: structurally valid, semantically wrong

- semantic: email_address: mapped to None but derives from customer_email
- semantic: order_date: mapped to None but derives from placed_at
- semantic: item_count: mapped to None but derives from items
- round trip: ok (put(get(t)) == t on every sampled row; this checks self-consistency of the mapping, not its meaning)

### unit_change / static: structurally valid, semantically wrong

- semantic: order_total: mapped to None but derives from order_total_cents
- semantic: shipping_cost: mapped to None but derives from shipping_cost_cents
- round trip: ok (put(get(t)) == t on every sampled row; this checks self-consistency of the mapping, not its meaning)

### unit_change / name_baseline: structural failure

- structural: applying the mapping raised ValueError: invalid literal for int() with base 10: '2489.77'
- round trip: not defined (types differ between target and base for a mapped column, so put() would need a conversion)

### lossy_rounding / static: structurally valid, semantically wrong

- semantic: order_total_rounded: mapped to None but derives from order_total_cents
- round trip: not defined (the case is lossy: some values cannot be reconstructed from the target)

### lossy_rounding / name_baseline: structurally valid, semantically wrong

- semantic: order_total_cents: value 2490 after mapping, base has 248977
- round trip: not defined (the case is lossy: some values cannot be reconstructed from the target)

### swap / static: structurally valid, semantically wrong

- semantic: order_total_cents: mapped to order_total_cents but derives from shipping_cost_cents
- semantic: shipping_cost_cents: mapped to shipping_cost_cents but derives from order_total_cents
- semantic: order_total_cents: value 499 after mapping, base has 248977
- round trip: ok (put(get(t)) == t on every sampled row; this checks self-consistency of the mapping, not its meaning)

### swap / name_baseline: structurally valid, semantically wrong

- semantic: order_total_cents: mapped to order_total_cents but derives from shipping_cost_cents
- semantic: shipping_cost_cents: mapped to shipping_cost_cents but derives from order_total_cents
- semantic: order_total_cents: value 499 after mapping, base has 248977
- round trip: ok (put(get(t)) == t on every sampled row; this checks self-consistency of the mapping, not its meaning)

### compound / static: structurally valid, semantically wrong

- semantic: email_address: mapped to None but derives from customer_email
- round trip: not defined (types differ between target and base for a mapped column, so put() would need a conversion)

## Totals

16 mapper × case runs: 8 correct, 1 structural failures, 7 structurally valid but semantically wrong.

The `swap` case is the one to look at: both mappers are structurally valid and round-trip cleanly, and both put each money column's meaning in the other column. Neither mapper converts units: in `lossy_rounding` the name baseline finds the right column, the integer values coerce, and every value is wrong (structurally valid, semantically wrong; no round trip is defined because the cents no longer exist); in `unit_change` the same mapper finds the right columns but fractional units cannot be coerced into an integer cents column, so the mapping fails to apply at all, which is a structural failure with a correct column assignment.
