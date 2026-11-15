"""Run every quality check in sql/00_quality_checks.sql against DuckDB.

Each block in the SQL file starts with `-- CHECK: <name>` and must be a single
SELECT statement. Results print as plain ASCII tables. If a result has a
`status` column containing `FAIL`, the runner exits with code 1.

Usage:
    uv run scripts/run_quality_checks.py
    uv run scripts/run_quality_checks.py --db path/to/olist.duckdb --sql path/to/checks.sql
"""

from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "olist.duckdb"
DEFAULT_SQL_PATH = PROJECT_ROOT / "sql" / "00_quality_checks.sql"

CHECK_MARKER = re.compile(r"^--\s*CHECK:\s*(?P<name>.+?)\s*$", re.MULTILINE)


def split_checks(sql: str) -> list[tuple[str, str]]:
    """Split a SQL file into (check name, statement) pairs."""
    markers = list(CHECK_MARKER.finditer(sql))
    checks: list[tuple[str, str]] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(sql)
        statement = sql[start:end].strip()
        if statement:
            checks.append((marker.group("name"), statement))
    return checks


def format_value(value: Any) -> str:
    """Format a cell for the console without relying on Unicode box drawing."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, (float, Decimal)):
        return f"{value:,.2f}"
    return str(value)


def print_table(columns: list[str], rows: list[tuple[Any, ...]]) -> None:
    """Print rows as an ASCII table sized to its contents."""
    body = [[format_value(value) for value in row] for row in rows]
    widths = [len(column) for column in columns]
    for row in body:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def render(cells: list[str]) -> str:
        padded = (cell.ljust(width) for cell, width in zip(cells, widths))
        return "| " + " | ".join(padded) + " |"

    print(border)
    print(render(columns))
    print(border)
    for row in body:
        print(render(row))
    print(border)


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
        help=f"SQL file with -- CHECK: markers (default: {DEFAULT_SQL_PATH})",
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

    checks = split_checks(args.sql.read_text(encoding="utf-8"))
    if not checks:
        print(f"No '-- CHECK:' blocks found in {args.sql}", file=sys.stderr)
        return 1

    con = duckdb.connect(str(args.db), read_only=True)
    failures = 0
    try:
        for number, (name, statement) in enumerate(checks, 1):
            result = con.execute(statement)
            columns = [column[0] for column in result.description]
            rows = result.fetchall()

            print(f"[{number}/{len(checks)}] {name}")
            print_table(columns, rows)
            print()

            if "status" in columns:
                status_index = columns.index("status")
                failures += sum(
                    1 for row in rows if str(row[status_index]).upper() == "FAIL"
                )
    except duckdb.Error as error:
        print(f"\nSQL error in check '{name}': {error}", file=sys.stderr)
        return 1
    finally:
        con.close()

    if failures:
        print(f"{len(checks)} checks executed, {failures} row(s) marked FAIL")
        return 1

    print(f"{len(checks)} checks executed, no FAIL statuses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
