# Ladybug 0.20.2 rerun with Q11 cache workaround

Preparation started 2026-09-03 21:06:53 UTC. The benchmark runs on `main` at `717a95e2e32b4b3733f62b09973912fbf9d1ccd4`, after PR #13 was merged, with the local Q11 workaround below. The merged lockfile still referenced Ladybug 0.15.3; only that package entry was updated to 0.20.2 before execution.

This reruns all 30 Ladybug queries after applying the query-specific workaround from [Ladybug issue #906](https://github.com/LadybugDB/ladybug/issues/906). Q11 disables `enable_cached_prepared_statement` with `none`, executes the unchanged query, then restores `both` in a `finally` block. Both setting calls use the existing result-materialization/printing helper and are inside Q11's timed function. The other 29 queries retain the PR's dummy-parameter caching behavior. ANALYZE, indexes, query text, expected results and result cleanup are otherwise unchanged.

Ladybug remains exactly 0.20.2 and pytest-benchmark remains 5.2.3. All benchmark options match the [original run](../20260903T204340Z/run-notes.md), including min_rounds=5 and disabled warmup. This is one full-suite process, not an isolated-query run. The existing validated SF1 graph is reused without rebuilding or deleting data; counts/indexes are rechecked. The Neo4j VM stays stopped.

The fresh Ladybug results will be combined with the completed Kuzu, Lance Graph and Neo4j suites in `../20260903T204340Z/` for the current README table. Those three systems are not rerun because their code and data have not changed. Earlier Ladybug failures and isolated-query outputs remain in their original results directory, not in the current README table.

The prior `diagnose_q11.py` dynamically imports the working-tree queries; after this workaround its `pr` mode no longer represents the unmodified PR. Its saved logs and source hash record the earlier failure.

## Result

The full Ladybug suite passed all 30 tests in 22.04 seconds, with no failures or skips. Actual run time: 2026-09-03 21:10:04 to 21:10:27 UTC. Every query has at least five measured rounds (range: 5 to 1,248). Q11 averaged 7.854 ms over 85 rounds, including the two cache-setting calls. Cache restoration on both success and Python exceptions is covered by three passing regression tests in `test_q11_cache_workaround.py`.

The new Ladybug suite plus the three earlier accepted suites gives 120 passing full-suite query results. Their query, benchmark and ingestion source hashes were checked against main and match for all non-Ladybug engines. The README contains only the latest four-engine results. Current CLI outputs are in the top-level `results/` directory; previous CLI outputs are preserved under `results/archived/20260903-before-rerun/`.

Created [follow-up issue #16](https://github.com/prrao87/graph-benchmark-ldbc/issues/16) after the rerun, tracking removal of the Q11 workaround once the upstream fix is released and validated. The user authorized committing and pushing these changes to main. No database files, credentials or virtual environments are included.
