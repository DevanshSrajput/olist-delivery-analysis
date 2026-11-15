"""Build the clean delivered-orders analysis table and assert its grain.

Runs the stages in sql/01_analysis_orders.sql in order, then checks that every
stage has count(*) = count(distinct order_id). Any duplicate makes the runner
exit with code 1.

Usage:
    uv run scripts/build_analysis_table.py
    uv run scripts/build_analysis_table.py --db path/to/olist.duckdb --sql path/to/build.sql
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "olist.duckdb"
DEFAULT_SQL_PATH = PROJECT_ROOT / "sql" / "01_analysis_orders.sql"

STAGE_MARKER = re.compile(
    r"^--\s*STAGE:\s*(?P<object>[A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.MULTILINE,
)


def split_stages(sql: str) -> list[tuple[str, str]]:
    """Split the build file into (object name, statement) pairs."""
    markers = list(STAGE_MARKER.finditer(sql))
    stages: list[tuple[str, str]] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(sql)
        statement = sql[start:end].strip()
        if statement:
            stages.append((marker.group("object"), statement))
    return stages


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"DuckDB database file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--sql",
        type=Path,
        default=DEFAULT_SQL_PATH,
        help=f"staged build SQL file (default: {DEFAULT_SQL_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.db.is_file():
        print(
            f"Database not found: {args.db}\n"
            "Run scripts/load_to_duckdb.py first.",
            file=sys.stderr,
        )
        return 1
    if not args.sql.is_file():
        print(f"SQL file not found: {args.sql}", file=sys.stderr)
        return 1

    stages = split_stages(args.sql.read_text(encoding="utf-8"))
    if not stages:
        print(f"No '-- STAGE:' blocks found in {args.sql}", file=sys.stderr)
        return 1

    con = duckdb.connect(str(args.db))
    results: list[tuple[str, int, int, int, str]] = []
    try:
        for object_name, statement in stages:
            con.execute(statement)
            rows, distinct = con.execute(
                f'select count(*), count(distinct order_id) from "{object_name}"'
            ).fetchone()
            duplicates = rows - distinct
            status = "ok" if duplicates == 0 else "FAIL"
            results.append((object_name, rows, distinct, duplicates, status))
    except duckdb.Error as error:
        print(f"\nSQL error while building '{object_name}': {error}", file=sys.stderr)
        return 1
    finally:
        con.close()

    headers = ("stage", "rows", "distinct_order_ids", "duplicate_rows", "status")
    widths = [
        max(len(headers[0]), *(len(result[0]) for result in results)),
        max(len(headers[1]), *(len(f"{result[1]:,}") for result in results)),
        max(len(headers[2]), *(len(f"{result[2]:,}") for result in results)),
        max(len(headers[3]), *(len(f"{result[3]:,}") for result in results)),
        len(headers[4]),
    ]
    print(
        f"{headers[0]:<{widths[0]}}  {headers[1]:>{widths[1]}}  "
        f"{headers[2]:>{widths[2]}}  {headers[3]:>{widths[3]}}  {headers[4]}"
    )
    print("-" * (sum(widths) + 8))
    for object_name, rows, distinct, duplicates, status in results:
        print(
            f"{object_name:<{widths[0]}}  {rows:>{widths[1]},}  "
            f"{distinct:>{widths[2]},}  {duplicates:>{widths[3]},}  {status}"
        )

    failures = sum(1 for result in results if result[4] == "FAIL")
    print()
    if failures:
        print(f"{len(results)} stage assertions, {failures} failed")
        return 1

    print(f"{len(results)} stage assertions passed")
    print(f"analysis_orders written to {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
