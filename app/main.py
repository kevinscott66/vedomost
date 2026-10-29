"""Small, local payment ledger. Money is stored as integer minor units."""

import json
import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.database import ROOT, STATIC, Database
from app.exchange_rates import ExchangeRateService
from app.security import LocalBoundaryMiddleware

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=40)]
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
MonthlyFee = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


MAX_ID = 2**63 - 1
StudentId = Annotated[int, PathParam(gt=0, le=MAX_ID)]


class StudentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Text
    phone: Phone
    group: Text
    monthly_fee: MonthlyFee
    start_month: str | None = None

    @field_validator("start_month")
    @classmethod
    def valid_start_month(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
            raise ValueError("Use YYYY-MM for start_month")
        date.fromisoformat(value + "-01")
        return value


class Student(StudentInput):
    id: int
    start_month: str


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: Annotated[int, Field(gt=0, le=MAX_ID)]
    amount: Money
    date: date
    currency: Literal["UZS", "RUB", "USD"] = "UZS"


class Payment(PaymentInput):
    id: int
    base_amount: Decimal
    exchange_rate: Decimal
    rate_date: date | None
    rate_source: str | None
    voided_at: str | None = None
    void_reason: str | None = None


class VoidInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class Debtor(Student):
    paid: Decimal
    debt: Decimal


class DebtorsReport(BaseModel):
    month: str
    total_debt: Decimal
    debtors: list[Debtor]


class StudentStatement(BaseModel):
    month: str
    student: Student
    charge: Decimal
    paid: Decimal
    debt: Decimal
    payments: list[Payment]


def minor_units(value: Decimal) -> int:
    return int(value * 100)


def money(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(Decimal("0.01"))


def month_bounds(month: str) -> tuple[str, str | None]:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
        raise HTTPException(422, "Месяц должен быть в формате YYYY-MM")
    try:
        start = date.fromisoformat(month + "-01")
        if month == "9999-12":
            return start.isoformat(), None
        end = (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
    except ValueError:
        raise HTTPException(422, "Укажите существующий месяц с 0001-01 по 9999-12") from None
    return start.isoformat(), end.isoformat()


def student_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "group": row["group_name"],
        "monthly_fee": money(row["monthly_fee_cents"]),
        "start_month": row["start_month"],
    }


def payment_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "amount": money(row["original_amount_cents"]),
        "currency": row["currency"],
        "base_amount": money(row["amount_cents"]),
        "exchange_rate": Decimal(row["exchange_rate"]),
        "rate_date": row["rate_date"],
        "rate_source": row["rate_source"],
        "date": row["paid_on"],
        "voided_at": row["voided_at"],
        "void_reason": row["void_reason"],
    }


def create_app(database_path: str | Path | None = None) -> FastAPI:
    database = Database(database_path)
    connect = database.connect
    exchange_rates = ExchangeRateService(
        database.path.with_name(database.path.name + ".exchange-rates.json")
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        database.initialize()
        yield

    api = FastAPI(
        title="Учёт оплат учебного центра",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    api.add_middleware(LocalBoundaryMiddleware)

    @api.exception_handler(sqlite3.OperationalError)
    async def database_busy(_request, exc):
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            return JSONResponse({"detail": "Database busy; retry later"}, status_code=503)
        raise exc

    api.mount("/static", StaticFiles(directory=STATIC), name="static")

    def require_student(db, student_id: StudentId):
        row = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Ученик не найден")
        return row

    def record_activity(db, action, student, detail, payment_id=None):
        db.execute(
            "INSERT INTO activity(action,created_at,student_id,student_name,payment_id,detail) "
            "VALUES(?,?,?,?,?,?)",
            (
                action,
                datetime.now(timezone.utc).isoformat(),
                student["id"],
                student["name"],
                payment_id,
                json.dumps(detail, default=str, ensure_ascii=False),
            ),
        )

    @api.get("/activity")
    def activity(before: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None):
        with connect() as db:
            rows = db.execute(
                "SELECT * FROM activity WHERE (? IS NULL OR id < ?) ORDER BY id DESC LIMIT 51",
                (before, before),
            ).fetchall()
            items = [{**dict(row), "detail": json.loads(row["detail"])} for row in rows[:50]]
            return {"items": items, "next_before": items[-1]["id"] if len(rows) > 50 else None}

    @api.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @api.get("/privacy", include_in_schema=False)
    def privacy():
        return FileResponse(STATIC / "privacy.html")

    @api.get("/terms", include_in_schema=False)
    def terms():
        return FileResponse(STATIC / "terms.html")

    @api.get("/rights", include_in_schema=False)
    def rights():
        return FileResponse(STATIC / "rights.html")

    @api.get("/docs", include_in_schema=False)
    def documentation():
        return FileResponse(STATIC / "docs.html")

    @api.get("/case", include_in_schema=False)
    def portfolio_case():
        return FileResponse(STATIC / "case.html")

    @api.get("/try", include_in_schema=False)
    def teaching_example():
        return FileResponse(STATIC / "try.html")

    @api.get("/redoc", include_in_schema=False)
    def redoc():
        return RedirectResponse("/docs")

    @api.get("/license.txt", include_in_schema=False)
    def license_text():
        return FileResponse(ROOT / "LICENSE.txt", media_type="text/plain; charset=utf-8")

    @api.get("/third-party-notices.txt", include_in_schema=False)
    def third_party_notices():
        return FileResponse(ROOT / "THIRD_PARTY_NOTICES.md", media_type="text/plain; charset=utf-8")

    @api.get("/students", response_model=list[Student])
    def students():
        with connect() as db:
            rows = db.execute("SELECT * FROM students ORDER BY name COLLATE NOCASE, id")
            return [student_dict(row) for row in rows]

    @api.get("/exchange-rates")
    def get_exchange_rates():
        return exchange_rates.get()

    @api.post("/students", response_model=Student, status_code=201)
    def add_student(student: StudentInput):
        with connect(write=True) as db:
            cursor = db.execute(
                "INSERT INTO students(name, phone, group_name, monthly_fee_cents, start_month) "
                "VALUES(?, ?, ?, ?, ?)",
                (
                    student.name,
                    student.phone,
                    student.group,
                    minor_units(student.monthly_fee),
                    student.start_month or date.today().strftime("%Y-%m"),
                ),
            )
            result = student_dict(require_student(db, cursor.lastrowid))
            record_activity(db, "student.add", result, {"after": result})
            return result

    @api.get("/students/{student_id}", response_model=Student)
    def get_student(student_id: StudentId):
        with connect() as db:
            return student_dict(require_student(db, student_id))

    @api.put("/students/{student_id}", response_model=Student)
    def update_student(student_id: StudentId, student: StudentInput):
        with connect(write=True) as db:
            existing = require_student(db, student_id)
            start_month = student.start_month or existing["start_month"]
            earliest = db.execute(
                "SELECT MIN(substr(paid_on,1,7)) FROM payments "
                "WHERE student_id=? AND voided_at IS NULL",
                (student_id,),
            ).fetchone()[0]
            if earliest and start_month > earliest:
                raise HTTPException(409, "Начало обучения позже существующих оплат")
            db.execute(
                "UPDATE students SET name=?, phone=?, group_name=?, monthly_fee_cents=?, "
                "start_month=? WHERE id=?",
                (
                    student.name,
                    student.phone,
                    student.group,
                    minor_units(student.monthly_fee),
                    start_month,
                    student_id,
                ),
            )
            result = student_dict(require_student(db, student_id))
            if result != student_dict(existing):
                record_activity(
                    db,
                    "student.update",
                    result,
                    {"before": student_dict(existing), "after": result},
                )
            return result

    @api.delete("/students/{student_id}", status_code=204)
    def delete_student(student_id: StudentId):
        with connect(write=True) as db:
            existing = require_student(db, student_id)
            if db.execute(
                "SELECT 1 FROM payments WHERE student_id = ? LIMIT 1", (student_id,)
            ).fetchone():
                raise HTTPException(
                    409, "Нельзя удалить ученика с оплатами: история должна сохраниться"
                )
            record_activity(
                db, "student.delete", student_dict(existing), {"before": student_dict(existing)}
            )
            db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        return Response(status_code=204)

    @api.post("/payments", response_model=Payment, status_code=201)
    def add_payment(
        payment: PaymentInput,
        idempotency_key: Annotated[str | None, Header(min_length=16, max_length=128)] = None,
    ):
        original_cents = minor_units(payment.amount)
        payload = f"{payment.student_id}|{original_cents}|{payment.date.isoformat()}"
        if payment.currency != "UZS":
            payload += f"|{payment.currency}"

        def replay(db):
            prior = db.execute(
                "SELECT payload, payment_id FROM payment_requests WHERE request_key = ?",
                (idempotency_key,),
            ).fetchone()
            if prior:
                if prior["payload"] != payload:
                    raise HTTPException(409, "Idempotency key used for a different payment")
                row = db.execute(
                    "SELECT * FROM payments WHERE id = ?", (prior["payment_id"],)
                ).fetchone()
                return payment_dict(row)
            return None

        # A retry must return its booked snapshot even when today's rate source is down.
        if idempotency_key:
            with connect() as db:
                prior_result = replay(db)
            if prior_result is not None:
                return prior_result
        with connect() as db:
            existing = require_student(db, payment.student_id)
        if payment.date.isoformat()[:7] < existing["start_month"]:
            raise HTTPException(422, "Дата оплаты раньше начала обучения")

        exchange_rate = Decimal(1)
        base_cents = original_cents
        rate_date = None
        rate_source = None
        if payment.currency != "UZS":
            snapshot = exchange_rates.get()
            if snapshot.get("status") != "fresh" or snapshot.get("source") not in {"CBU", "CBR"}:
                raise HTTPException(503, "Нет свежего официального курса для оплаты")
            try:
                booking_rates = snapshot.get("booking_rates", {})
                rate_value = booking_rates.get(
                    payment.currency, snapshot["rates"][payment.currency]
                )
                exchange_rate = Decimal(str(rate_value))
                rate_date = date.fromisoformat(snapshot["rate_date"])
                rate_source = snapshot["source"]
                with localcontext() as context:
                    context.prec = 80
                    converted = (payment.amount * exchange_rate * 100).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                base_cents = int(converted)
            except (KeyError, ValueError, ArithmeticError):
                raise HTTPException(503, "Официальный курс недоступен") from None
            if base_cents <= 0 or base_cents > MAX_ID:
                raise HTTPException(422, "Сумма в UZS выходит за допустимый диапазон")

        with connect(write=True) as db:
            if idempotency_key:
                prior_result = replay(db)
                if prior_result is not None:
                    return prior_result
            existing = require_student(db, payment.student_id)
            if payment.date.isoformat()[:7] < existing["start_month"]:
                raise HTTPException(422, "Дата оплаты раньше начала обучения")
            month_start, month_end = month_bounds(payment.date.isoformat()[:7])
            # A valid individual conversion can still overflow SQLite SUM when combined.
            # Check under the same write lock; Python integers do not overflow.
            month_paid = sum(
                row[0]
                for row in db.execute(
                    "SELECT amount_cents FROM payments WHERE student_id = ? "
                    "AND voided_at IS NULL AND paid_on >= ? AND (? IS NULL OR paid_on < ?)",
                    (payment.student_id, month_start, month_end, month_end),
                )
            )
            if month_paid + base_cents > MAX_ID:
                raise HTTPException(422, "Monthly payment total exceeds storage limit")
            cursor = db.execute(
                "INSERT INTO payments(student_id, amount_cents, paid_on, original_amount_cents, "
                "currency, exchange_rate, rate_date, rate_source) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    payment.student_id,
                    base_cents,
                    payment.date.isoformat(),
                    original_cents,
                    payment.currency,
                    str(exchange_rate),
                    rate_date.isoformat() if rate_date else None,
                    rate_source,
                ),
            )
            if idempotency_key:
                db.execute(
                    "INSERT INTO payment_requests(request_key,payload,payment_id) VALUES(?,?,?)",
                    (idempotency_key, payload, cursor.lastrowid),
                )
            row = db.execute("SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)).fetchone()
            result = payment_dict(row)
            record_activity(
                db, "payment.add", student_dict(existing), {"payment": result}, result["id"]
            )
            return result

    @api.post("/payments/{payment_id}/void", response_model=Payment)
    def void_payment(payment_id: StudentId, data: VoidInput):
        with connect(write=True) as db:
            row = db.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Payment not found")
            if row["voided_at"]:
                if row["void_reason"] != data.reason:
                    raise HTTPException(409, "Payment already voided")
                return payment_dict(row)
            db.execute(
                "UPDATE payments SET voided_at=?, void_reason=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), data.reason, payment_id),
            )
            result = payment_dict(
                db.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
            )
            student = student_dict(require_student(db, row["student_id"]))
            record_activity(db, "payment.void", student, {"payment": result}, payment_id)
            return result

    @api.get("/students/{student_id}/payments", response_model=list[Payment])
    def payments(student_id: StudentId):
        with connect() as db:
            require_student(db, student_id)
            rows = db.execute(
                "SELECT * FROM payments WHERE student_id = ? ORDER BY paid_on DESC, id DESC",
                (student_id,),
            )
            return [payment_dict(row) for row in rows]

    @api.get("/students/{student_id}/statement", response_model=StudentStatement)
    def statement(student_id: StudentId, month: Annotated[str, Query()]):
        start, end = month_bounds(month)
        with connect() as db:
            # One read snapshot: a concurrent payment cannot split detail and total.
            db.execute("BEGIN")
            student = require_student(db, student_id)
            payments = db.execute(
                "SELECT * FROM payments WHERE student_id=? AND paid_on>=? "
                "AND (? IS NULL OR paid_on<?) ORDER BY paid_on, id",
                (student_id, start, end, end),
            ).fetchall()
            charged = student["monthly_fee_cents"] if student["start_month"] <= month else 0
            paid = sum(row["amount_cents"] for row in payments if not row["voided_at"])
            return {
                "month": month,
                "student": student_dict(student),
                "charge": money(charged),
                "paid": money(paid),
                "debt": money(max(0, charged - paid)),
                "payments": [payment_dict(row) for row in payments],
            }

    @api.get("/debtors", response_model=DebtorsReport)
    def debtors(month: Annotated[str, Query(description="Календарный месяц YYYY-MM")]):
        start, end = month_bounds(month)
        with connect() as db:
            rows = db.execute(
                """
                SELECT s.*, COALESCE(SUM(p.amount_cents), 0) AS paid_cents
                FROM students s
                LEFT JOIN payments p ON p.student_id = s.id
                    AND p.voided_at IS NULL AND p.paid_on >= ? AND (? IS NULL OR p.paid_on < ?)
                WHERE s.start_month <= ?
                GROUP BY s.id
                HAVING COALESCE(SUM(p.amount_cents), 0) < s.monthly_fee_cents
                ORDER BY s.monthly_fee_cents - COALESCE(SUM(p.amount_cents), 0) DESC, s.id
            """,
                (start, end, end, month),
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
