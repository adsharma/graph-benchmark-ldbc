"""Summarize accepted full suites separately from Ladybug crash diagnostics."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
LABELS = ["neo4j-2025.12.1", "kuzu-0.11.3", "lance-graph-0.5.4"]


def main():
    results = {}
    records = {}
    for label in LABELS:
        records[label] = json.loads((OUT / f"{label}-run.json").read_text())
        assert records[label]["accepted"], f"Unaccepted run: {label}"
        raw = json.loads((OUT / f"{label}.json").read_text())
        results[label] = {b["name"]: b["stats"] for b in raw["benchmarks"]}
        assert len(results[label]) == 30

    print("# Local PR #13 benchmark results\n")
    print(
        "Neo4j, Kuzu and Lance Graph each passed all 30 tests: 90 accepted full-suite results, with no skips or failures and at least five measured rounds per query. Ladybug's full suite crashed at Q11 (exit 139); it is not a valid completed run.\n"
    )
    print(
        "Apple M5, 10 logical CPUs, 24 GiB RAM; macOS 26.6.2; Python 3.13.14; pytest-benchmark 5.2.3. Neo4j ran in a native-arm64 Colima VM limited to 4 CPUs and 10 GiB RAM. Embedded engines ran natively with the VM stopped. This compares these local deployment configurations, not equal-resource engine limits.\n"
    )
    print(
        "Graphs were freshly built from the same SF1 CsvBasic dataset. Counts and indexes were checked before timing: 3,181,724 nodes and 17,256,038 relationships per engine.\n"
    )
    print(
        "Ladybug includes PR #13 plus current main: version 0.20.2, ANALYZE before timing, dummy-parameter plan caching, result cleanup, and six ART indexes. This run does not isolate the benefit of any one change.\n"
    )
    print(
        "Mean latency in milliseconds; parenthesized ratios are Neo4j mean / engine mean, so values above 1 mean faster than this Neo4j setup. Calibration is enabled, warmup is disabled, min_rounds=5, max_time=1.0, min_time=0.000005, GC disabled. Query result conversion and printing remain inside the timed functions. These are not controlled cold-cache measurements.\n"
    )
    print("| Query | " + " | ".join(f"{label} (ms)" for label in LABELS) + " |")
    print("| --- | " + " | ".join("---:" for _ in LABELS) + " |")
    wins = dict.fromkeys(LABELS, 0)
    for i in range(1, 31):
        query = f"test_benchmark_query{i}"
        means = [results[label][query]["mean"] * 1000 for label in LABELS]
        row = [f"q{i}", f"{means[0]:.3f}"]
        row.extend(f"{value:.3f} ({means[0] / value:.2f}x)" for value in means[1:])
        print("| " + " | ".join(row) + " |")
        wins[LABELS[min(range(len(means)), key=means.__getitem__)]] += 1
    print("\n## Validation\n")
    print("| Engine | Tests passed | Measured rounds per query | Lowest mean count |")
    print("| --- | ---: | --- | ---: |")
    for label in LABELS:
        low, high = records[label]["round_range"]
        print(f"| {label} | 30 | {low} to {high} | {wins[label]} |")
    print(
        "\nLowest mean counts describe this single run; they are not significance tests. Full min/median/mean/spread statistics are retained in each engine's JSON and text output. Historical results were not overwritten and should not be treated as a controlled same-machine baseline.\n"
    )
    print(
        "See [run notes](run-notes.md), `*-run.json` for commands, timestamps and package versions, `validate-*.json` for graph checks, and `*.xml` for test outcomes."
    )
    print("\n## Ladybug isolated-query diagnostics\n")
    print(
        "After the full-suite crash, each of Ladybug's 30 queries was attempted in a separate process with the same benchmark options and unchanged query/assertion code. These runs are diagnostic: process and connection lifetime differ from a full-suite run, so their timings are not included in the comparison above. A crash prevents pytest from writing valid JSON/XML.\n"
    )
    print("| Query | Outcome | Mean (ms) | Rounds |")
    print("| --- | --- | ---: | ---: |")
    passed = []
    failed = []
    for i in range(1, 31):
        label = f"ladybug-0.20.2-q{i}"
        record = json.loads((OUT / f"{label}-run.json").read_text())
        if record["accepted"]:
            raw = json.loads((OUT / f"{label}.json").read_text())
            stats = raw["benchmarks"][0]["stats"]
            print(f"| q{i} | Passed | {stats['mean'] * 1000:.3f} | {stats['rounds']} |")
            passed.append(i)
        else:
            print(f"| q{i} | Failed (exit {record['exit_code']}) | n/a | n/a |")
            failed.append(i)
    print(
        f"\nIsolated queries: {len(passed)} passed, {len(failed)} failed. Failed queries: {', '.join('Q' + str(i) for i in failed)}. The requested 120/120 passing acceptance gate was not met."
    )


if __name__ == "__main__":
    main()
