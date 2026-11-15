"""Load every Olist CSV in data/ into a DuckDB database, one table per file.

Timestamp columns are stored as TIMESTAMP, money columns as DECIMAL(12,2), and
zip-code prefixes as VARCHAR so leading zeros survive.

Usage:
    uv run scripts/load_to_duckdb.py
    uv run scripts/load_to_duckdb.py --data-dir path/to/csvs --db path/to/olist.duckdb
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = PROJECT_ROOT / "olist.duckdb"

ColumnTypes = dict[str, str]

# table name -> (csv filename, ordered column name/type pairs)
SCHEMAS: dict[str, tuple[str, ColumnTypes]] = {
    "customers": (
        "olist_customers_dataset.csv",
        {
            "customer_id": "VARCHAR",
            "customer_unique_id": "VARCHAR",
            "customer_zip_code_prefix": "VARCHAR",
            "customer_city": "VARCHAR",
            "customer_state": "VARCHAR",
        },
    ),
    "geolocation": (
        "olist_geolocation_dataset.csv",
        {
            "geolocation_zip_code_prefix": "VARCHAR",
            "geolocation_lat": "DOUBLE",
            "geolocation_lng": "DOUBLE",
            "geolocation_city": "VARCHAR",
            "geolocation_state": "VARCHAR",
        },
    ),
    "order_items": (
        "olist_order_items_dataset.csv",
        {
            "order_id": "VARCHAR",
            "order_item_id": "INTEGER",
            "product_id": "VARCHAR",
            "seller_id": "VARCHAR",
            "shipping_limit_date": "TIMESTAMP",
            "price": "DECIMAL(12,2)",
            "freight_value": "DECIMAL(12,2)",
        },
    ),
    "order_payments": (
        "olist_order_payments_dataset.csv",
        {
            "order_id": "VARCHAR",
            "payment_sequential": "INTEGER",
            "payment_type": "VARCHAR",
            "payment_installments": "INTEGER",
            "payment_value": "DECIMAL(12,2)",
        },
    ),
    "order_reviews": (
        "olist_order_reviews_dataset.csv",
        {
            "review_id": "VARCHAR",
            "order_id": "VARCHAR",
            "review_score": "INTEGER",
            "review_comment_title": "VARCHAR",
            "review_comment_message": "VARCHAR",
            "review_creation_date": "TIMESTAMP",
            "review_answer_timestamp": "TIMESTAMP",
        },
    ),
    "orders": (
        "olist_orders_dataset.csv",
        {
            "order_id": "VARCHAR",
            "customer_id": "VARCHAR",
            "order_status": "VARCHAR",
            "order_purchase_timestamp": "TIMESTAMP",
            "order_approved_at": "TIMESTAMP",
            "order_delivered_carrier_date": "TIMESTAMP",
            "order_delivered_customer_date": "TIMESTAMP",
            "order_estimated_delivery_date": "TIMESTAMP",
        },
    ),
    "products": (
        "olist_products_dataset.csv",
        {
            "product_id": "VARCHAR",
            "product_category_name": "VARCHAR",
            "product_name_lenght": "INTEGER",
            "product_description_lenght": "INTEGER",
            "product_photos_qty": "INTEGER",
            "product_weight_g": "INTEGER",
            "product_length_cm": "INTEGER",
            "product_height_cm": "INTEGER",
            "product_width_cm": "INTEGER",
        },
    ),
    "sellers": (
        "olist_sellers_dataset.csv",
        {
            "seller_id": "VARCHAR",
            "seller_zip_code_prefix": "VARCHAR",
            "seller_city": "VARCHAR",
            "seller_state": "VARCHAR",
        },
    ),
    "product_category_name_translation": (
        "product_category_name_translation.csv",
        {
            "product_category_name": "VARCHAR",
            "product_category_name_english": "VARCHAR",
        },
    ),
}


def sql_literal(value: str) -> str:
    """Quote a Python string as a SQL single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


def columns_sql(columns: ColumnTypes) -> str:
    """Render DuckDB's read_csv columns struct, e.g. {'a': 'VARCHAR'}."""
    entries = ", ".join(
        f"{sql_literal(name)}: {sql_literal(type_)}" for name, type_ in columns.items()
    )
    return "{" + entries + "}"


def load_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    csv_path: Path,
    columns: ColumnTypes,
) -> None:
    """Create or replace one table from one CSV with an explicit schema."""
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        f"SELECT * FROM read_csv("
        f"{sql_literal(str(csv_path))}, "
        f"header = true, "
        f"columns = {columns_sql(columns)}, "
        f"encoding = 'utf-8'"
        f")"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"directory holding the Olist CSVs (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"DuckDB database file (default: {DEFAULT_DB_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    missing = [
        filename
        for filename, _ in SCHEMAS.values()
        if not (args.data_dir / filename).is_file()
    ]
    if missing:
        print(f"Missing CSV files in {args.data_dir}:", file=sys.stderr)
        for filename in missing:
            print(f"  - {filename}", file=sys.stderr)
        return 1

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.db))
    try:
        for table, (filename, columns) in SCHEMAS.items():
            load_table(con, table, args.data_dir / filename, columns)

        print(f"Loaded {len(SCHEMAS)} tables into {args.db}")
        print()
        print(f"{'table':<36}{'rows':>10}")
        total = 0
        for table in SCHEMAS:
            (rows,) = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()
            total += rows
            print(f"{table:<36}{rows:>10,}")
        print("-" * 46)
        print(f"{'total':<36}{total:>10,}")
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
