## Follow-up

Restore Q11's prepared-statement caching once a Ladybug release containing the fix for https://github.com/LadybugDB/ladybug/issues/906 is available and verified locally.

## Current workaround

With Ladybug 0.20.2, Q11 returns the expected result once, then segfaults on repeated cached execution. The temporary workaround in `ladybugdb/query.py` sets `enable_cached_prepared_statement='none'` around Q11 and restores `'both'` in a `finally` block. The other queries retain the dummy-parameter caching path. ANALYZE, secondary indexes, query text and result cleanup are unchanged.

The local full Ladybug suite passed all 30 tests on main at `717a95e2e32b4b3733f62b09973912fbf9d1ccd4` plus this workaround, using Ladybug 0.20.2 and pytest-benchmark 5.2.3 with `min_rounds=5`, `max_time=1.0`, `min_time=0.000005`, disabled GC and disabled warmup. Host: Apple M5, macOS 26.6.2, Python 3.13.14. Q11 averaged 7.854 ms over 85 rounds; its timing includes the cache-disable and cache-restore calls.

## Acceptance criteria

- [ ] Confirm the upstream fix is included in the Ladybug version being tested; issue closure alone is not sufficient.
- [ ] Update the dependency/lockfile to that release without unrelated package upgrades.
- [ ] Remove only Q11's temporary cache toggles, restoring the same cached execution path used by the other queries.
- [ ] Verify at least 20 consecutive cached Q11 executions on one connection without crashing, returning `[{"num_e": 190, "o.name": "MDLR_Airlines"}]` each time.
- [ ] Rerun all 30 Ladybug benchmarks in one process with the same settings and at least five measured rounds per query. Retain the current result assertions.
- [ ] Save CLI/JSON results, update the README's Ladybug column and remove the workaround note. Preserve previous raw outputs under `results/`.

Until then, retain the Q11-only workaround and its cache-restoration regression tests.
