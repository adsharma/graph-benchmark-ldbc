"""
LDBC SNB SF1 benchmark queries using PyGraphistry GFQL with a Polars backend.

GFQL is under active development. Only queries 1-6 are currently supported;
the remaining queries will be added as the Cypher engine matures.

Each ``run_queryN`` function returns a ``polars.DataFrame``.

Column naming notes:
  - Property access is case-sensitive and matches the lowercase column name.
  - Node ``:Label`` maps to ``label__<Label>`` boolean columns.
  - Edge ``[:REL_TYPE]`` filters the ``type`` string column (GFQL
    discriminator_key="type") — no per-rel boolean columns needed.
  - IDs (``id``/``src``/``dst``) are native Int64 for fast integer joins.
  - Organisation's original CSV ``type`` column is renamed to ``original_type``.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Add this directory to the path for local imports without shadowing
# the installed `graphistry` (pygraphistry) library.
_SCRIPT_ROOT = Path(__file__).resolve().parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

import graphistry
import pandas as pd
import polars as pl

import build_graph

SCRIPT_ROOT = _SCRIPT_ROOT

POOL: dict[str, Any] = {}


def get_graph() -> graphistry.Graphistry:
    """Return a singleton PyGraphistry graph with nodes & edges loaded.
    Uses the Polars backend for GFQL Cypher.
    """
    if "graph" not in POOL:
        nodes, edges = build_graph.load_built_graph()
        g = graphistry.edges(edges, "src", "dst").nodes(nodes, "id")
        POOL["graph"] = g
    return POOL["graph"]  # type: ignore[return-value]


def _to_polars(df: pl.DataFrame | None) -> pl.DataFrame:
    if df is None:
        return pl.DataFrame()
    if isinstance(df, pl.DataFrame):
        return df
    return pl.DataFrame()



def _extract_result(result: graphistry.Graphistry) -> pl.DataFrame:
    """Extract projected columns from a GFQL query result graph."""
    nodes = _to_polars(result._nodes if hasattr(result, "_nodes") else None)
    if nodes.shape[1] > 0 and nodes.shape[0] > 0:
        mask = nodes.select(pl.any_horizontal(pl.all().is_not_null())).to_series()
        nodes = nodes.filter(mask)
        return nodes
    edges = _to_polars(result._edges if hasattr(result, "_edges") else None)
    if edges.shape[1] > 0:
        return edges
    return pl.DataFrame()


def _execute(
    g: graphistry.Graphistry,
    idx: int,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> pl.DataFrame:
    print(f"\nQuery {idx}:\n{cypher}")
    if params:
        print(f"Parameters: {params}")
    result = g.gfql(cypher, params=params, engine="polars")
    out = _extract_result(result)
    print(out)
    return out


# ── Supported queries (1-6) ─────────────────────────────────────────────────

def run_query1(g: graphistry.Graphistry) -> pl.DataFrame:
    """Who are the names of people who live in Glasgow and are interested in Napoleon?"""
    cypher = """
        MATCH (p:Person)-[:personIsLocatedIn]->(pl:Place),
              (p)-[:hasInterest]->(t:Tag)
        WHERE pl.name = $place_name AND t.name = $tag_name
        RETURN p.firstname, p.lastname
    """
    return _execute(g, 1, cypher, {"place_name": "Glasgow", "tag_name": "Napoleon"})


def run_query2(g: graphistry.Graphistry) -> pl.DataFrame:
    """IDs of posts by Lei Zhang whose content contains Zulu."""
    cypher = """
        MATCH (p:Person)<-[:postHasCreator]-(post:Post)
        WHERE p.firstname = $first_name AND p.lastname = $last_name
          AND post.content CONTAINS $content_fragment
        RETURN post.id
    """
    return _execute(
        g, 2, cypher,
        {"first_name": "Lei", "last_name": "Zhang", "content_fragment": "Zulu"},
    )


def run_query3(g: graphistry.Graphistry) -> pl.DataFrame:
    """Creator of post ID 962077547172 and where they studied."""
    cypher = """
        MATCH (post:Post {id: $post_id})-[:postHasCreator]->(person:Person),
              (person)-[:studyAt]->(org:Organisation)
        RETURN person.firstname, person.lastname, org.name
    """
    return _execute(g, 3, cypher, {"post_id": 962077547172})


def run_query4(g: graphistry.Graphistry) -> pl.DataFrame:
    """Comment IDs by Alfredo Gomez with length > 100."""
    cypher = """
        MATCH (p:Person)<-[:commentHasCreator]-(c:Comment)
        WHERE p.firstname = $first_name AND p.lastname = $last_name
          AND c.length > $min_length
        RETURN c.id
    """
    return _execute(
        g, 4, cypher,
        {"first_name": "Alfredo", "last_name": "Gomez", "min_length": 100},
    )


def run_query5(g: graphistry.Graphistry) -> pl.DataFrame:
    """Full names of persons with last name Choi who are members of forums containing John Brown."""
    cypher = """
        MATCH (f:Forum)-[:hasMember]->(p:Person)
        WHERE f.title CONTAINS $forum_title_fragment
          AND p.lastname CONTAINS $last_name_fragment
        RETURN DISTINCT p.firstname, p.lastname
        LIMIT 10
    """
    return _execute(
        g, 5, cypher,
        {"forum_title_fragment": "John Brown", "last_name_fragment": "Choi"},
    )


def run_query6(g: graphistry.Graphistry) -> pl.DataFrame:
    """IDs of employees who work at Nova_Air and whose last name contains Bravo."""
    cypher = """
        MATCH (p:Person)-[:workAt]->(o:Organisation)
        WHERE o.name = $organization_name AND p.lastname CONTAINS $last_name_fragment
        RETURN p.id
    """
    return _execute(
        g, 6, cypher,
        {"organization_name": "Nova_Air", "last_name_fragment": "Bravo"},
    )


# ── Unsupported queries (7-30) ──────────────────────────────────────────────
# These queries are not yet supported by GFQL's Cypher engine due to
# limitations with complex multi-hop patterns, aggregation + grouping,
# and/or performance on large cross-products. They will be added as
# the engine matures.

def run_query7(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q7: GFQL Cypher does not yet support this pattern (complex multi-hop with comma-separated path + branch)")


def run_query8(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q8: not yet supported")


def run_query9(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q9: not yet supported")


def run_query10(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q10: not yet supported")


def run_query11(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q11: not yet supported")


def run_query12(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q12: not yet supported")


def run_query13(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q13: not yet supported")


def run_query14(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q14: not yet supported")


def run_query15(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q15: not yet supported")


def run_query16(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q16: not yet supported")


def run_query17(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q17: not yet supported")


def run_query18(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q18: not yet supported")


def run_query19(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q19: not yet supported")


def run_query20(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q20: not yet supported")


def run_query21(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q21: not yet supported")


def run_query22(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q22: not yet supported")


def run_query23(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q23: not yet supported")


def run_query24(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q24: not yet supported")


def run_query25(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q25: not yet supported")


def run_query26(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q26: not yet supported")


def run_query27(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q27: not yet supported")


def run_query28(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q28: not yet supported")


def run_query29(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q29: not yet supported")


def run_query30(g: graphistry.Graphistry) -> pl.DataFrame:
    raise NotImplementedError("Q30: not yet supported")


# ── Query registry ──────────────────────────────────────────────────────────

QUERY_FUNCTIONS: dict[int, Callable[[graphistry.Graphistry], pl.DataFrame]] = {
    1: run_query1,
    2: run_query2,
    3: run_query3,
    4: run_query4,
    5: run_query5,
    6: run_query6,
    7: run_query7,
    8: run_query8,
    9: run_query9,
    10: run_query10,
    11: run_query11,
    12: run_query12,
    13: run_query13,
    14: run_query14,
    15: run_query15,
    16: run_query16,
    17: run_query17,
    18: run_query18,
    19: run_query19,
    20: run_query20,
    21: run_query21,
    22: run_query22,
    23: run_query23,
    24: run_query24,
    25: run_query25,
    26: run_query26,
    27: run_query27,
    28: run_query28,
    29: run_query29,
    30: run_query30,
}


def _parse_selection(argv: list[str]) -> list[int] | None:
    if not argv:
        return None
    selection = argv[0].strip()
    if selection in {"run_all", "all"}:
        return None
    parts = [p.strip() for p in selection.split(",") if p.strip()]
    indices: list[int] = []
    for part in parts:
        try:
            indices.append(int(part))
        except ValueError:
            raise ValueError(f"Invalid query index: {part}")
    return indices


def main(selected: list[int] | None = None) -> None:
    g = get_graph()
    start = time.perf_counter()
    if selected is None:
        selected = [1, 2, 3, 4, 5, 6]  # only supported queries by default
    for idx in selected:
        func = QUERY_FUNCTIONS.get(idx)
        if func is None:
            print(f"Skipping unknown query index: {idx}")
            continue
        try:
            func(g)
        except NotImplementedError as e:
            print(f"\nQuery {idx}: SKIPPED - {e}")
    elapsed = time.perf_counter() - start
    print(f"\nCompleted in {elapsed:.2f}s")


if __name__ == "__main__":
    selected_queries = _parse_selection(sys.argv[1:])
    main(selected_queries)
