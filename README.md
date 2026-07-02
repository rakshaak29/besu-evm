#  Hyperledger Besu EVM Performance Benchmarking

Welcome to the **Besu EVM Benchmarking** repository! This project serves as a continuous performance tracking and regression-detection harness for the Hyperledger Besu Ethereum Virtual Machine (EVM).

Whether you are looking to benchmark a new EVM feature, check the throughput of gas operations (MGas/s), or visualize performance trends over time, this project brings everything under a single dashboard.

---

##  Table of Contents
- [ Key Features](#-key-features)
- [ Repository Structure](#-repository-structure)
- [ Quick Start (Local Run)](#-quick-start-local-run)
- [ How It Works Under the Hood](#-how-it-works-under-the-hood)
  - [1. Low-level `evmtool` Benchmarks](#1-low-level-evmtool-benchmarks)
  - [2. JMH Microbenchmarks](#2-jmh-microbenchmarks)
  - [3. Dashboard Aggregator](#3-dashboard-aggregator)
  - [4. Result Comparator](#4-result-comparator)
- [ CI/CD & Automated Pipelines](#-cicd--automated-pipelines)
  - [ Weekly Performance Runs](#-weekly-performance-runs)
  - [ Pull Request Regression Checks](#-pull-request-regression-checks)
- [ Extending the Benchmarks](#️-extending-the-benchmarks)

---

##  Key Features

* **Dual-Engine Benchmarking**: 
  * Run low-level instructions directly on the `evmtool` binary to measure throughput in Millions of Gas per second (**MGas/s** or **MGps**).
  * Run standard Java Microbenchmark Harness (**JMH**) tests embedded in Hyperledger Besu's core.
* **Interactive Visual Dashboard**: A modern, responsive, zero-dependency static dashboard (Chart.js + vanilla JS/CSS) to explore history, inspect specific category performance, and quickly spot regressions.
* **Automatic Pull Request Auditing**: CI checks run on pull requests (triggered via label) to compare bytecode executions against base branches and post sticky comparison comments with visual regression indicators (🔴/🟢).

---

##  Repository Structure

Below is a map of the repository to help you navigate:

```
besu-evm/
├── .github/
│   └── workflows/
│       ├── pr-benchmark-check.yml  # Run benchmarks on PRs & post comparisons
│       └── run-benchmarks.yml      # Weekly run scheduler & GitHub Pages deployer
├── dashboard/                      # Web-based frontend visualization
│   ├── css/
│   │   └── styles.css              # Custom dashboard layout & design
│   ├── data/                       # Compiled historical JSON files (Gitignored/populated)
│   │   ├── index.json              # Latest runs & active regressions metadata
│   │   └── trends.json             # Historical datapoints for line charts
│   ├── js/
│   │   └── app.js                  # Frontend state management & Chart.js rendering
│   └── index.html                  # Main dashboard page
├── results/
│   └── history/                    # Historical JSON files representing runs
│       └── 20250224_000000_evmtool.json
├── scripts/                        # Python orchestrators & parsers
│   ├── build_dashboard_data.py     # Aggregates raw JSON files for the dashboard
│   ├── compare_results.py          # Compares base/PR runs for PR reports
│   ├── generate_sample_data.py     # Helper to populate local test histories
│   ├── parse_jmh.py                # Standardizes raw JMH JSON outputs
│   └── run_evmtool_benchmarks.py   # Drives evmtool with custom opcode loops
├── netlify.toml                    # Netlify deployment configuration
└── README.md                       # This file!
```

---

##  Quick Start (Local Run)

Want to see the dashboard locally or run a quick benchmark test? Follow these steps:

### 1. Prerequisites
Make sure you have **Python 3.x** installed. If you want to run `evmtool` or JMH benchmarks, you will also need **Java 21** and a local clone of [Hyperledger Besu](https://github.com/hyperledger/besu).

### 2. Populate Sample Data
If you just cloned this repository and want to explore the dashboard locally, compile the mock data using the sample generator:
```bash
# Generate mock JSON run reports under results/history/
python3 scripts/generate_sample_data.py

# Aggregate the raw results into the frontend data schema
python3 scripts/build_dashboard_data.py
```

### 3. Open the Dashboard
Since the dashboard fetches client-side JSON files, start a quick local HTTP server to avoid CORS blocks:
```bash
# Start a simple python web server inside the dashboard directory
cd dashboard
python3 -m http.server 8000
```
Now, open your browser and navigate to `http://localhost:8000` to view the interactive charts and trend lines!

---

##  How It Works Under the Hood

### 1. Low-level `evmtool` Benchmarks
* **File**: [`scripts/run_evmtool_benchmarks.py`](file:///Users/rakshaak/.gemini/antigravity-ide/scratch/besu-evm/scripts/run_evmtool_benchmarks.py)
* **What it does**: Drives Besu's `evmtool` CLI. It defines tight loops of specific EVM bytecode operations (e.g. arithmetic `ADD`/`MUL`/`EXP`, memory manipulation `MSTORE`/`MLOAD`, and cryptography `SHA3_32B`).
* **Metric**: Throughput is calculated using the total gas consumed over the execution time (`MGas/s`). 

### 2. JMH Microbenchmarks
* **File**: [`scripts/parse_jmh.py`](file:///Users/rakshaak/.gemini/antigravity-ide/scratch/besu-evm/scripts/parse_jmh.py)
* **What it does**: Besu comes with built-in JMH tests. This script parses raw JSON files produced by JMH running in Besu into our standardized benchmark format.
* **Metric**: Operations per second (`ops/s`).

### 3. Dashboard Aggregator
* **File**: [`scripts/build_dashboard_data.py`](file:///Users/rakshaak/.gemini/antigravity-ide/scratch/besu-evm/scripts/build_dashboard_data.py)
* **What it does**: Loops through all JSON records inside `results/history/`. It builds two main indices:
  * `index.json`: Contains latest run stats, a list of all historical runs, active regressions (performance changes exceeding the designated threshold), and the latest values.
  * `trends.json`: Chronologically ordered historic values grouped by benchmark name.

### 4. Result Comparator
* **File**: [`scripts/compare_results.py`](file:///Users/rakshaak/.gemini/antigravity-ide/scratch/besu-evm/scripts/compare_results.py)
* **What it does**: Compares two benchmark runs. If the score change exceeds a specified percentage (e.g., `-5.0%`), it flags a performance regression. It automatically prints a markdown report suited for posting on GitHub PRs.

---

##  CI/CD & Automated Pipelines

This repository is designed to be fully automated.

### 📈 Weekly Performance Runs
* **Workflow**: `.github/workflows/run-benchmarks.yml`
* **Trigger**: Automatically runs every Monday at `00:00 UTC`, or can be triggered manually.
* **Actions**: 
  1. Clones `hyperledger/besu` on the `main` branch.
  2. Builds `evmtool` and the JMH test JAR.
  3. Executes the full suite of benchmarks.
  4. Parses results and saves the new JSON into `results/history/`.
  5. Re-runs the aggregator `build_dashboard_data.py`.
  6. Commits the results to git and deploys the new dashboard code to GitHub Pages.

###  Pull Request Regression Checks
* **Workflow**: `.github/workflows/pr-benchmark-check.yml`
* **Trigger**: Triggered on any Besu-related PR when a repository maintainer adds the `run-benchmarks` label.
* **Actions**:
  1. Clones both the base branch and the PR branch of Hyperledger Besu.
  2. Builds `evmtool` binaries for both branches.
  3. Executes benchmarks on both versions to get identical baselines.
  4. Compares PR results vs. Base results using `compare_results.py`.
  5. Posts an automated, sticky comment outlining performance differences and flagging any performance regressions.

---

##  Extending the Benchmarks

To add a new EVM bytecode opcode test:
1. Open [`scripts/run_evmtool_benchmarks.py`](file:///Users/rakshaak/.gemini/antigravity-ide/scratch/besu-evm/scripts/run_evmtool_benchmarks.py).
2. Find the `BENCHMARKS` array.
3. Append your definition structure:
   ```python
   {
       "name": "YOUR_OPCODE_NAME",
       "category": "arithmetic", # or bitwise, stack, memory, crypto, calls
       "description": "Short explanation of the loop logic",
       "code": "5B6001...",       # Hex representation of EVM bytecode
       "gas": 100_000_000,
       "input": "",              # Hex input payload if needed
       "repeats": 10,
   }
   ```
4. Run the benchmark tool locally to verify correctness!
