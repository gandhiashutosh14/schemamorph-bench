from schemamorph_bench.cli import main
from schemamorph_bench.generator import BASE_SCHEMA, CASES, build_cases, generate_base
from schemamorph_bench.harness import apply_mapping, run, score
from schemamorph_bench.mappers import MAPPERS, NameBaselineMapper, StaticMapper


def _results(rows=60, seed=3):
    base, cases = build_cases(rows, seed)
    return base, cases, {(r.case, r.mapper): r for r in run(cases, base, MAPPERS)}


def test_generator_is_deterministic_per_seed_and_cases_carry_ground_truth():
    assert generate_base(20, 1) == generate_base(20, 1) and generate_base(20, 1) != generate_base(20, 2)
    base, cases = build_cases(30, 9)
    assert [c.name for c in cases] == [n for n, _ in CASES]
    for c in cases:
        assert len(c.target_rows) == 30 and set(c.truth) == {col for col, _ in c.target_schema}
        for t, d in c.truth.items():
            if d.source is not None:
                assert d.source in dict(BASE_SCHEMA)
    assert next(c for c in cases if c.name == "drop_column").dropped == ["region"]
    assert next(c for c in cases if c.name == "lossy_rounding").round_trip_defined is False
    swap = next(c for c in cases if c.name == "swap")
    assert swap.truth["order_total_cents"].source == "shipping_cost_cents" and swap.truth["order_total_cents"].conversion == "value_swap"


def test_rename_and_reorder_outcomes():
    _, _, res = _results()
    assert res[("rename", "static")].verdict == "structural failure" or res[("rename", "static")].unmapped_targets  # static cannot see renamed columns
    assert res[("rename", "static")].lost_sources == ["customer_email", "items", "placed_at"]
    assert res[("rename", "name_baseline")].verdict == "correct" and res[("rename", "name_baseline")].round_trip == "ok"
    assert res[("reorder", "static")].verdict == "correct" and res[("reorder", "name_baseline")].verdict == "correct"


def test_swap_counterexample_round_trips_and_is_semantically_wrong():
    _, _, res = _results()
    for mapper in ("static", "name_baseline"):
        r = res[("swap", mapper)]
        assert r.structural_ok and r.round_trip == "ok"
        assert not r.semantic_columns_ok and not r.semantic_values_ok
        assert r.verdict == "structurally valid, semantically wrong"
        assert any("order_total_cents: mapped to order_total_cents but derives from shipping_cost_cents" in f for f in r.semantic_failures)


def test_lossy_case_has_no_defined_round_trip_and_unit_change_is_a_value_failure():
    _, _, res = _results()
    for mapper in ("static", "name_baseline"):
        assert res[("lossy_rounding", mapper)].round_trip == "not defined"
        assert "lossy" in res[("lossy_rounding", mapper)].round_trip_note
    # unit_change: the baseline finds the right columns, but 123.45 units cannot be coerced into an integer
    # cents column, so the mapping does not even apply: a structural failure with a correct column assignment.
    unit = res[("unit_change", "name_baseline")]
    assert unit.mapping["order_total"] == "order_total_cents" and unit.semantic_columns_ok
    assert not unit.structural_ok and any("raised" in f for f in unit.structural_failures)
    assert res[("unit_change", "static")].unmapped_targets == ["order_total", "shipping_cost"]
    assert res[("unit_change", "static")].verdict == "structurally valid, semantically wrong"
    # lossy_rounding: whole units are integers, so the mapping applies, the column is right, and every value is wrong.
    lossy = res[("lossy_rounding", "name_baseline")]
    assert lossy.structural_ok and lossy.semantic_columns_ok and not lossy.semantic_values_ok
    assert lossy.mapping["order_total_rounded"] == "order_total_cents"
    assert lossy.verdict == "structurally valid, semantically wrong"


def test_drop_type_change_and_compound():
    _, _, res = _results()
    drop = res[("drop_column", "name_baseline")]
    assert drop.verdict == "correct" and drop.lost_sources == ["region"] and drop.unmapped_targets == []
    tc = res[("type_change", "name_baseline")]
    assert tc.structural_ok and tc.semantic_values_ok            # "3" coerces back to 3, meaning preserved
    assert tc.round_trip == "not defined" and "types differ" in tc.round_trip_note
    assert res[("compound", "name_baseline")].verdict == "correct"
    assert res[("compound", "static")].lost_sources == ["customer_email", "region"]


def test_mapping_application_coerces_and_reports_bad_values():
    base = generate_base(3, 1)
    rows = apply_mapping({"items": "items"}, [{"items": "4"}])
    assert rows == [{"items": 4}]
    _, cases = build_cases(3, 1)
    case = next(c for c in cases if c.name == "type_change")
    bad = score(case, "broken", {"items": "order_id", "order_id": "items"}, base)   # both wrong, both coercible
    assert bad.structural_ok and not bad.semantic_columns_ok
    worse = score(case, "broken", {"status": "items"}, base)                          # "paid" cannot become an int
    assert not worse.structural_ok and any("raised" in f for f in worse.structural_failures)


def test_name_baseline_respects_type_compatibility_and_synonyms():
    m = NameBaselineMapper()
    base = list(BASE_SCHEMA)
    assert m.map(base, [("Email-Address", "str"), ("ITEM_COUNT", "int"), ("nothing_like_it", "str")], []) == \
        {"Email-Address": "customer_email", "ITEM_COUNT": "items", "nothing_like_it": None}
    assert m.map(base, [("customer_email", "int")], []) == {"customer_email": None}     # str column cannot feed an int target
    assert StaticMapper().map(base, [("order_id", "int"), ("renamed", "int")], []) == {"order_id": "order_id", "renamed": None}


def test_cli_writes_report_and_json(tmp_path):
    out, js = tmp_path / "b.md", tmp_path / "b.json"
    assert main(["run", "--rows", "25", "--seed", "2", "--out", str(out), "--json", str(js)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "structurally valid, semantically wrong" in text and "swap" in text and js.exists()
