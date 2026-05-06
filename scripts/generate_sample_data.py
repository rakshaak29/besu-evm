#!/usr/bin/env python3
"""
generate_sample_data.py — Generates realistic sample benchmark data
for dashboard development and demonstration purposes.
Run once to populate results/history/ with fake historical runs.
"""
import json, random, math
from pathlib import Path
from datetime import datetime, timedelta, timezone

BENCHMARKS = [
    ("ADD",            "arithmetic", 4200, "MGps"),
    ("MUL",            "arithmetic", 2800, "MGps"),
    ("DIV",            "arithmetic", 1950, "MGps"),
    ("EXP",            "arithmetic",  380, "MGps"),
    ("AND",            "bitwise",    4800, "MGps"),
    ("XOR",            "bitwise",    4700, "MGps"),
    ("SHL",            "bitwise",    4100, "MGps"),
    ("SHR",            "bitwise",    4050, "MGps"),
    ("PUSH_POP",       "stack",      5500, "MGps"),
    ("DUP",            "stack",      5200, "MGps"),
    ("MSTORE_MLOAD",   "memory",     3100, "MGps"),
    ("SHA3_32B",       "crypto",      980, "MGps"),
    ("CALLDATALOAD",   "calls",      3900, "MGps"),
]

REFS = ["main", "main", "main", "main", "v25.1.0", "v25.2.0", "v25.3.0"]
SHAS = [f"{random.randint(0x1000000, 0xFFFFFFF):07x}" for _ in range(20)]

def noisy(base, pct=3.0):
    return round(base * (1 + random.uniform(-pct/100, pct/100)), 2)

def make_run(ts: datetime, ref: str, sha: str, drift: float):
    bmarks = []
    for name, cat, base_score, unit in BENCHMARKS:
        score = noisy(base_score * (1 + drift), pct=2.5)
        bmarks.append({
            "name": name,
            "category": cat,
            "description": f"{name} operation benchmark",
            "status": "ok",
            "score": score,
            "score_unit": unit,
            "exec_time_ms": round(random.uniform(50, 300), 1),
            "gas_used": random.randint(50_000_000, 100_000_000),
            "gas_limit": 100_000_000,
            "repeats": 10,
        })
    return {
        "schema_version": "1.0",
        "type": "evmtool",
        "besu_sha": sha,
        "besu_ref": ref,
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_benchmarks": len(bmarks),
        "benchmarks": bmarks,
    }

out_dir = Path("results/history")
out_dir.mkdir(parents=True, exist_ok=True)

base_ts = datetime(2025, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
refs_cycle = ["main"] * 14 + ["v25.1.0", "v25.2.0"]
sha_pool = [f"{random.randint(0x1000000, 0xFFFFFFF):07x}" for _ in range(20)]

for i in range(16):
    ts = base_ts + timedelta(weeks=i)
    ref = refs_cycle[i % len(refs_cycle)]
    sha = sha_pool[i % len(sha_pool)]
    # Simulate gradual improvement with a small regression at run 10
    drift = i * 0.005
    if i == 10:
        drift -= 0.08   # simulate a regression
    run = make_run(ts, ref, sha, drift)
    filename = ts.strftime("%Y%m%d_%H%M%S") + "_evmtool.json"
    path = out_dir / filename
    with open(path, "w") as f:
        json.dump(run, f, indent=2)
    print(f"  wrote {filename}")

print(f"\n✅ Generated 16 sample runs in {out_dir}")
