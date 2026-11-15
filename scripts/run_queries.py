"""Run analysis SQL files and save every -- OUTPUT: result to CSV.

Each block in a SQL file starts with `-- OUTPUT: <filename>.csv` and must be a
single SELECT. Results are written to outputs/ with a header row.

Usage:
    uv run scripts/run_queries.py
    uv run scripts/run_queries.py --sql sql/q1_review_score_by_delay.sql
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "olist.duckdb"
DEFAULT_SQL_DIR = PROJECT_ROOT / "sql"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"

OUTPUT_MARKER = re.compile(
    r"^--\s*OUTPUT:\s*(?P<filename>[A-Za-z0-9_.-]+\.csv)\s*$",
    re.MULTILINE,
)


def split_outputs(sql: str) -> list[tuple[str, str]]:
    """Split a SQL file into (csv filename, statement) pairs."""
    markers = list(OUTPUT_MARKER.finditer(sql))
    outputs: list[tuple[str, str]] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(sql)
        statement = sql[start:end].strip()
        if statement:
            outputs.append((marker.group("filename"), statement))
    return outputs


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
        nargs="+",
        type=Path,
        default=None,
        help="SQL files to run (default: sql/q[1-4]_*.sql)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"directory for CSV files (default: {DEFAULT_OUTPUT_DIR})",
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

    sql_paths = args.sql or sorted(DEFAULT_SQL_DIR.glob("q[1-4]_*.sql"))
    if not sql_paths:
        print(f"No SQL files found in {args.sql or DEFAULT_SQL_DIR}", file=sys.stderr)
        return 1

    plans: list[tuple[Path, str, str]] = []
    seen: set[str] = set()
    for sql_path in sql_paths:
        if not sql_path.is_file():
            print(f"SQL file not found: {sql_path}", file=sys.stderr)
            return 1
        outputs = split_outputs(sql_path.read_text(encoding="utf-8"))
        if not outputs:
            print(f"No '-- OUTPUT:' blocks found in {sql_path}", file=sys.stderr)
            return 1
        for filename, statement in outputs:
            if filename in seen:
                print(f"Duplicate output filename: {filename}", file=sys.stderr)
                return 1
            seen.add(filename)
            plans.append((sql_path, filename, statement))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        for sql_path, filename, statement in plans:
            try:
                result = con.execute(statement)
                columns = [column[0] for column in result.description]
                rows = result.fetchall()
            except duckdb.Error as error:
                print(
                    f"SQL error in {sql_path.name} -> {filename}: {error}",
                    file=sys.stderr,
                )
                return 1

            csv_path = args.out_dir / filename
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerows(rows)
            print(f"{csv_path.name:<48}{len(rows):>6} rows x {len(columns)} columns")
    finally:
        con.close()

    print()
    print(f"{len(sql_paths)} SQL files, {len(plans)} CSV files written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
