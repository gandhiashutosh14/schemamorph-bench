"""
CLI:
  schemamorph-bench run --rows 200 --seed 7 --out reports/benchmark.md --json reports/benchmark.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from .generator import CASES, build_cases
from .harness import CaseResult, run
from .mappers import MAPPERS

ROOT = Path(__file__).resolve().parent.parent


def _revision() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
        dirty = [line for line in status.splitlines() if line.strip() and "reports/" not in line]
        return sha + (" (uncommitted changes present)" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def render(results: List[CaseResult], cases, rows: int, seed: int, command: str) -> str:
    by_case = {c.name: c for c in cases}
    lines = ["# Schema-drift benchmark", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} at revision {_revision()} with `{command}`. "
             f"{rows} synthetic rows (seed {seed}), {len(cases)} transformations, {len(MAPPERS)} deterministic mappers. "
             "Structural validity, round-trip behaviour and semantic correctness are scored separately; a round trip that "
             "passes proves self-consistency of the mapping, not that a column carries the right meaning.", "",
             "| Case | What changed | Mapper | Structural | Round trip | Semantic (columns / values) | Verdict | Unmapped targets | Lost sources |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r.case} | {by_case[r.case].description} | {r.mapper} | {'ok' if r.structural_ok else 'FAIL'} | {r.round_trip} | "
                     f"{'ok' if r.semantic_columns_ok else 'FAIL'} / {'ok' if r.semantic_values_ok else 'FAIL'} | **{r.verdict}** | "
                     f"{', '.join(r.unmapped_targets) or '-'} | {', '.join(r.lost_sources) or '-'} |")
    lines += ["", "## Failure detail", ""]
    for r in results:
        if r.structural_failures or r.semantic_failures or r.round_trip == "fail":
            lines.append(f"### {r.case} / {r.mapper}: {r.verdict}")
            lines.append("")
            for f in r.structural_failures:
                lines.append(f"- structural: {f}")
            for f in r.semantic_failures[:6]:
                lines.append(f"- semantic: {f}")
            lines.append(f"- round trip: {r.round_trip} ({r.round_trip_note})")
            lines.append("")
    correct = sum(1 for r in results if r.verdict == "correct")
    structural = sum(1 for r in results if not r.structural_ok)
    semantic = sum(1 for r in results if r.structural_ok and r.verdict != "correct")
    lines += ["## Totals", "", f"{len(results)} mapper × case runs: {correct} correct, {structural} structural failures, "
              f"{semantic} structurally valid but semantically wrong.", "",
              "The `swap` case is the one to look at: both mappers are structurally valid and round-trip cleanly, and both put "
              "each money column's meaning in the other column. Neither mapper converts units: in `lossy_rounding` the name "
              "baseline finds the right column, the integer values coerce, and every value is wrong (structurally valid, "
              "semantically wrong; no round trip is defined because the cents no longer exist); in `unit_change` the same "
              "mapper finds the right columns but fractional units cannot be coerced into an integer cents column, so the "
              "mapping fails to apply at all, which is a structural failure with a correct column assignment."]
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="schemamorph-bench", description="Schema-drift benchmark: generate transformed tables with ground truth and score mappers.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--rows", type=int, default=200)
    r.add_argument("--seed", type=int, default=7)
    r.add_argument("--out", required=True)
    r.add_argument("--json", dest="json_path")
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    base, cases = build_cases(args.rows, args.seed)
    results = run(cases, base, MAPPERS)
    text = render(results, cases, args.rows, args.seed, f"schemamorph-bench run --rows {args.rows} --seed {args.seed} --out {args.out}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text, encoding="utf-8")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps([x.to_dict() for x in results], indent=2), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
