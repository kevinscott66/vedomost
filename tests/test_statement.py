"""Both adapters must explain the same booked, month-scoped debt."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.exchange_rates import ExchangeRateService
from app.main import create_app
from cloud.domain import DomainError, handle


@pytest.fixture(params=["sqlite", "cloud"])
def ledger(request, tmp_path, monkeypatch):
    quote = {
        "status": "fresh",
        "source": "CBU",
        "rate_date": "2026-10-01",
        "rates": {"UZS": 1, "USD": 12000, "RUB": 150},
        "booking_rates": {"UZS": "1", "USD": "12000", "RUB": "150"},
    }
    monkeypatch.setattr(ExchangeRateService, "get", lambda self: quote)
    if request.param == "sqlite":
        with TestClient(
            create_app(tmp_path / "test.sqlite3"),
            client=("127.0.0.1", 50100),
            base_url="http://127.0.0.1",
        ) as client:

            def call(method, path, body=None, query=None):
                response = client.request(method, path, json=body, params=query)
                return response.status_code, response.json()

            yield call, quote
    else:
        state = {
            "students": [],
            "payments": [],
            "requests": {},
            "next_student": 1,
            "next_payment": 1,
        }

        def call(method, path, body=None, query=None):
            nonlocal state
            try:
                status, response, changed, state = handle(
                    state, method, path, body=body, query=query, quote=quote
                )
                return status, response
            except DomainError as error:
                return error.status, {"detail": error.detail}

        yield call, quote


def create_student(call, **changes):
    status, student = call(
        "POST",
        "/students",
        dict(
            name="Анна",
            phone="000",
            group="A2",
            monthly_fee="800000.00",
            start_month="2026-10",
            **changes,
        ),
    )
    assert status == 201
    return student["id"]


def test_statement_keeps_booked_rate_and_excludes_other_months_and_students(ledger):
    call, quote = ledger
    sid = create_student(call)
    other = create_student(call)
    for target, amount, currency, day in [
        (sid, "25", "USD", "2026-10-15"),
        (sid, "100000.10", "UZS", "2026-10-01"),
        (sid, "500000", "UZS", "2026-11-01"),
        (other, "3", "USD", "2026-10-02"),
    ]:
        assert (
            call(
                "POST",
                "/payments",
                dict(student_id=target, amount=amount, currency=currency, date=day),
            )[0]
            == 201
        )
    quote["booking_rates"]["USD"] = "19000"
    quote["rates"]["USD"] = 19000
    status, result = call("GET", f"/students/{sid}/statement", query={"month": "2026-10"})
    assert status == 200
    assert result["student"]["id"] == sid
    assert Decimal(result["charge"]) == Decimal("800000")
    assert Decimal(result["paid"]) == Decimal("400000.10")
    assert Decimal(result["debt"]) == Decimal("399999.90")
    assert [p["date"] for p in result["payments"]] == ["2026-10-01", "2026-10-15"]
    assert Decimal(result["payments"][1]["exchange_rate"]) == Decimal("12000")
    _, report = call("GET", "/debtors", query={"month": "2026-10"})
    debtor = next(s for s in report["debtors"] if s["id"] == sid)
    assert Decimal(debtor["debt"]) == Decimal(result["debt"])


def test_statement_before_start_overpayment_and_last_calendar_month(ledger):
    call, _ = ledger
    sid = create_student(call)
    _, before = call("GET", f"/students/{sid}/statement", query={"month": "2026-09"})
    assert Decimal(before["charge"]) == 0 and before["payments"] == []
    assert (
        call("POST", "/payments", dict(student_id=sid, amount="900000", date="9999-12-31"))[0]
        == 201
    )
    _, last = call("GET", f"/students/{sid}/statement", query={"month": "9999-12"})
    assert Decimal(last["debt"]) == 0 and Decimal(last["paid"]) == 900000
    _, next_month = call("GET", f"/students/{sid}/statement", query={"month": "2026-11"})
    assert Decimal(next_month["paid"]) == 0 and Decimal(next_month["debt"]) == 800000


def test_statement_validates_scope(ledger):
    call, _ = ledger
    sid = create_student(call)
    for month in ("2026-00", "0000-12", "2026-10-01"):
        assert call("GET", f"/students/{sid}/statement", query={"month": month})[0] == 422
    assert call("GET", f"/students/{sid}/statement")[0] == 422
    assert call("GET", "/students/12345/statement", query={"month": "2026-10"})[0] == 404
