#!/usr/bin/env python3
"""
build_dashboard_data.py — Aggregates all JSON result files from
results/history/ into a single dashboard/data/index.json that
the browser dashboard reads at runtime.

Usage:
  python3 build_dashboard_data.py --results-dir results/history
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--results-dir", default="results/history", help="Directory of result JSONs")
    p.add_argument("--output-dir", default="dashboard/data", help="Output directory for dashboard data")
    return p.parse_args()


def load_all_results(results_dir: Path) -> list[dict]:
    files = sorted(results_dir.glob("*.json"))
    results = []
    for f in files:
        try:
            with open(f) as fp:
                data = json.load(fp)
            data["_filename"] = f.name
            results.append(data)
        except Exception as e:
            print(f"  ⚠ Skipping {f.name}: {e}")
    return results


def build_runs_index(results: list[dict]) -> list[dict]:
    """Lightweight run summaries for the runs list."""
    runs = []
    for r in results:
        benchmarks = r.get("benchmarks", [])
        ok = sum(1 for b in benchmarks if b.get("status") != "error")
        runs.append({
            "filename": r["_filename"],
            "type": r.get("type", "unknown"),
            "timestamp": r.get("timestamp", ""),
            "besu_ref": r.get("besu_ref", ""),
            "besu_sha": r.get("besu_sha", ""),
            "total": r.get("total_benchmarks", len(benchmarks)),
            "ok": ok,
        })
    return sorted(runs, key=lambda x: x["timestamp"], reverse=True)


def build_trend_data(results: list[dict]) -> dict:
    """
    Returns: { benchmark_name: [ {timestamp, besu_ref, besu_sha, score, unit}, ... ] }
    Sorted chronologically.
    """
    trends: dict[str, list] = {}

    for r in sorted(results, key=lambda x: x.get("timestamp", "")):
        ts = r.get("timestamp", "")
        ref = r.get("besu_ref", "")
        sha = r.get("besu_sha", "")

        for b in r.get("benchmarks", []):
            if b.get("status") == "error":
                continue
            name = b.get("name", "unknown")
            if name not in trends:
                trends[name] = []
            trends[name].append({
                "timestamp": ts,
                "besu_ref": ref,
                "besu_sha": sha,
                "score": b.get("score", 0.0),
                "score_unit": b.get("score_unit", ""),
                "category": b.get("category", "other"),
            })

    return trends


def build_latest_snapshot(results: list[dict]) -> list[dict]:
    """Returns the most recent result entry for each benchmark."""
    latest: dict[str, dict] = {}

    for r in sorted(results, key=lambda x: x.get("timestamp", "")):
        ts = r.get("timestamp", "")
        ref = r.get("besu_ref", "")
        sha = r.get("besu_sha", "")
        for b in r.get("benchmarks", []):
            if b.get("status") == "error":
                continue
            name = b.get("name", "unknown")
            latest[name] = {
                **b,
                "timestamp": ts,
                "besu_ref": ref,
                "besu_sha": sha,
            }

    return sorted(latest.values(), key=lambda x: (x.get("category", ""), x.get("name", "")))


def detect_regressions(trends: dict, threshold_pct: float = 10.0) -> list[dict]:
    """
    Check if the last run is worse than the previous run by more than threshold.
    Returns a list of regression dicts.
    """
    regressions = []
    for name, points in trends.items():
        if len(points) < 2:
            continue
        prev = points[-2]
        curr = points[-1]
        prev_score = prev.get("score", 0)
        curr_score = curr.get("score", 0)
        if prev_score == 0:
            continue
        pct = ((curr_score - prev_score) / prev_score) * 100.0
        unit = curr.get("score_unit", "")
        higher_is_better = "MGps" in unit or "ops/s" in unit.lower()
        if higher_is_better and pct <= -threshold_pct:
            regressions.append({
                "name": name,
                "category": curr.get("category", ""),
                "pct_change": round(pct, 2),
                "prev_score": prev_score,
                "curr_score": curr_score,
                "unit": unit,
                "prev_ref": prev.get("besu_ref", ""),
                "curr_ref": curr.get("besu_ref", ""),
            })
        elif not higher_is_better and pct >= threshold_pct:
            regressions.append({
                "name": name,
                "category": curr.get("category", ""),
                "pct_change": round(pct, 2),
                "prev_score": prev_score,
                "curr_score": curr_score,
                "unit": unit,
                "prev_ref": prev.get("besu_ref", ""),
                "curr_ref": curr.get("besu_ref", ""),
            })
    return sorted(regressions, key=lambda x: x["pct_change"])


def main():
    args = parse_args()
    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Loading results from {results_dir} ...")
    all_results = load_all_results(results_dir)
    print(f"   Found {len(all_results)} result file(s).")

    runs = build_runs_index(all_results)
    trends = build_trend_data(all_results)
    latest = build_latest_snapshot(all_results)
    regressions = detect_regressions(trends)

    index = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_runs": len(runs),
        "total_benchmarks": len(latest),
        "regressions": regressions,
        "runs": runs,
        "latest": latest,
    }

    # Write index.json (run metadata + latest snapshot)
    with open(output_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2)

    # Write trends.json (historical data per benchmark)
    with open(output_dir / "trends.json", "w") as f:
        json.dump(trends, f, indent=2)

    print(f"✅ Dashboard data written to {output_dir}/")
    print(f"   - index.json  ({len(latest)} benchmarks, {len(regressions)} regressions)")
    print(f"   - trends.json ({len(trends)} trend series)")


if __name__ == "__main__":
    main()
