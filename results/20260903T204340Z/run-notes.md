# Local PR #13 benchmark run

Started: 2026-09-03 20:43:40 UTC.

## Provenance

- Branch: `codex/test-pr-13` (local only).
- PR head: `a778f2576e64b47a8d4c578db569667ff5d1c4cd`.
- Main merged: `affd9586f728f77299682df44138d7c506b09bf5`.
- Local merge: `a26379a56311d3f979055010469e09af8b8358c3`.
- Only package version changed from the original lockfile: Ladybug 0.15.3 → 0.20.2.
- Ladybug dependency pinned to `==0.20.2`; all other package versions retained.
- Host: Apple M5, 10 logical CPUs, 24 GiB memory, macOS 26.6.2 (25G83), arm64.
- Neo4j runtime: dedicated Colima profile `ldbc-benchmark`, 4 CPUs, 10 GiB memory, 100 GiB virtual disk; native arm64 with Apple Virtualization.
- Neo4j image: `neo4j:2025.12.1`; existing Compose heap/page-cache settings retained, Bolt bound to `127.0.0.1:7687`.
- Verified image digest: `neo4j@sha256:c64d8750884c95ae57441a103d64d08fdaf55265acc3af687aa8ec25aa77d0c3`, architecture `arm64`.
- Python 3.13.14; pytest 9.0.2; pytest-benchmark 5.2.3; Kuzu 0.11.3; lance-graph 0.5.4; pylance 1.0.4; Neo4j Python driver 6.1.0. Full package inventory: `environment.txt`.
- Dataset: https://datasets.ldbcouncil.org/snb-interactive-v1/social_network-sf1-CsvBasic-StringDateFormatter.tar.zst
- Downloaded archive SHA256: `5d74f5b0b0570eb593b3317e14ffab3d5dd181efb7e2c947e0ed0409c377b23d` (recorded locally; no upstream checksum supplied).

## Measurement contract

Each engine runs all 30 tests in its own process. Order: Ladybug, Kuzu, Lance Graph, Neo4j. No concurrent ingestion/benchmarks; Neo4j VM stopped during embedded-engine measurements. PR #13's statistics, dummy-parameter plan caching, result cleanup, and main's secondary indexes are tested together; this is not an ANALYZE-only comparison.

```sh
uv run --frozen pytest benchmark_query.py \
  --benchmark-min-rounds=5 \
  --benchmark-min-time=0.000005 \
  --benchmark-max-time=1.0 \
  --benchmark-timer=time.perf_counter \
  --benchmark-calibration-precision=10 \
  --benchmark-warmup=off \
  --benchmark-warmup-iterations=5 \
  --benchmark-disable-gc \
  --benchmark-sort=fullname
```

JSON and JUnit output arguments are appended for evidence. The round count is at least five per query, not exactly five. Warmup remains disabled. Existing assertions, result materialization and timed printing are unchanged.

## Setup events

- Dataset downloaded and extracted successfully with the repository script.
- Installed Colima 0.10.3, Lima 2.2.0, Docker CLI 29.7.2, and Compose 5.5.1.
- Initial Ladybug build attempt stopped before execution because the sandbox could not access the uv cache. Retained `build-ladybug.log`; retry requested normal authorized cache access.
- Fresh Ladybug, Kuzu and Lance Graph builds succeeded. All 31 graph table counts match the documented SF1 counts. Ladybug's eight primary-key indexes and six ART indexes, Kuzu's primary keys, and Lance's eight ID BTree indexes were verified.
- Verified Neo4j was empty before ingestion; only the dedicated `ldbc-benchmark` Compose project's volumes are used.
- Per the user's follow-up, the root README will be updated after completion. Historical raw outputs and the original heatmap will remain unchanged.

## Status

All four databases were built and passed counts/index validation. Neo4j node ingestion took 57.9698 seconds and relationship ingestion took 241.0531 seconds. Its VM was confirmed stopped before embedded measurements.

Ladybug's full-suite attempt crashed with a native segmentation fault while timing Q11, after ten tests passed. Exit code: 139. The crash prevented pytest from completing benchmark JSON and writing JUnit results; `ladybug-0.20.2.txt` and `ladybug-0.20.2-run.json` preserve the failure. Its zero-byte JSON file is retained as failure evidence, not valid measurements. No partial Ladybug timings are accepted as a complete run.

Kuzu, Lance Graph and Neo4j each passed all 30 tests with the requested options and at least five rounds. A filtered native crash report is saved in `ladybug-native-crash.json`; it records EXC_BAD_ACCESS / SIGSEGV in Ladybug's native module, with prepared-statement execution frames. That stack alone does not establish the cause.

## Ladybug failure diagnosis

- Q11 alone also segfaulted with exit 139 under the unchanged pytest benchmark configuration (`ladybug-0.20.2-q11.*`).
- To ensure no query remained unattempted, all other Ladybug queries ran in separate processes with the same options and unchanged benchmark/query source. All 29 passed. These diagnostic timings are reported separately because the connection/process lifetime differs from a full-suite run.
- `diagnose_q11.py pr` returned the correct Q11 result once, then segfaulted on iteration 2 (exit 139).
- `diagnose_q11.py without-dummy` passed 20 repetitions with the correct result (exit 0). The only execution-path difference between these diagnostic modes is omitting the dummy parameter; both retain ANALYZE, result conversion and explicit result cleanup.
- Q11's expected result is `[{"num_e": 190, "o.name": "MDLR_Airlines"}]`.
- This isolates a reproducible cached-execution trigger on this environment, not the native defect or its applicability to other platforms. The benchmark source still contains all original PR changes; no workaround was applied.

## Completion

- All 120 engine/query combinations were attempted. There are 90 passing full-suite results plus 29 passing isolated Ladybug tests; Q11 remains a reproducible native crash. The 120/120 full-suite acceptance gate was not met.
- Full-suite measured-round ranges: Kuzu 7 to 789, Lance Graph 29 to 1217, Neo4j 5 to 42. Isolated successful Ladybug queries each have at least five rounds.
- The root README contains only the latest results, environment and failure explanation. Historical CLI outputs remain in `results/` and `results/archived/`; the old heatmap file is retained but no longer displayed in the README.
- Neo4j counts/indexes were rechecked after its restart. After its benchmark, the container was stopped with a 120-second graceful-stop allowance, then Colima was stopped. The VM stayed stopped during Ladybug diagnostics. Data volumes were retained.
- Nothing was pushed; the contributor's PR was not modified. All additional changes remain local.
- Final checks passed: Ruff checks/formatting on the four run helpers, `git diff --check`, exact README-to-JSON table agreement, package-version delta limited to Ladybug, and 119 passing test results with at least five measured rounds. Final runtime status is retained in `runtime-final-state.txt`.

## Reproduction

From the repository root, the focused crash check is:

```sh
uv run --frozen python -u -X faulthandler results/20260903T204340Z/diagnose_q11.py pr
uv run --frozen python -u -X faulthandler results/20260903T204340Z/diagnose_q11.py without-dummy
```

The graph must already exist. `run_benchmark.py` refuses to overwrite existing evidence; use a new timestamped directory for another benchmark campaign. To resume the dedicated Neo4j server, start Colima profile `ldbc-benchmark`, then use `DOCKER_CONTEXT=colima-ldbc-benchmark docker-compose -p ldbc-benchmark -f neo4j/docker-compose.yml --env-file neo4j/.env start`.
