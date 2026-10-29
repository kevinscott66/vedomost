"""Database location, schema and transaction boundaries for the local ledger."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"


def database_path(value: str | Path | None = None) -> Path:
    path = Path(value or os.getenv("DATABASE_PATH") or ROOT / "data" / "school.sqlite3")
    path = path.expanduser().resolve()
    if path == STATIC or STATIC in path.parents:
        raise ValueError("Database must be outside the publicly served static directory")
    return path


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = database_path(path)

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                # Acquire write authority before checking references, not after.
                if write:
                    db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 4:
                raise RuntimeError("Database schema is newer than this application")
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    monthly_fee_cents INTEGER NOT NULL CHECK(monthly_fee_cents >= 0)
                );
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                    paid_on TEXT NOT NULL,
                    original_amount_cents INTEGER NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'UZS',
                    exchange_rate TEXT NOT NULL DEFAULT '1',
                    rate_date TEXT,
                    rate_source TEXT
                );
                CREATE INDEX IF NOT EXISTS payments_student_date
                    ON payments(student_id, paid_on);
                CREATE TABLE IF NOT EXISTS payment_requests (
                    request_key TEXT PRIMARY KEY NOT NULL,
                    payload TEXT NOT NULL,
                    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE RESTRICT
                );

            """)

            columns = {row["name"] for row in db.execute("PRAGMA table_info(students)")}
            if "start_month" not in columns:
                month = date.today().strftime("%Y-%m")
                db.execute(
                    f"ALTER TABLE students ADD COLUMN start_month TEXT NOT NULL DEFAULT '{month}'"
                )
                # No real enrollment date existed. Preserve known payment history;
                # do not invent debt before the earliest recorded payment/current month.
                db.execute(
                    "UPDATE students SET start_month = MIN(start_month, COALESCE("
                    "(SELECT MIN(substr(paid_on,1,7)) FROM payments WHERE student_id=students.id),"
                    "start_month))"
                )
            payment_columns = {row["name"] for row in db.execute("PRAGMA table_info(payments)")}
            if "original_amount_cents" not in payment_columns:
                db.execute(
                    "ALTER TABLE payments ADD COLUMN original_amount_cents "
                    "INTEGER NOT NULL DEFAULT 0"
                )
                db.execute("UPDATE payments SET original_amount_cents = amount_cents")
            if "currency" not in payment_columns:
                db.execute("ALTER TABLE payments ADD COLUMN currency TEXT NOT NULL DEFAULT 'UZS'")
            if "exchange_rate" not in payment_columns:
                db.execute(
                    "ALTER TABLE payments ADD COLUMN exchange_rate TEXT NOT NULL DEFAULT '1'"
                )
            if "rate_date" not in payment_columns:
                db.execute("ALTER TABLE payments ADD COLUMN rate_date TEXT")
            if "rate_source" not in payment_columns:
                db.execute("ALTER TABLE payments ADD COLUMN rate_source TEXT")
            for column in ("voided_at", "void_reason"):
                if column not in payment_columns:
                    db.execute(f"ALTER TABLE payments ADD COLUMN {column} TEXT")
            db.execute("""CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL, created_at TEXT NOT NULL,
                student_id INTEGER NOT NULL, student_name TEXT NOT NULL,
                payment_id INTEGER, detail TEXT NOT NULL
            )""")
            db.execute("PRAGMA user_version = 4")
