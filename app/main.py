"""Small, local payment ledger. Money is stored as integer minor units."""

import os
import re
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

STATIC = Path(__file__).parent / "static"
ROOT = Path(__file__).resolve().parent.parent
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=40)]
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
MonthlyFee = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class StudentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Text
    phone: Phone
    group: Text
    monthly_fee: MonthlyFee


class Student(StudentInput):
    id: int


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: Annotated[int, Field(gt=0)]
    amount: Money
    date: date


class Payment(PaymentInput):
    id: int


class Debtor(Student):
    paid: Decimal
    debt: Decimal


class DebtorsReport(BaseModel):
    month: str
    total_debt: Decimal
    debtors: list[Debtor]


def minor_units(value: Decimal) -> int:
    return int(value * 100)


def money(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(Decimal("0.01"))


def month_bounds(month: str) -> tuple[str, str]:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
        raise HTTPException(422, "Месяц должен быть в формате YYYY-MM")
    try:
        start = date.fromisoformat(month + "-01")
        end = (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
    except ValueError:
        raise HTTPException(422, "Укажите существующий месяц с 0001-01 по 9999-11") from None
    return start.isoformat(), end.isoformat()


def student_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "group": row["group_name"],
        "monthly_fee": money(row["monthly_fee_cents"]),
    }


def payment_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "amount": money(row["amount_cents"]),
        "date": row["paid_on"],
    }


def create_app(database_path: str | Path | None = None) -> FastAPI:
    path = Path(database_path or os.getenv("DATABASE_PATH", ROOT / "data" / "school.sqlite3"))

    @contextmanager
    def connect():
        db = sqlite3.connect(path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        path.parent.mkdir(parents=True, exist_ok=True)
        with connect() as db:
            db.executescript("""
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
                    paid_on TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS payments_student_date
                    ON payments(student_id, paid_on);
            """)
        yield

    api = FastAPI(title="Учёт оплат учебного центра", version="1.0.0", lifespan=lifespan)
    api.mount("/static", StaticFiles(directory=STATIC), name="static")

    def require_student(db, student_id: int):
        row = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Ученик не найден")
        return row

    @api.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @api.get("/students", response_model=list[Student])
    def students():
        with connect() as db:
            rows = db.execute("SELECT * FROM students ORDER BY name COLLATE NOCASE, id")
            return [student_dict(row) for row in rows]

    @api.post("/students", response_model=Student, status_code=201)
    def add_student(student: StudentInput):
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO students(name, phone, group_name, monthly_fee_cents) "
                "VALUES(?, ?, ?, ?)",
                (student.name, student.phone, student.group, minor_units(student.monthly_fee)),
            )
            return student_dict(require_student(db, cursor.lastrowid))

    @api.get("/students/{student_id}", response_model=Student)
    def get_student(student_id: int):
        with connect() as db:
            return student_dict(require_student(db, student_id))

    @api.put("/students/{student_id}", response_model=Student)
    def update_student(student_id: int, student: StudentInput):
        with connect() as db:
            require_student(db, student_id)
            db.execute(
                "UPDATE students SET name=?, phone=?, group_name=?, monthly_fee_cents=? WHERE id=?",
                (
                    student.name,
                    student.phone,
                    student.group,
                    minor_units(student.monthly_fee),
                    student_id,
                ),
            )
            return student_dict(require_student(db, student_id))

    @api.delete("/students/{student_id}", status_code=204)
    def delete_student(student_id: int):
        with connect() as db:
            require_student(db, student_id)
            if db.execute(
                "SELECT 1 FROM payments WHERE student_id = ? LIMIT 1", (student_id,)
            ).fetchone():
                raise HTTPException(
                    409, "Нельзя удалить ученика с оплатами: история должна сохраниться"
                )
            db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        return Response(status_code=204)

    @api.post("/payments", response_model=Payment, status_code=201)
    def add_payment(payment: PaymentInput):
        with connect() as db:
            require_student(db, payment.student_id)
            cursor = db.execute(
                "INSERT INTO payments(student_id, amount_cents, paid_on) VALUES(?, ?, ?)",
                (payment.student_id, minor_units(payment.amount), payment.date.isoformat()),
            )
            row = db.execute("SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return payment_dict(row)

    @api.get("/students/{student_id}/payments", response_model=list[Payment])
    def payments(student_id: int):
        with connect() as db:
            require_student(db, student_id)
            rows = db.execute(
                "SELECT * FROM payments WHERE student_id = ? ORDER BY paid_on DESC, id DESC",
                (student_id,),
            )
            return [payment_dict(row) for row in rows]

    @api.get("/debtors", response_model=DebtorsReport)
    def debtors(month: Annotated[str, Query(description="Календарный месяц YYYY-MM")]):
        start, end = month_bounds(month)
        with connect() as db:
            rows = db.execute(
                """
                SELECT s.*, COALESCE(SUM(p.amount_cents), 0) AS paid_cents
                FROM students s
                LEFT JOIN payments p ON p.student_id = s.id AND p.paid_on >= ? AND p.paid_on < ?
                GROUP BY s.id
                HAVING COALESCE(SUM(p.amount_cents), 0) < s.monthly_fee_cents
                ORDER BY s.monthly_fee_cents - COALESCE(SUM(p.amount_cents), 0) DESC, s.id
            """,
                (start, end),
            ).fetchall()
            result = [
                dict(
                    student_dict(row),
                    paid=money(row["paid_cents"]),
                    debt=money(row["monthly_fee_cents"] - row["paid_cents"]),
                )
                for row in rows
            ]
        return {
            "month": month,
            "total_debt": sum((item["debt"] for item in result), Decimal("0.00")),
            "debtors": result,
        }

    return api


app = create_app()
