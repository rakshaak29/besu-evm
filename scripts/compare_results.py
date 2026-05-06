#!/usr/bin/env python3
"""
compare_results.py — Compares two benchmark result files (base vs PR)
and outputs a human-readable Markdown comment for GitHub PRs.

Usage:
  python3 compare_results.py \
    --base /tmp/base_results.json \
    --pr   /tmp/pr_results.json \
    --output /tmp/comparison.md \
    --regression-threshold 5.0
"""

import argparse
import json
import sys
from pathlib import Path


REGRESSION_EMOJI = "🔴"
IMPROVEMENT_EMOJI = "🟢"
NEUTRAL_EMOJI = "⚪"
WARNING_EMOJI = "⚠️"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="Base branch results JSON")
    p.add_argument("--pr", required=True, help="PR branch results JSON")
    p.add_argument("--output", required=True, help="Output Markdown file")
    p.add_argument(
        "--regression-threshold",
        type=float,
        default=5.0,
        help="% change threshold to flag as regression (default: 5.0)",
    )
    return p.parse_args()


def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def by_name(result_file: dict) -> dict:
    return {b["name"]: b for b in result_file.get("benchmarks", [])}


def pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100.0


def emoji_for(pct: float, threshold: float, higher_is_better: bool) -> str:
    """Return coloured circle based on direction and threshold."""
    significant = abs(pct) >= threshold
    if not significant:
        return NEUTRAL_EMOJI
    if higher_is_better:
        return IMPROVEMENT_EMOJI if pct > 0 else REGRESSION_EMOJI
    else:
        return IMPROVEMENT_EMOJI if pct < 0 else REGRESSION_EMOJI


def higher_is_better(unit: str) -> bool:
    unit_lower = unit.lower()
    if "ops/s" in unit_lower or "mgps" in unit_lower or "throughput" in unit_lower:
        return True
    # ns/op, ms — lower is better
    return False


def build_comment(base_data: dict, pr_data: dict, threshold: float) -> str:
    base_map = by_name(base_data)
    pr_map = by_name(pr_data)

    all_names = sorted(set(base_map) | set(pr_map))

    rows = []
    regressions = []
    improvements = []

    for name in all_names:
        base_b = base_map.get(name)
        pr_b = pr_map.get(name)

        if base_b is None:
            rows.append(f"| {name} | — | {pr_b['score']:.2f} | {pr_b['score_unit']} | `NEW` |")
            continue
        if pr_b is None:
            rows.append(f"| {name} | {base_b['score']:.2f} | — | {base_b['score_unit']} | `REMOVED` |")
            continue

        base_score = base_b.get("score", 0.0)
        pr_score = pr_b.get("score", 0.0)
        unit = pr_b.get("score_unit", "")
        pct = pct_change(base_score, pr_score)
        hib = higher_is_better(unit)
        icon = emoji_for(pct, threshold, hib)

        if abs(pct) >= threshold:
            if (hib and pct < 0) or (not hib and pct > 0):
                regressions.append((name, pct, unit))
            else:
                improvements.append((name, pct, unit))

        direction = "▲" if pct > 0 else ("▼" if pct < 0 else "=")
        rows.append(
            f"| {icon} {name} | {base_score:.2f} | {pr_score:.2f} | {unit} | {direction} {pct:+.1f}% |"
        )

    base_ref = base_data.get("besu_ref", "base")
    pr_ref = pr_data.get("besu_ref", "pr")
    base_sha = base_data.get("besu_sha", "?")
    pr_sha = pr_data.get("besu_sha", "?")
    bench_type = pr_data.get("type", "unknown")

    lines = [
        "## 📊 EVM Benchmark Results",
        "",
        f"> Comparing **{base_ref}** (`{base_sha[:7]}`) → **{pr_ref}** (`{pr_sha[:7]}`)",
        f"> Benchmark type: `{bench_type}` | Regression threshold: ±{threshold}%",
        "",
    ]

    if regressions:
        lines += [
            f"### {REGRESSION_EMOJI} Regressions Detected",
            "",
            "The following benchmarks regressed beyond the threshold:",
            "",
        ]
        for name, pct, unit in sorted(regressions, key=lambda x: x[1]):
            lines.append(f"- **{name}**: `{pct:+.1f}%` ({unit})")
        lines.append("")

    if improvements:
        lines += [
            f"### {IMPROVEMENT_EMOJI} Improvements",
            "",
        ]
        for name, pct, unit in sorted(improvements, key=lambda x: -x[1]):
            lines.append(f"- **{name}**: `{pct:+.1f}%` ({unit})")
        lines.append("")

    lines += [
        "### Full Results",
        "",
        "| Benchmark | Base | PR | Unit | Change |",
        "|-----------|------|----|------|--------|",
    ]
    lines += rows
    lines += [
        "",
        "<details>",
        "<summary>Legend</summary>",
        "",
        f"- {IMPROVEMENT_EMOJI} Improvement ≥ {threshold}%",
        f"- {REGRESSION_EMOJI} Regression ≥ {threshold}%",
        f"- {NEUTRAL_EMOJI} No significant change (< {threshold}%)",
        "",
        "</details>",
    ]

    return "\n".join(lines)


def main():
    args = parse_args()

    base_data = load(args.base)
    pr_data = load(args.pr)

    comment = build_comment(base_data, pr_data, args.regression_threshold)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(comment)

    print(f"✅ Comparison written to {out}")

    # Exit code 1 if regressions found — CI can use this to fail the check
    base_map = by_name(base_data)
    pr_map = by_name(pr_data)
    for name in set(base_map) & set(pr_map):
        b = base_map[name]
        p = pr_map[name]
        pct = pct_change(b.get("score", 0), p.get("score", 0))
        hib = higher_is_better(p.get("score_unit", ""))
        if abs(pct) >= args.regression_threshold:
            if (hib and pct < 0) or (not hib and pct > 0):
                print(f"⚠️  Regression detected in: {name} ({pct:+.1f}%)")
                sys.exit(1)

    print("✅ No regressions detected.")


if __name__ == "__main__":
    main()
