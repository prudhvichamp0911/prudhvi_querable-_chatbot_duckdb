"""Rebuild data/analytics.duckdb from the CSVs in data/.

    python scripts/build_duckdb.py           # only if a CSV changed
    python scripts/build_duckdb.py --force   # always

The backend also builds the file on first use when QUERY_ENGINE=duckdb, so
this script is only needed to rebuild by hand.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import duckdb_store  # noqa: E402


def main():
    force = "--force" in sys.argv[1:]
    built = duckdb_store.build(force=force)
    print(("built " if built else "up to date ") + str(duckdb_store.DB_PATH))
    for table, columns in duckdb_store.schema().items():
        print(f"  {table}: {len(columns)} columns")
    duckdb_store.reset_connection()


if __name__ == "__main__":
    main()
