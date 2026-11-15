"""Export the full Q5 low-score review population for classification.

Population: distinct review_id with score 1 or 2 and non-whitespace comment
text. The 100-review sample is a subset and its cached labels are reused by
scripts/classify_reviews.py.

Usage:
    uv run scripts/export_q5_population.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "olist.duckdb"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "q5_full_population.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"DuckDB database file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"CSV output path (default: {DEFAULT_OUTPUT_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.db.is_file():
        print(f"Database not found: {args.db}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_sql = str(args.output.resolve()).replace("\\", "/")

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        population = r"""
            select distinct
                review_id,
                review_comment_message as comment
            from order_reviews
            where review_score in (1, 2)
              and regexp_matches(review_comment_message, '\S')
            order by review_id
        """
        rows = con.execute(f"select count(*) from ({population})").fetchone()[0]
        con.execute(
            f"copy ({population}) to '{output_sql}' "
            "(header, delimiter ',', quote '\"', escape '\"')"
        )
    finally:
        con.close()

    print(f"Wrote {rows:,} reviews to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
