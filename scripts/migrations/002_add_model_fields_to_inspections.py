"""
Migration: Add model_name and model_version to inspections table

Run: python scripts/migrations/002_add_model_fields_to_inspections.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "pcb_defects.db"


def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(inspections)")
    columns = [row[1] for row in cursor.fetchall()]

    if "model_name" not in columns:
        cursor.execute("ALTER TABLE inspections ADD COLUMN model_name TEXT")
        print("Added column 'model_name'")

    if "model_version" not in columns:
        cursor.execute("ALTER TABLE inspections ADD COLUMN model_version TEXT")
        print("Added column 'model_version'")

    conn.commit()
    conn.close()
    print("Migration completed.")


if __name__ == "__main__":
    migrate()
