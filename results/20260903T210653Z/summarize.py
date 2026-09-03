"""Combine the latest accepted full suite for each of the four engines."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
EARLIER = OUT.parent / "20260903T204340Z"
SOURCES = {
    "neo4j-2025.12.1": EARLIER,
    "kuzu-0.11.3": EARLIER,
    "ladybug-0.20.2": OUT,
    "lance-graph-0.5.4": EARLIER,
}


def main():
    results = {}
    records = {}
    for label, directory in SOURCES.items():
        record = json.loads((directory / f"{label}-run.json").read_text())
        assert record["accepted"]
        assert record["test_totals"] == {
            "tests": 30,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
        }
        records[label] = record
        data = json.loads((directory / f"{label}.json").read_text())
        results[label] = {b["name"]: b["stats"] for b in data["benchmarks"]}
        assert set(results[label]) == {f"test_benchmark_query{i}" for i in range(1, 31)}
        assert all(stats["rounds"] >= 5 for stats in results[label].values())

    print("# Latest accepted benchmark results: 2026-09-03\n")
    print(
        "All four systems have a completed 30-query suite: 120 passing results with no failures or skips, and at least five measured rounds per query. Ladybug was rerun on main after PR #13 was merged, with the Q11-only cache workaround. The other three suites are from the earlier run on the same machine; their query, benchmark and ingestion source hashes match main.\n"
    )
    print(
        "Apple M5, 10 logical CPUs, 24 GiB RAM, macOS 26.6.2, Python 3.13.14, pytest-benchmark 5.2.3. Neo4j uses a native-arm64 Colima VM with 4 CPUs and 10 GiB RAM. Embedded engines run natively with the VM stopped. These are deployment-specific, not equal-resource or controlled cold-cache comparisons.\n"
    )
    print(
        "Ladybug remains at 0.20.2. Q11 disables the prepared-statement cache, then restores it in a finally block; both setting calls are included in the measured time. Other queries keep caching. Follow-up: [restore caching after upstream #906 is fixed](https://github.com/prrao87/graph-benchmark-ldbc/issues/16).\n"
    )
    print(
        "Mean latency in milliseconds. Ratios are Neo4j mean / engine mean; above 1 means faster than this Neo4j setup.\n"
    )
    print("| Query | " + " | ".join(f"{label} (ms)" for label in SOURCES) + " |")
    print("| --- | " + " | ".join("---:" for _ in SOURCES) + " |")
    for i in range(1, 31):
        name = f"test_benchmark_query{i}"
        means = [results[label][name]["mean"] * 1000 for label in SOURCES]
        row = [f"q{i}", f"{means[0]:.3f}"]
        row.extend(f"{value:.3f} ({means[0] / value:.2f}x)" for value in means[1:])
        print("| " + " | ".join(row) + " |")
    print("\n## Validation\n")
    print("| Engine | Passed | Round range | Source |")
    print("| --- | ---: | --- | --- |")
    for label, directory in SOURCES.items():
        low, high = records[label]["round_range"]
        relative = "" if directory == OUT else "../20260903T204340Z/"
        print(f"| {label} | 30 | {low} to {high} | [JSON]({relative}{label}.json) |")
    print(
        "\nAll graphs have 3,181,724 nodes and 17,256,038 relationships, with expected indexes verified. See [run notes](run-notes.md) for the Q11 workaround and provenance; previous failed and isolated Ladybug runs remain under `../20260903T204340Z/` and are not included in this table."
    )


if __name__ == "__main__":
    main()
