"""Compare repeated Q11 execution with/without the PR's dummy parameter.

Diagnostic only: does not alter benchmark sources or report benchmark timings.
Both modes keep ANALYZE, result conversion, result cleanup and the same database.
"""

import importlib.util
import sys
from pathlib import Path

import ladybug

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ladybug_queries", ROOT / "ladybugdb/query.py"
)
queries = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queries)


class WithoutDummy:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=None):
        return self.connection.execute(query)


def main():
    mode = sys.argv[1]
    assert mode in {"pr", "without-dummy"}
    db = ladybug.Database(str(ROOT / "ladybugdb/ldbc_snb_sf1.lbdb"))
    conn = ladybug.Connection(db)
    result = conn.execute("ANALYZE")
    result.close()
    target = conn if mode == "pr" else WithoutDummy(conn)
    for i in range(1, 21):
        print(f"mode={mode} iteration={i} begin", flush=True)
        rows = queries.run_query11(target).to_dicts()
        assert rows == [{"num_e": 190, "o.name": "MDLR_Airlines"}], rows
        print(f"mode={mode} iteration={i} passed", flush=True)
    conn.close()
    db.close()
    print(f"mode={mode}: 20 repeated executions passed", flush=True)


if __name__ == "__main__":
    main()
