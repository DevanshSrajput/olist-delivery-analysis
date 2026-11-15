"""Export the fixed-seed Q5 review sample to labels_human.csv.

The SQL file draws 100 distinct low-score reviews with text using DuckDB's
seeded reservoir sample. This script adds an empty label column and preserves
the comment text exactly.

Usage:
    uv run scripts/export_review_sample.py

Refuses to overwrite a labels_human.csv that already contains labels unless
--force is passed, so hand-labelled work is not silently destroyed.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "olist.duckdb"
DEFAULT_SQL_PATH = PROJECT_ROOT / "sql" / "q5_sample_low_score_reviews.sql"
DEFAULT_OUT_PATH = PROJECT_ROOT / "labels_human.csv"

EXPECTED_SAMPLE_SIZE = 100


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
        help=f"sample SQL file (default: {DEFAULT_SQL_PATH})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help=f"output CSV (default: {DEFAULT_OUT_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite even if the existing file contains non-empty labels",
    )
    return parser.parse_args(argv)


def count_existing_labels(path: Path) -> int:
    """Count non-empty labels in an existing output file."""
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "label" not in reader.fieldnames:
            return 0
        return sum(1 for row in reader if (row.get("label") or "").strip())


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

    if not args.force:
        existing_labels = count_existing_labels(args.out)
        if existing_labels:
            print(
                f"Refusing to overwrite {args.out}: it already has "
                f"{existing_labels} labeled row(s). Use --force to replace it.",
                file=sys.stderr,
            )
            return 1

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        result = con.execute(args.sql.read_text(encoding="utf-8"))
        columns = [column[0] for column in result.description]
        rows = result.fetchall()
    except duckdb.Error as error:
        print(f"SQL error in {args.sql}: {error}", file=sys.stderr)
        return 1
    finally:
        con.close()

    if columns != ["review_id", "comment"]:
        print(f"Unexpected columns: {columns}", file=sys.stderr)
        return 1
    if len(rows) != EXPECTED_SAMPLE_SIZE:
        print(
            f"Expected {EXPECTED_SAMPLE_SIZE} rows, got {len(rows)}",
            file=sys.stderr,
        )
        return 1
    if len({row[0] for row in rows}) != len(rows):
        print("Sample contains duplicate review_id values", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["review_id", "comment", "label"])
        for review_id, comment in rows:
            writer.writerow([review_id, comment, ""])

    print(f"Population: score 1 or 2 with non-empty text, distinct review_id")
    print(f"Seed: 42 (fixed in {args.sql.name})")
    print(f"Sample: {len(rows)} distinct reviews")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
