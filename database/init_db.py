
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "wellness_app.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

def init_database() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
    print(f"Database initialized successfully at: {DB_PATH}")

if __name__ == "__main__":
    init_database()
