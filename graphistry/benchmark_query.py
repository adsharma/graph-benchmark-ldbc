from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

# Add this directory to the path for local imports without shadowing
# the installed `graphistry` (pygraphistry) library.
_SCRIPT_ROOT = Path(__file__).resolve().parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

import graphistry
import polars as pl
import pytest

import build_graph
import query

_graph_instance: graphistry.Graphistry | None = None


def _get_graph() -> graphistry.Graphistry:
    global _graph_instance
    if _graph_instance is None:
        nodes, edges = build_graph.load_built_graph()
        _graph_instance = graphistry.edges(edges, "src", "dst").nodes(nodes, "id")
    return _graph_instance


@pytest.fixture(scope="session")
def graph_context() -> graphistry.Graphistry:
    return _get_graph()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _rows(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, pl.DataFrame):
        return result.to_dicts()
    if hasattr(result, "to_dicts"):
        return result.to_dicts()
    return list(result)


def _normalize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append({str(key).lower(): value for key, value in row.items()})
    return normalized


def _row_sort_key(row: dict[str, Any]) -> tuple:
    return tuple(sorted(row.items()))


def _assert_rows(
    result: Any,
    expected_rows: Iterable[dict[str, Any]],
    *,
    order_sensitive: bool = False,
) -> None:
    rows = _normalize_rows(_rows(result))
    expected = _normalize_rows(expected_rows)
    if order_sensitive:
        assert rows == expected
        return
    assert sorted(rows, key=_row_sort_key) == sorted(expected, key=_row_sort_key)


def _assert_single_value(result: Any, key: str, expected_value: Any) -> None:
    rows = _normalize_rows(_rows(result))
    assert rows == [{key.lower(): expected_value}]


# ── Supported benchmark tests (1-6) ─────────────────────────────────────────


def test_benchmark_query1(benchmark, graph_context):
    result = benchmark(query.run_query1, graph_context)
    _assert_rows(
        result,
        [{"p.firstname": "Thomas", "p.lastname": "Brown"}],
        order_sensitive=True,
    )


def test_benchmark_query2(benchmark, graph_context):
    result = benchmark(query.run_query2, graph_context)
    _assert_rows(
        result,
        [
            {"post.id": 2061586474857},
            {"post.id": 2061586474860},
        ],
    )


def test_benchmark_query3(benchmark, graph_context):
    result = benchmark(query.run_query3, graph_context)
    _assert_rows(
        result,
        [
            {
                "person.firstname": "Mads",
                "person.lastname": "Haugland",
                "org.name": "Norwegian_School_of_Sport_Sciences",
            }
        ],
        order_sensitive=True,
    )


def test_benchmark_query4(benchmark, graph_context):
    result = benchmark(query.run_query4, graph_context)
    _assert_rows(result, [{"c.id": 1924145496676}], order_sensitive=True)


def test_benchmark_query5(benchmark, graph_context):
    result = benchmark(query.run_query5, graph_context)
    _assert_rows(
        result,
        [{"p.firstname": "Akihiko", "p.lastname": "Choi"}],
        order_sensitive=True,
    )


def test_benchmark_query6(benchmark, graph_context):
    result = benchmark(query.run_query6, graph_context)
    _assert_rows(
        result,
        [
            {"p.id": 28587302332692},
            {"p.id": 17592186046501},
            {"p.id": 19791209310595},
            {"p.id": 15393162799645},
            {"p.id": 15393162791641},
        ],
    )
