# Graphistry with Polars Backend

This directory benchmarks the LDBC SNB SF1 dataset using [PyGraphistry](https://github.com/graphistry/pygraphistry) with a [Polars](https://pola.rs/) backend. Instead of running against a graph database server, PyGraphistry's GFQL (Graphistry Graph Query Language) engine executes Cypher queries directly against in-memory Polars DataFrames.

All timing numbers shown below are on an M3 Macbook Pro with 32 GB of RAM.

## Setup

```sh
# Graphistry with Polars support is needed
uv add 'graphistry[polars]'
```

All dependencies are managed via `uv sync` from the repository root.

## Build the graph

The `build_graph.py` script reads the pipe-delimited CSV files under `../csv/`,
normalises them into a unified **nodes** table and a unified **edges** table,
adds boolean label columns for GFQL Cypher compatibility, and writes them as
Parquet files for fast reloading.

```sh
cd graphistry && uv run build_graph.py
```

The output is written to `graphistry/graph_data/nodes.parquet` and
`graphistry/graph_data/edges.parquet`.

## Execute queries

The query suite currently supports queries 1-6 (queries 7-30 are not yet
supported by GFQL's Cypher engine). Each query is written in Cypher and
executed via PyGraphistry's GFQL engine on the Polars backend.

Run the full supported query suite:

```bash
cd graphistry && uv run query.py
```

Run a subset by passing a comma-separated list of query numbers:

```bash
uv run query.py "1,2,6"
```

## Run benchmark

The benchmark uses `pytest-benchmark` to measure each query's execution time.

```bash
uv run pytest graphistry/benchmark_query.py \
  --benchmark-min-rounds=5 \
  --benchmark-warmup-iterations=5 \
  --benchmark-disable-gc \
  --benchmark-sort=fullname
```

Or from the `graphistry` directory:

```bash
cd graphistry && uv run pytest benchmark_query.py \
  --benchmark-min-rounds=5 \
  --benchmark-warmup-iterations=5 \
  --benchmark-disable-gc \
  --benchmark-sort=fullname
```

### Expected output format

```
========================================== test session starts ===========================================
platform darwin -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=True min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=5)
rootdir: /Users/user/code/graph-benchmark-ldbc-snb
configfile: pyproject.toml
plugins: anyio-4.12.1, benchmark-5.2.3, asyncio-1.3.0, Faker-40.1.2
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 6 items

benchmark_query.py ......                                                  [100%]
```

## How it works

1. **build_graph.py** reads each node CSV (Person, Comment, Post, Forum, Tag, Tagclass, Place, Organisation) and each edge CSV (knows, hasInterest, etc.), normalises column names, casts `id`/`src`/`dst` to `Int64`, and concatenates them into two unified Polars DataFrames. Node ``:Label`` matching uses boolean ``label__<Label>`` columns; edge ``[:REL_TYPE]`` matching filters the single ``type`` string column (GFQL's discriminator_key="type"), so no per-relationship boolean columns are needed.

2. **query.py** loads the unified DataFrames and creates a PyGraphistry graph object via `graphistry.edges(edges, 'src', 'dst').nodes(nodes, 'id')`. Each supported query is implemented as a GFQL Cypher string executed via `g.gfql(cypher, params=..., engine='polars')`.

3. **benchmark_query.py** wraps each query in a `pytest-benchmark` test with the same expected-result assertions as the other backends (Ladybug, Kuzu, lance-graph, Neo4j) for cross-validation.

## Performance notes

Each query takes ~445 ms on the SF1 graph (3.1 M nodes, 17 M edges). Two
issues that were inflating this were fixed:

1. **ID prefix hack (removed).** An earlier version prefixed node IDs with
   their type as strings (e.g. `"Person:933"`) to avoid across-type ID
   collisions in the unified nodes table. This forced *string* joins on 17 M
   edges and added `~150 ms`. IDs are now native `Int64`; GFQL's `:Label`
   filter restricts to one node type *before* the id join, so within-type
   uniqueness is sufficient and cross-type collisions are resolved by the
   label filter.

2. **Unused `rel__*` boolean columns (removed).** GFQL Cypher `[:REL_TYPE]`
   filters the `type` string column, not per-relationship `rel__<Rel>` boolean
   columns. The 23 redundant boolean columns (≈400 MB) were dropped; edges
   went from 1.4 GB → 1.0 GB.

### Why aren't GFQL's physical indexes helping? (verified)

PyGraphistry *does* ship pay-as-you-go GFQL physical indexes
(`g.create_index('edge_out_adj' | 'edge_in_adj' | 'node_id')`, or `g.gfql_index_all()`).
They are **opt-in and not built by** `graphistry.edges(...).nodes(...)` — by default
`index_policy="use"` and the index registry is empty, so `maybe_index_hop` bails and
every query is a full O(E) scan. Confirmed empirically: the two edge-adjacency
indexes build in ~3 s over 17 M edges (matching the "~5 s" build cost), but **do
not reduce Q1–Q6** for two independent reasons:

1. **The queries are index-non-coverable by shape.** `g.gfql_explain(...)` reports
   `used_index=False, reason='query not index-coverable'` for Q1–Q6 under every
   policy (`use`/`force`). The index planner (`_hop_is_index_coverable`) only routes
   the *seeded single-hop* shape \u2014 `MATCH (a {id:\u2026})-[e]->(b)` with an
   **untyped** edge (`edge_match is None`), a single id seed, and no two-sided
   WHERE. Our queries use **typed edges** (`-[:workAt]->`, `-[:personIsLocatedIn]->`,
   \u2026) and two-side WHERE predicates (`o.name=\u2026 AND p.lastname CONTAINS\u2026`),
   which set `edge_match`/row-predicates and are rejected. (A typed edge is only
   coverable as a wavefront scan, not via the index.) Forcing `index_policy='force'`
   therefore makes Q6 *slower* (445 ms \u2192 3.4 s) \u2014 the index sits idle while
   the registry attach adds overhead.

2. **The `node_id` index cannot be built at all.** It requires globally-unique node
   ids, but LDBC ids collide across node types (e.g. `Comment:557` and `Place:557`).
   Restoring the old string-prefix hack would satisfy this one index, but these
   queries don\u2019t use the `node_id` index path, so it wouldn\u2019t help.

Even the index\u2019s *canonical* shape, `MATCH (a {id:N})-[e]->(b)`, shows **no**
speedup here with the index resident (~940 ms on vs off): the index accelerates the
edge lookup (O(degree) vs O(E)) but the plan still funnels through the order-stable
combine that `with_row_index()` + `collect_all`s the **full** 3.1 M-node frame per
query, which dominates. We therefore deliberately do **not** build the indexes for
this benchmark\u2014they\u2019re cheap to build but cannot accelerate typed-edge,
two-side-filter Cypher, and forcing them adds overhead.

### The combine/collect floor

The remaining ~445 ms is structural to GFQL's Polars backend: every
edge-traversing Cypher query runs three `collect_all` passes (hop + order-stable
combine + RETURN row-pipeline) that scan/join the **full** 17 M-edge +
3.1 M-node graph. The equivalent hand-written Polars join runs in ~8 ms, so this is
GFQL's wavefront/combine overhead, not the data. It is not fixable from the
benchmark side; it is inherent to the current GFQL Polars engine, and the
benchmark reflects GFQL's real performance on this workload (vs the indexed
graph DBs at 1–50 ms).

## Architecture

```
graphistry/
├── README.md               ← This file
├── build_graph.py          ← CSV → unified Polars DataFrames + labels
├── query.py                ← GFQL Cypher queries (Q1-Q6 supported)
├── benchmark_query.py      ← pytest-benchmark test suite
└── graph_data/             ← Built Parquet files (gitignored)
    ├── nodes.parquet
    └── edges.parquet
```

## Supported queries

| Query | Description | Status |
|-------|-------------|--------|
| Q1 | People in Glasgow interested in Napoleon | ✅ |
| Q2 | Posts by Lei Zhang containing "Zulu" | ✅ |
| Q3 | Creator of post ID 962077547172 and their studies | ✅ |
| Q4 | Comments by Alfredo Gomez with length > 100 | ✅ |
| Q5 | Forum members with last name Choi | ✅ |
| Q6 | Nova_Air employees with last name containing Bravo | ✅ |
| Q7–Q30 | Complex multi-hop / aggregation queries | ❌ (GFQL limitation) |
