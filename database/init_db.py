#!/usr/bin/env python3
"""Initialize SQLite database for lead-explorer-os.

Builds database from schema.sql and populates with filtered lead data.
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Constants
DB_FILE = "leads.db"
SCHEMA_FILE = "schema.sql"

def init_database(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Initialize and return SQLite database connection.

    Args:
        db_path: Optional database file path. Defaults to leads.db.

    Returns:
        SQLite database connection.
    """
    # Default database file should be in the database directory
    db_path = db_path or Path(__file__).parent / "leads.db"

    # Convert relative path to absolute
    if not Path(db_path).is_absolute():
        db_path = Path(__file__).parent / db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    schema_path = Path(__file__).parent / SCHEMA_FILE
    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = f.read()
            conn.executescript(schema)
        print(f"[OK] Created database: {db_path}")
    else:
        print(f"[ERROR] Schema file not found: {schema_path}")

    return conn

def load_filtered_data(conn: sqlite3.Connection, source_file: str) -> int:
    """Load filtered lead data from parser output CSV into database.

    Args:
        conn: SQLite database connection.
        source_file: Path to filtered CSV file.

    Returns:
        Number of records loaded.
    """
    # The filtered.csv file should be in the parent directory (backend folder)
    backend_dir = Path(__file__).parent.parent / "backend"
    source_path = backend_dir / Path(source_file)
    
    if not source_path.exists():
        print(f"[ERROR] Source file not found: {source_path}")
        return 0

    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads")

    import csv
    with open(source_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

        for record in records:
            cursor.execute(
                """
                INSERT INTO leads (id, name, email, phone, industry, region, source, created_at, intent_score, interest_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("id", ""),
                    record.get("name", ""),
                    record.get("email", ""),
                    record.get("phone", ""),
                    record.get("industry", ""),
                    record.get("region", ""),
                    record.get("source", ""),
                    record.get("created_at", ""),
                    record.get("intent_score", 0.0),
                    record.get("interest_level", "Cold")
                )
            )

    conn.commit()
    print(f"[OK] Loaded {len(records)} records into database")
    return len(records)

def main():
    """Initialize database and populate with filtered lead data."""
    print("Initializing lead-explorer-os database...")

    conn = init_database()
    loaded = load_filtered_data(conn, "filtered.csv")

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM leads")
    total = cursor.fetchone()["count"]

    print(f"[OK] Database ready: {total} total records (loaded: {loaded})")

if __name__ == "__main__":
    main()
