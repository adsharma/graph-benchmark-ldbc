"""Rerun the full Ladybug suite with the Q11 cache workaround."""

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent / "20260903T204340Z"))
import run_benchmark

run_benchmark.OUT = OUT
sys.argv = [sys.argv[0], "ladybug"]

if __name__ == "__main__":
    raise SystemExit(run_benchmark.main())
