# Local PR #13 benchmark results

Neo4j, Kuzu and Lance Graph each passed all 30 tests: 90 accepted full-suite results, with no skips or failures and at least five measured rounds per query. Ladybug's full suite crashed at Q11 (exit 139); it is not a valid completed run.

Apple M5, 10 logical CPUs, 24 GiB RAM; macOS 26.6.2; Python 3.13.14; pytest-benchmark 5.2.3. Neo4j ran in a native-arm64 Colima VM limited to 4 CPUs and 10 GiB RAM. Embedded engines ran natively with the VM stopped. This compares these local deployment configurations, not equal-resource engine limits.

Graphs were freshly built from the same SF1 CsvBasic dataset. Counts and indexes were checked before timing: 3,181,724 nodes and 17,256,038 relationships per engine.

Ladybug includes PR #13 plus current main: version 0.20.2, ANALYZE before timing, dummy-parameter plan caching, result cleanup, and six ART indexes. This run does not isolate the benefit of any one change.

Mean latency in milliseconds; parenthesized ratios are Neo4j mean / engine mean, so values above 1 mean faster than this Neo4j setup. Calibration is enabled, warmup is disabled, min_rounds=5, max_time=1.0, min_time=0.000005, GC disabled. Query result conversion and printing remain inside the timed functions. These are not controlled cold-cache measurements.

| Query | neo4j-2025.12.1 (ms) | kuzu-0.11.3 (ms) | lance-graph-0.5.4 (ms) |
| --- | ---: | ---: | ---: |
| q1 | 4.098 | 1.716 (2.39x) | 1.281 (3.20x) |
| q2 | 5.082 | 1.313 (3.87x) | 2.266 (2.24x) |
| q3 | 2.018 | 1.023 (1.97x) | 1.840 (1.10x) |
| q4 | 3.141 | 0.855 (3.67x) | 2.912 (1.08x) |
| q5 | 4.244 | 3.419 (1.24x) | 1.986 (2.14x) |
| q6 | 3.145 | 0.705 (4.46x) | 0.706 (4.46x) |
| q7 | 1.508 | 27.588 (0.05x) | 15.430 (0.10x) |
| q8 | 11.720 | 2.651 (4.42x) | 1.139 (10.29x) |
| q9 | 1.782 | 1.712 (1.04x) | 1.878 (0.95x) |
| q10 | 3.514 | 1.511 (2.33x) | 27.044 (0.13x) |
| q11 | 10.935 | 7.735 (1.41x) | 3.043 (3.59x) |
| q12 | 3.888 | 17.120 (0.23x) | 18.705 (0.21x) |
| q13 | 8.398 | 42.157 (0.20x) | 9.465 (0.89x) |
| q14 | 1.288 | 1.464 (0.88x) | 2.432 (0.53x) |
| q15 | 2.603 | 2.299 (1.13x) | 2.114 (1.23x) |
| q16 | 1.418 | 1.735 (0.82x) | 3.910 (0.36x) |
| q17 | 3.119 | 2.553 (1.22x) | 2.220 (1.41x) |
| q18 | 2.739 | 1.441 (1.90x) | 1.741 (1.57x) |
| q19 | 5.189 | 13.232 (0.39x) | 19.478 (0.27x) |
| q20 | 393.291 | 13.666 (28.78x) | 2.828 (139.05x) |
| q21 | 1.336 | 0.445 (3.00x) | 1.456 (0.92x) |
| q22 | 2.618 | 21.507 (0.12x) | 13.224 (0.20x) |
| q23 | 3.081 | 1.151 (2.68x) | 2.510 (1.23x) |
| q24 | 1.291 | 1.191 (1.08x) | 1.706 (0.76x) |
| q25 | 2.579 | 1.388 (1.86x) | 1.308 (1.97x) |
| q26 | 1.222 | 3.280 (0.37x) | 3.014 (0.41x) |
| q27 | 2.518 | 14.305 (0.18x) | 24.665 (0.10x) |
| q28 | 3.033 | 1.457 (2.08x) | 2.547 (1.19x) |
| q29 | 2.359 | 0.965 (2.45x) | 2.645 (0.89x) |
| q30 | 1055.151 | 153.493 (6.87x) | 35.090 (30.07x) |

## Validation

| Engine | Tests passed | Measured rounds per query | Lowest mean count |
| --- | ---: | --- | ---: |
| neo4j-2025.12.1 | 30 | 5 to 42 | 9 |
| kuzu-0.11.3 | 30 | 7 to 789 | 12 |
| lance-graph-0.5.4 | 30 | 29 to 1217 | 9 |

Lowest mean counts describe this single run; they are not significance tests. Full min/median/mean/spread statistics are retained in each engine's JSON and text output. Historical results were not overwritten and should not be treated as a controlled same-machine baseline.

See [run notes](run-notes.md), `*-run.json` for commands, timestamps and package versions, `validate-*.json` for graph checks, and `*.xml` for test outcomes.

## Ladybug isolated-query diagnostics

After the full-suite crash, each of Ladybug's 30 queries was attempted in a separate process with the same benchmark options and unchanged query/assertion code. These runs are diagnostic: process and connection lifetime differ from a full-suite run, so their timings are not included in the comparison above. A crash prevents pytest from writing valid JSON/XML.

| Query | Outcome | Mean (ms) | Rounds |
| --- | --- | ---: | ---: |
| q1 | Passed | 1.193 | 15 |
| q2 | Passed | 0.670 | 13 |
| q3 | Passed | 0.949 | 15 |
| q4 | Passed | 0.296 | 15 |
| q5 | Passed | 3.400 | 13 |
| q6 | Passed | 0.682 | 16 |
| q7 | Passed | 27.476 | 10 |
| q8 | Passed | 2.490 | 14 |
| q9 | Passed | 0.680 | 14 |
| q10 | Passed | 23.537 | 11 |
| q11 | Failed (exit 139) | n/a | n/a |
| q12 | Passed | 25.818 | 7 |
| q13 | Passed | 42.622 | 9 |
| q14 | Passed | 1.575 | 14 |
| q15 | Passed | 2.403 | 14 |
| q16 | Passed | 3.990 | 11 |
| q17 | Passed | 2.535 | 14 |
| q18 | Passed | 1.047 | 15 |
| q19 | Passed | 13.113 | 12 |
| q20 | Passed | 13.338 | 11 |
| q21 | Passed | 0.384 | 14 |
| q22 | Passed | 19.599 | 12 |
| q23 | Passed | 0.447 | 15 |
| q24 | Passed | 0.631 | 11 |
| q25 | Passed | 0.760 | 15 |
| q26 | Passed | 2.786 | 15 |
| q27 | Passed | 15.438 | 12 |
| q28 | Passed | 1.267 | 15 |
| q29 | Passed | 0.464 | 15 |
| q30 | Passed | 370.376 | 5 |

Isolated queries: 29 passed, 1 failed. Failed queries: Q11. The requested 120/120 passing acceptance gate was not met.
