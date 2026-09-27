#!/usr/bin/env python3
"""
Database Initializer & Migration Utility
Supports SQLite for lightweight/embedded local use and executes schema.sql.
"""

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = os.environ.get("DB_PATH", "workout_app.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def init_database(db_path: str = DEFAULT_DB_PATH):
    print(f"[*] Initializing database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if not SCHEMA_PATH.exists():
        print(f"[!] Schema file not found: {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    cursor.executescript(schema_sql)
    conn.commit()

    # Auto-seed Wger Exercise Catalog if empty
    CATALOG_JSON = Path(__file__).parent.parent / "data" / "exercises_seed.json"
    cursor.execute("SELECT COUNT(*) FROM exercises")
    ex_count = cursor.fetchone()[0]
    if ex_count == 0 and CATALOG_JSON.exists():
        import json
        with open(CATALOG_JSON, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        cursor.executemany("""
            INSERT OR IGNORE INTO exercises (id, user_id, name, category, primary_muscle, secondary_muscles, is_custom, description, equipment, animation_svg, images)
            VALUES (:id, 'default_user', :name, :category, :primary_muscle, :secondary_muscles, :is_custom, :description, :equipment, :animation_svg, :images)
        """, catalog)
        conn.commit()
        print(f"[+] Automatically seeded {len(catalog)} exercises into catalog.")

    # Verify default settings
    cursor.execute("SELECT key, value FROM user_settings WHERE key = 'selected_ollama_model'")
    row = cursor.fetchone()
    if row:
        print(f"[+] Verified default setting: {row[0]} = {row[1]}")
    else:
        print("[!] Warning: default setting selected_ollama_model was not seeded!")

    conn.close()
    print("[+] Database initialized successfully.")

if __name__ == "__main__":
    init_database()
