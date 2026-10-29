"""Pure ledger rules for the Cloudflare Worker adapter.

State is a JSON-compatible object. Monetary values remain decimal strings so the
Worker can persist them without passing through binary floating point.
"""

from __future__ import annotations

import copy
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_ID = 2**63 - 1
MAX_STUDENTS = 100
MAX_PAYMENTS = 1000
MAX_REQUESTS = 1000
MAX_EVENTS = 3000


class DomainError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail
        super().__init__(detail)


class StudentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=3, max_length=40)
    group: str = Field(min_length=1, max_length=160)
    monthly_fee: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    start_month: str | None = None

    @field_validator("name", "phone", "group", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("start_month")
    @classmethod
    def month_valid(cls, value):
        if value is not None:
            _month_bounds(value)
        return value


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: int = Field(gt=0, le=MAX_ID)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    date: date
    currency: Literal["UZS", "RUB", "USD"] = "UZS"


class VoidInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


def _record(state, action, student, detail, payment_id=None):
    events = state.setdefault("activity", [])
    if len(events) >= MAX_EVENTS:
        raise DomainError(422, "Activity limit reached")
    events.append(
        {
            "id": len(events) + 1,
            "action": action,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "student_id": student["id"],
            "student_name": student["name"],
            "payment_id": payment_id,
            "detail": copy.deepcopy(detail),
        }
    )


def _validated(model, data):
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise DomainError(422, exc.errors(include_url=False)[0]["msg"]) from None


def _month_bounds(month: str) -> tuple[str, str | None]:
    if not isinstance(month, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
        raise DomainError(422, "Месяц должен быть в формате YYYY-MM")
    try:
        start = date.fromisoformat(month + "-01")
    except ValueError:
        raise DomainError(422, "Укажите существующий месяц с 0001-01 по 9999-12") from None
    if month == "9999-12":
        return start.isoformat(), None
    end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
    return start.isoformat(), end.isoformat()


def _decimal(value) -> Decimal:
    try:
        out = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise DomainError(422, "Invalid decimal value") from None
    if not out.is_finite():
        raise DomainError(422, "Invalid decimal value")
    return out


def _cents(value) -> int:
    return int(_decimal(value) * 100)


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def _student(state, student_id):
    if (
        not isinstance(student_id, int)
        or isinstance(student_id, bool)
        or not 0 < student_id <= MAX_ID
    ):
        raise DomainError(422, "Invalid student id")
    for student in state["students"]:
        if student["id"] == student_id:
            return student
    raise DomainError(404, "Ученик не найден")


def _public_student(student):
    return copy.deepcopy(student)


def _public_payment(payment):
    # Older JSON ledgers predate cancellation fields. Normalize responses without
    # rewriting stored payments or the immutable activity snapshots beside them.
    return {"voided_at": None, "void_reason": None, **copy.deepcopy(payment)}


def seed(today: date | None = None) -> dict:
    today = today or date.today()
    day = today.isoformat()
    month = day[:7]
    students = [
        {
            "id": 1,
            "name": "Анна Миронова",
            "phone": "+7 000 000-00-00",
            "group": "Английский · А2",
            "monthly_fee": "800000.00",
            "start_month": month,
        },
        {
            "id": 2,
            "name": "Марк Соколов",
            "phone": "+7 000 000-00-00",
            "group": "Математика · 9 класс",
            "monthly_fee": "500000.00",
            "start_month": month,
        },
        {
            "id": 3,
            "name": "София Белова",
            "phone": "+7 000 000-00-00",
            "group": "Английский · B1",
            "monthly_fee": "850000.00",
            "start_month": month,
        },
        {
            "id": 4,
            "name": "Тимур Орлов",
            "phone": "+7 000 000-00-00",
            "group": "Информатика · 10 класс",
            "monthly_fee": "600000.00",
            "start_month": month,
        },
    ]
    d = day
    payments = [
        {
            "id": 1,
            "student_id": 1,
            "amount": "400000.00",
            "currency": "UZS",
            "base_amount": "400000.00",
            "exchange_rate": "1",
            "rate_date": None,
            "rate_source": None,
            "date": d,
        },
        {
            "id": 2,
            "student_id": 3,
            "amount": "850000.00",
            "currency": "UZS",
            "base_amount": "850000.00",
            "exchange_rate": "1",
            "rate_date": None,
            "rate_source": None,
            "date": d,
        },
        {
            "id": 3,
            "student_id": 4,
            "amount": "150000.00",
            "currency": "UZS",
            "base_amount": "150000.00",
            "exchange_rate": "1",
            "rate_date": None,
            "rate_source": None,
            "date": d,
        },
    ]
    return {
        "students": students,
        "payments": [_public_payment(p) for p in payments],
        "requests": {},
        "next_student": 5,
        "next_payment": 4,
    }


def _result(status, response, changed, working, original):
    return status, response, changed, working if changed else original


def handle(state, method, path, query=None, body=None, idempotency_key=None, quote=None):
    """Apply one request and return (status, JSON response, changed, new_state).

    ``quote`` is the async adapter's official FX snapshot. It is consulted only
    for a new non-UZS payment; idempotent replays happen before quote validation.
    """
    working = copy.deepcopy(state)
    query, body = query or {}, body or {}
    method, path = method.upper(), path.rstrip("/") or "/"
    try:
        if method == "GET" and path == "/activity":
            before = query.get("before")
            if before is not None:
                try:
                    before = int(before)
                except (TypeError, ValueError):
                    raise DomainError(422, "Invalid activity cursor") from None
                if not 0 < before <= MAX_ID:
                    raise DomainError(422, "Invalid activity cursor")
            rows = [
                e
                for e in reversed(working.get("activity", []))
                if before is None or e["id"] < before
            ]
            return _result(
                200,
                {"items": rows[:50], "next_before": rows[49]["id"] if len(rows) > 50 else None},
                False,
                working,
                state,
            )
        m_void = re.fullmatch(r"/payments/([0-9]+)/void", path)
        if method == "POST" and m_void:
            pid = int(m_void.group(1))
            if not 0 < pid <= MAX_ID:
                raise DomainError(422, "Invalid payment id")
            data = _validated(VoidInput, body)
            p = next((p for p in working["payments"] if p["id"] == pid), None)
            if p is None:
                raise DomainError(404, "Payment not found")
            if p.get("voided_at"):
                if p["void_reason"] != data.reason:
                    raise DomainError(409, "Payment already voided")
                return _result(200, _public_payment(p), False, working, state)
            p.update(voided_at=datetime.now(timezone.utc).isoformat(), void_reason=data.reason)
            _record(
                working, "payment.void", _student(working, p["student_id"]), {"payment": p}, pid
            )
            return _result(200, _public_payment(p), True, working, state)
        if method == "GET" and path == "/students":
            rows = sorted(working["students"], key=lambda s: (s["name"].casefold(), s["id"]))
            return _result(200, rows, False, working, state)
        if method == "GET" and path == "/debtors":
            month = query.get("month")
            if month is None:
                raise DomainError(422, "month is required")
            start, end = _month_bounds(month)
            debtors = []
            for s in working["students"]:
                if s["start_month"] > month:
                    continue
                paid = sum(
                    _cents(p["base_amount"])
                    for p in working["payments"]
                    if p["student_id"] == s["id"]
                    and not p.get("voided_at")
                    and start <= p["date"]
                    and (end is None or p["date"] < end)
                )
                fee = _cents(s["monthly_fee"])
                if paid < fee:
                    debtors.append(
                        {**_public_student(s), "paid": _money(paid), "debt": _money(fee - paid)}
                    )
            debtors.sort(key=lambda s: (-_cents(s["debt"]), s["id"]))
            total = sum(_cents(s["debt"]) for s in debtors)
            if total > MAX_ID:
                raise DomainError(422, "Monthly debt total exceeds storage limit")
            return _result(
                200,
                {"month": month, "total_debt": _money(total), "debtors": debtors},
                False,
                working,
                state,
            )

        if method == "POST" and path == "/students":
            if len(working["students"]) >= MAX_STUDENTS:
                raise DomainError(422, "Student limit reached")
            item = _validated(StudentInput, body)
            month = item.start_month or date.today().isoformat()[:7]
            sid = working["next_student"]
            if sid > MAX_ID:
                raise DomainError(422, "Student id limit reached")
            s = {
                "id": sid,
                "name": item.name,
                "phone": item.phone,
                "group": item.group,
                "monthly_fee": f"{item.monthly_fee:.2f}",
                "start_month": month,
            }
            working["students"].append(s)
            working["next_student"] += 1
            _record(working, "student.add", s, {"after": s})
            return _result(201, s, True, working, state)

        m = re.fullmatch(r"/students/([^/]+)(?:/(payments|statement))?", path)
        if m:
            try:
                sid = int(m.group(1))
            except ValueError:
                raise DomainError(422, "Invalid student id") from None
            s = _student(working, sid)
            if m.group(2) == "statement" and method == "GET":
                month = query.get("month")
                start, end = _month_bounds(month)
                rows = [
                    p
                    for p in working["payments"]
                    if p["student_id"] == sid
                    and start <= p["date"]
                    and (end is None or p["date"] < end)
                ]
                rows.sort(key=lambda p: (p["date"], p["id"]))
                charge = _cents(s["monthly_fee"]) if s["start_month"] <= month else 0
                paid = sum(_cents(p["base_amount"]) for p in rows if not p.get("voided_at"))
                return _result(
                    200,
                    {
                        "month": month,
                        "student": _public_student(s),
                        "charge": _money(charge),
                        "paid": _money(paid),
                        "debt": _money(max(0, charge - paid)),
                        "payments": [_public_payment(p) for p in rows],
                    },
                    False,
                    working,
                    state,
                )
            if m.group(2) == "payments" and method == "GET":
                rows = [p for p in working["payments"] if p["student_id"] == sid]
                rows.sort(key=lambda p: (p["date"], p["id"]), reverse=True)
                return _result(200, [_public_payment(p) for p in rows], False, working, state)
            if not m.group(2) and method == "GET":
                return _result(200, _public_student(s), False, working, state)
            if not m.group(2) and method == "PUT":
                item = _validated(StudentInput, body)
                start_month = item.start_month or s["start_month"]
                earliest = min(
                    (
                        p["date"][:7]
                        for p in working["payments"]
                        if p["student_id"] == sid and not p.get("voided_at")
                    ),
                    default=None,
                )
                if earliest and start_month > earliest:
                    raise DomainError(409, "Начало обучения позже существующих оплат")
                before = copy.deepcopy(s)
                s.update(
                    name=item.name,
                    phone=item.phone,
                    group=item.group,
                    monthly_fee=f"{item.monthly_fee:.2f}",
                    start_month=start_month,
                )
                if s != before:
                    _record(working, "student.update", s, {"before": before, "after": s})
                return _result(200, _public_student(s), True, working, state)
            if not m.group(2) and method == "DELETE":
                if any(p["student_id"] == sid for p in working["payments"]):
                    raise DomainError(
                        409, "Нельзя удалить ученика с оплатами: история должна сохраниться"
                    )
                _record(working, "student.delete", s, {"before": s})
                working["students"].remove(s)
                return _result(204, None, True, working, state)

        if method == "POST" and path == "/payments":
            item = _validated(PaymentInput, body)
            original = _cents(item.amount)
            normalized = f"{item.student_id}|{original}|{item.date.isoformat()}" + (
                f"|{item.currency}" if item.currency != "UZS" else ""
            )
            if idempotency_key is not None:
                if not isinstance(idempotency_key, str) or not 16 <= len(idempotency_key) <= 128:
                    raise DomainError(422, "Invalid idempotency key")
                prior = working["requests"].get(idempotency_key)
                if prior:
                    if prior["payload"] != normalized:
                        raise DomainError(409, "Idempotency key used for a different payment")
                    return _result(
                        201,
                        _public_payment(
                            next(p for p in working["payments"] if p["id"] == prior["payment_id"])
                        ),
                        False,
                        working,
                        state,
                    )
            s = _student(working, item.student_id)
            month = item.date.isoformat()[:7]
            if month < s["start_month"]:
                raise DomainError(422, "Дата оплаты раньше начала обучения")
            rate, rate_date, source = Decimal(1), None, None
            base = original
            if item.currency != "UZS":
                if (
                    not isinstance(quote, dict)
                    or quote.get("status") != "fresh"
                    or quote.get("source") not in {"CBU", "CBR"}
                ):
                    raise DomainError(503, "Нет свежего официального курса для оплаты")
                try:
                    raw_rates = quote.get("booking_rates") or quote.get("rates") or {}
                    rate = _decimal(raw_rates[item.currency])
                    rate_date = date.fromisoformat(quote["rate_date"]).isoformat()
                    source = quote["source"]
                    with localcontext() as ctx:
                        ctx.prec = 80
                        base = int(
                            (item.amount * rate * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
                        )
                except (KeyError, ValueError, ArithmeticError):
                    raise DomainError(503, "Официальный курс недоступен") from None
                if base <= 0 or base > MAX_ID:
                    raise DomainError(422, "Сумма в UZS выходит за допустимый диапазон")
            if len(working["payments"]) >= MAX_PAYMENTS:
                raise DomainError(422, "Payment limit reached")
            start, end = _month_bounds(month)
            paid = sum(
                _cents(p["base_amount"])
                for p in working["payments"]
                if p["student_id"] == item.student_id
                and not p.get("voided_at")
                and start <= p["date"]
                and (end is None or p["date"] < end)
            )
            if paid + base > MAX_ID:
                raise DomainError(422, "Monthly payment total exceeds storage limit")
            if idempotency_key and len(working["requests"]) >= MAX_REQUESTS:
                raise DomainError(422, "Idempotency request limit reached")
            pid = working["next_payment"]
            if pid > MAX_ID:
                raise DomainError(422, "Payment id limit reached")
            payment = {
                "id": pid,
                "student_id": item.student_id,
                "amount": _money(original),
                "currency": item.currency,
                "base_amount": _money(base),
                "exchange_rate": format(rate, "f"),
                "rate_date": rate_date,
                "rate_source": source,
                "date": item.date.isoformat(),
                "voided_at": None,
                "void_reason": None,
            }
            working["payments"].append(payment)
            working["next_payment"] += 1
            _record(working, "payment.add", s, {"payment": payment}, pid)
            if idempotency_key:
                working["requests"][idempotency_key] = {"payload": normalized, "payment_id": pid}
            return _result(201, payment, True, working, state)

        raise DomainError(404, "Not found")
    except DomainError:
        raise
    except (KeyError, TypeError, ValueError):
        raise DomainError(422, "Invalid request") from None
