#!/usr/bin/env python3
"""
run_evmtool_benchmarks.py — Runs the Besu evmtool EVM benchmarks
and captures results in the normalized benchmark format.

This script drives the evmtool binary with a set of benchmark
definitions (EVM bytecode + inputs + gas), measures throughput (MGps),
and outputs a structured JSON results file.

Usage:
  python3 run_evmtool_benchmarks.py \
    --evmtool path/to/evm \
    --genesis path/to/evmtool-genesis.json \
    --output results/history/20250101_120000_evmtool.json \
    --besu-sha abc1234 \
    --besu-ref main \
    --timestamp 2025-01-01T12:00:00Z
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# -------------------------------------------------------------------
# Benchmark definitions
# Each entry: name, category, code (hex EVM bytecode), gas, input, repeats
# -------------------------------------------------------------------
BENCHMARKS = [
    # ── Arithmetic ──────────────────────────────────────────────────
    {
        "name": "ADD",
        "category": "arithmetic",
        "description": "Simple ADD operation in a tight loop",
        "code": "5B6001600101600056",   # JUMPDEST PUSH1 1 PUSH1 1 ADD POP JUMP 0
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "MUL",
        "category": "arithmetic",
        "description": "MUL operation in a tight loop",
        "code": "5B6001600102600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "DIV",
        "category": "arithmetic",
        "description": "DIV operation in a tight loop",
        "code": "5B6001600204600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "EXP",
        "category": "arithmetic",
        "description": "EXP operation (small exponent) in a loop",
        "code": "5B600260020A600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 5,
    },
    # ── Bitwise ─────────────────────────────────────────────────────
    {
        "name": "AND",
        "category": "bitwise",
        "description": "AND operation in a tight loop",
        "code": "5B600160FF1660005600",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "XOR",
        "category": "bitwise",
        "description": "XOR operation in a tight loop",
        "code": "5B600160FF1860005600",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "SHL",
        "category": "bitwise",
        "description": "SHL (left shift) in a tight loop",
        "code": "5B60016002601B600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "SHR",
        "category": "bitwise",
        "description": "SHR (right shift) in a tight loop",
        "code": "5B600160021C600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    # ── Stack ops ───────────────────────────────────────────────────
    {
        "name": "PUSH_POP",
        "category": "stack",
        "description": "PUSH1 + POP in a tight loop",
        "code": "5B600050600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    {
        "name": "DUP",
        "category": "stack",
        "description": "DUP1 + POP in a tight loop",
        "code": "5B600080506001600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    # ── Memory ──────────────────────────────────────────────────────
    {
        "name": "MSTORE_MLOAD",
        "category": "memory",
        "description": "MSTORE then MLOAD cycle",
        "code": "5B600160005260006051600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    # ── Hashing / Crypto ────────────────────────────────────────────
    {
        "name": "SHA3_32B",
        "category": "crypto",
        "description": "KECCAK256 over 32 bytes",
        "code": "5B60006020602020600056",
        "gas": 100_000_000,
        "input": "",
        "repeats": 10,
    },
    # ── Static call-like patterns ────────────────────────────────────
    {
        "name": "CALLDATALOAD",
        "category": "calls",
        "description": "CALLDATALOAD in a tight loop",
        "code": "5B600035506001600056",
        "gas": 100_000_000,
        "input": "0x" + "AA" * 32,
        "repeats": 10,
    },
]

# -------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Run Besu evmtool benchmarks")
    p.add_argument("--evmtool", required=True, help="Path to the evm binary")
    p.add_argument("--genesis", required=True, help="Path to genesis JSON for evmtool")
    p.add_argument("--output", required=True, help="Output JSON path")
    p.add_argument("--besu-sha", required=True)
    p.add_argument("--besu-ref", required=True)
    p.add_argument("--timestamp", default=None)
    return p.parse_args()


def run_single_benchmark(evmtool: str, genesis: str, bench: dict) -> dict:
    """Run one benchmark, parse stdout for MGps / execution time."""
    cmd = [
        evmtool,
        f"--code={bench['code']}",
        "--sender=0xd1cf9d73a91de6630c2bb068ba5fddf9f0deac09",
        "--receiver=0x588108d3eab34e94484d7cda5a1d31804ca96fe7",
        f"--genesis={genesis}",
        f"--gas={bench['gas']}",
        f"--repeat={bench['repeats']}",
    ]
    if bench.get("input"):
        cmd.append(f"--input={bench['input']}")

    print(f"  ▶ {bench['name']} ...", end="", flush=True)
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print(" ⏱ TIMEOUT")
        return _error_result(bench, "timeout")

    elapsed = time.monotonic() - t0

    if result.returncode != 0:
        print(f" ✗ exit {result.returncode}")
        return _error_result(bench, f"exit code {result.returncode}")

    mgps, exec_ms, gas_used = parse_evmtool_output(result.stdout + result.stderr)
    print(f" {mgps:.2f} MGps  ({exec_ms:.1f} ms)")

    return {
        "name": bench["name"],
        "category": bench["category"],
        "description": bench.get("description", ""),
        "status": "ok",
        "score": mgps,
        "score_unit": "MGps",
        "exec_time_ms": exec_ms,
        "gas_used": gas_used,
        "gas_limit": bench["gas"],
        "repeats": bench["repeats"],
        "wall_time_s": round(elapsed, 3),
    }


def parse_evmtool_output(output: str) -> tuple[float, float, int]:
    """Extract MGps, execution time (ms), and gas used from evmtool output."""
    mgps = 0.0
    exec_ms = 0.0
    gas_used = 0

    # evmtool typically prints something like:
    # "Result: xxx  Execution time: yyy ms  MGas/s: zzz"
    for line in output.splitlines():
        m = re.search(r"MGas/s:\s*([\d.]+)", line, re.IGNORECASE)
        if m:
            mgps = float(m.group(1))

        m = re.search(r"Execution time:\s*([\d.]+)\s*ms", line, re.IGNORECASE)
        if m:
            exec_ms = float(m.group(1))

        m = re.search(r"Gas used:\s*(\d+)", line, re.IGNORECASE)
        if m:
            gas_used = int(m.group(1))

    return mgps, exec_ms, gas_used


def _error_result(bench: dict, reason: str) -> dict:
    return {
        "name": bench["name"],
        "category": bench["category"],
        "description": bench.get("description", ""),
        "status": "error",
        "error": reason,
        "score": 0.0,
        "score_unit": "MGps",
    }


def main():
    args = parse_args()

    evmtool = args.evmtool
    genesis = args.genesis

    if not Path(evmtool).exists():
        print(f"ERROR: evmtool binary not found: {evmtool}", file=sys.stderr)
        sys.exit(1)

    if not Path(genesis).exists():
        print(f"ERROR: genesis file not found: {genesis}", file=sys.stderr)
        sys.exit(1)

    timestamp = args.timestamp or datetime.now(timezone.utc).isoformat()

    print(f"\n🚀 Running {len(BENCHMARKS)} evmtool benchmarks...")
    print(f"   Besu ref : {args.besu_ref} ({args.besu_sha})")
    print(f"   Timestamp: {timestamp}\n")

    results = []
    for bench in BENCHMARKS:
        r = run_single_benchmark(evmtool, genesis, bench)
        results.append(r)

    ok = sum(1 for r in results if r.get("status") == "ok")
    errors = len(results) - ok
    print(f"\n✅ {ok} passed  {'⚠️  ' + str(errors) + ' errors' if errors else ''}")

    output_data = {
        "schema_version": "1.0",
        "type": "evmtool",
        "besu_sha": args.besu_sha,
        "besu_ref": args.besu_ref,
        "timestamp": timestamp,
        "total_benchmarks": len(results),
        "benchmarks": results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"📁 Results written to: {out_path}")


if __name__ == "__main__":
    main()
