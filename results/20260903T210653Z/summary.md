# Latest accepted benchmark results: 2026-09-03

All four systems have a completed 30-query suite: 120 passing results with no failures or skips, and at least five measured rounds per query. Ladybug was rerun on main after PR #13 was merged, with the Q11-only cache workaround. The other three suites are from the earlier run on the same machine; their query, benchmark and ingestion source hashes match main.

Apple M5, 10 logical CPUs, 24 GiB RAM, macOS 26.6.2, Python 3.13.14, pytest-benchmark 5.2.3. Neo4j uses a native-arm64 Colima VM with 4 CPUs and 10 GiB RAM. Embedded engines run natively with the VM stopped. These are deployment-specific, not equal-resource or controlled cold-cache comparisons.

Ladybug remains at 0.20.2. Q11 disables the prepared-statement cache, then restores it in a finally block; both setting calls are included in the measured time. Other queries keep caching. Follow-up: [restore caching after upstream #906 is fixed](https://github.com/prrao87/graph-benchmark-ldbc/issues/16).

Mean latency in milliseconds. Ratios are Neo4j mean / engine mean; above 1 means faster than this Neo4j setup.

| Query | neo4j-2025.12.1 (ms) | kuzu-0.11.3 (ms) | ladybug-0.20.2 (ms) | lance-graph-0.5.4 (ms) |
| --- | ---: | ---: | ---: | ---: |
| q1 | 4.098 | 1.716 (2.39x) | 1.240 (3.30x) | 1.281 (3.20x) |
| q2 | 5.082 | 1.313 (3.87x) | 0.591 (8.59x) | 2.266 (2.24x) |
| q3 | 2.018 | 1.023 (1.97x) | 0.820 (2.46x) | 1.840 (1.10x) |
| q4 | 3.141 | 0.855 (3.67x) | 0.213 (14.78x) | 2.912 (1.08x) |
| q5 | 4.244 | 3.419 (1.24x) | 3.300 (1.29x) | 1.986 (2.14x) |
| q6 | 3.145 | 0.705 (4.46x) | 0.537 (5.85x) | 0.706 (4.46x) |
| q7 | 1.508 | 27.588 (0.05x) | 27.028 (0.06x) | 15.430 (0.10x) |
| q8 | 11.720 | 2.651 (4.42x) | 2.380 (4.93x) | 1.139 (10.29x) |
| q9 | 1.782 | 1.712 (1.04x) | 0.631 (2.82x) | 1.878 (0.95x) |
| q10 | 3.514 | 1.511 (2.33x) | 21.157 (0.17x) | 27.044 (0.13x) |
| q11 | 10.935 | 7.735 (1.41x) | 7.854 (1.39x) | 3.043 (3.59x) |
| q12 | 3.888 | 17.120 (0.23x) | 25.097 (0.15x) | 18.705 (0.21x) |
| q13 | 8.398 | 42.157 (0.20x) | 41.832 (0.20x) | 9.465 (0.89x) |
| q14 | 1.288 | 1.464 (0.88x) | 1.697 (0.76x) | 2.432 (0.53x) |
| q15 | 2.603 | 2.299 (1.13x) | 2.377 (1.09x) | 2.114 (1.23x) |
| q16 | 1.418 | 1.735 (0.82x) | 3.943 (0.36x) | 3.910 (0.36x) |
| q17 | 3.119 | 2.553 (1.22x) | 2.453 (1.27x) | 2.220 (1.41x) |
| q18 | 2.739 | 1.441 (1.90x) | 0.999 (2.74x) | 1.741 (1.57x) |
| q19 | 5.189 | 13.232 (0.39x) | 11.623 (0.45x) | 19.478 (0.27x) |
| q20 | 393.291 | 13.666 (28.78x) | 13.172 (29.86x) | 2.828 (139.05x) |
| q21 | 1.336 | 0.445 (3.00x) | 0.324 (4.12x) | 1.456 (0.92x) |
| q22 | 2.618 | 21.507 (0.12x) | 19.023 (0.14x) | 13.224 (0.20x) |
| q23 | 3.081 | 1.151 (2.68x) | 0.387 (7.97x) | 2.510 (1.23x) |
| q24 | 1.291 | 1.191 (1.08x) | 0.546 (2.37x) | 1.706 (0.76x) |
| q25 | 2.579 | 1.388 (1.86x) | 0.685 (3.77x) | 1.308 (1.97x) |
| q26 | 1.222 | 3.280 (0.37x) | 2.738 (0.45x) | 3.014 (0.41x) |
| q27 | 2.518 | 14.305 (0.18x) | 15.408 (0.16x) | 24.665 (0.10x) |
| q28 | 3.033 | 1.457 (2.08x) | 1.183 (2.56x) | 2.547 (1.19x) |
| q29 | 2.359 | 0.965 (2.45x) | 0.418 (5.65x) | 2.645 (0.89x) |
| q30 | 1055.151 | 153.493 (6.87x) | 354.873 (2.97x) | 35.090 (30.07x) |

## Validation

| Engine | Passed | Round range | Source |
| --- | ---: | --- | --- |
| neo4j-2025.12.1 | 30 | 5 to 42 | [JSON](../20260903T204340Z/neo4j-2025.12.1.json) |
| kuzu-0.11.3 | 30 | 7 to 789 | [JSON](../20260903T204340Z/kuzu-0.11.3.json) |
| ladybug-0.20.2 | 30 | 5 to 1248 | [JSON](ladybug-0.20.2.json) |
| lance-graph-0.5.4 | 30 | 29 to 1217 | [JSON](../20260903T204340Z/lance-graph-0.5.4.json) |

All graphs have 3,181,724 nodes and 17,256,038 relationships, with expected indexes verified. See [run notes](run-notes.md) for the Q11 workaround and provenance; previous failed and isolated Ladybug runs remain under `../20260903T204340Z/` and are not included in this table.
