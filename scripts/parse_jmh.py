#!/usr/bin/env python3
"""
parse_jmh.py — Parses raw JMH JSON output into the normalized
benchmark result format used by the Besu Benchmarks dashboard.

Usage:
  python3 parse_jmh.py \
    --input jmh-raw.json \
    --output results/history/20250101_120000_jmh.json \
    --besu-sha abc1234 \
    --besu-ref main \
    --timestamp 2025-01-01T12:00:00Z
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Parse JMH JSON output")
    p.add_argument("--input", required=True, help="Path to raw JMH JSON file")
    p.add_argument("--output", required=True, help="Path to write normalized JSON")
    p.add_argument("--besu-sha", required=True, help="Besu git commit SHA")
    p.add_argument("--besu-ref", required=True, help="Besu branch/tag/ref")
    p.add_argument("--timestamp", default=None, help="ISO8601 timestamp (default: now)")
    return p.parse_args()


def normalize_benchmark_name(raw_name: str) -> str:
    """Strip package prefix, keep only ClassName.methodName."""
    parts = raw_name.split(".")
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return raw_name


def parse_jmh_result(entry: dict) -> dict:
    """Convert a single JMH result entry to our normalized schema."""
    primary = entry.get("primaryMetric", {})
    raw_scores = primary.get("rawData", [[]])[0] if primary.get("rawData") else []

    score = primary.get("score", 0.0)
    score_error = primary.get("scoreError", 0.0)
    unit = primary.get("scoreUnit", "ops/s")

    # Determine category from class name
    class_name = entry.get("benchmark", "").split(".")[-2]
    category = categorize(class_name)

    return {
        "name": normalize_benchmark_name(entry.get("benchmark", "")),
        "full_name": entry.get("benchmark", ""),
        "category": category,
        "mode": entry.get("mode", "thrpt"),
        "score": round(score, 4),
        "score_error": round(score_error, 4),
        "score_unit": unit,
        "raw_scores": [round(s, 4) for s in raw_scores],
        "warmup_iterations": entry.get("warmupIterations", 0),
        "measurement_iterations": entry.get("measurementIterations", 0),
        "threads": entry.get("threads", 1),
        "jvm_args": entry.get("jvmArgs", []),
    }


def categorize(class_name: str) -> str:
    """Heuristic category assignment from benchmark class name."""
    name_lower = class_name.lower()
    if any(k in name_lower for k in ["add", "sub", "mul", "div", "mod", "exp"]):
        return "arithmetic"
    if any(k in name_lower for k in ["and", "or", "xor", "not", "shl", "shr", "sar"]):
        return "bitwise"
    if any(k in name_lower for k in ["sha", "keccak", "ecrecover", "bls", "bnpair", "p256"]):
        return "crypto"
    if any(k in name_lower for k in ["memory", "mstore", "mload", "calldatacopy"]):
        return "memory"
    if any(k in name_lower for k in ["sload", "sstore", "tload", "tstore"]):
        return "storage"
    if any(k in name_lower for k in ["call", "create", "selfdestruct"]):
        return "calls"
    if any(k in name_lower for k in ["transaction", "txtype"]):
        return "transaction"
    return "other"


def main():
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        raw = json.load(f)

    timestamp = args.timestamp or datetime.now(timezone.utc).isoformat()
    benchmarks = [parse_jmh_result(entry) for entry in raw]

    result = {
        "schema_version": "1.0",
        "type": "jmh",
        "besu_sha": args.besu_sha,
        "besu_ref": args.besu_ref,
        "timestamp": timestamp,
        "total_benchmarks": len(benchmarks),
        "benchmarks": benchmarks,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"✅ Parsed {len(benchmarks)} JMH benchmarks → {output_path}")


if __name__ == "__main__":
    main()
