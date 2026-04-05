"""
Migration: Add original_image_path to inspections table

Run: python scripts/migrations/001_add_original_image_path.py
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

    # Check if column already exists
    cursor.execute("PRAGMA table_info(inspections)")
    columns = [row[1] for row in cursor.fetchall()]

    if "original_image_path" in columns:
        print("Column 'original_image_path' already exists. No migration needed.")
        return

    cursor.execute("ALTER TABLE inspections ADD COLUMN original_image_path TEXT")
    conn.commit()
    conn.close()

    print("Migration completed: added 'original_image_path' column to inspections table.")


if __name__ == "__main__":
    migrate()
