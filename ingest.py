"""Load the project CSVs into MySQL in foreign-key-safe, repeatable batches."""
import argparse
import csv
import os
from pathlib import Path

import mysql.connector

TABLES = ("categories", "restaurants", "items", "users", "orders", "order_items", "payments")


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        if not columns:
            raise ValueError(f"Missing CSV header: {path}")
        return columns, ([None if value == "" else value for value in row.values()] for row in reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "food_delivery_dw"),
    )
    try:
        cursor = connection.cursor()
        for table in TABLES:
            columns, source_rows = rows(Path(__file__).parent / f"{table}.csv")
            names = ", ".join(f"`{column}`" for column in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            updates = ", ".join(f"`{column}`=VALUES(`{column}`)" for column in columns if column not in ("category_id", "restaurant_id", "item_id", "user_id", "order_id", "order_item_id", "payment_id"))
            statement = f"INSERT INTO `{table}` ({names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates or f'`{columns[0]}`=VALUES(`{columns[0]}`)'}"
            batch = []
            count = 0
            for row in source_rows:
                batch.append(row)
                if len(batch) == args.batch_size:
                    cursor.executemany(statement, batch)
                    count += len(batch)
                    batch.clear()
            if batch:
                cursor.executemany(statement, batch)
                count += len(batch)
            connection.commit()
            print(f"{table}: loaded {count} rows")
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
