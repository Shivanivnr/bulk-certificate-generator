
import sqlite3
from pathlib import Path

# Keep the database in the project folder
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "certificates.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                total_recipients INTEGER NOT NULL DEFAULT 0,
                successful_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                certificate_filename TEXT,
                error_message TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)

        connection.commit()
        print("Database tables created successfully!")

    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
