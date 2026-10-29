"""Cancellation and the activity trail must agree in both persistence adapters."""

import copy
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from test_cloud_worker import hosted  # noqa: F401

from app.database import Database
from app.main import create_app


@pytest.fixture(params=["sqlite", "hosted"])
def ledger(request, tmp_path):
    if request.param == "hosted":
        a, b, _, _ = request.getfixturevalue("hosted")
        for client in (a, b):
            assert client.post("/demos/vedomost/session", json={}).status_code == 200
        yield a, "/demos/vedomost", b
    else:
        with TestClient(
            create_app(tmp_path / "activity.sqlite3"),
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        ) as c:
            yield c, "", None


def new_student(c, base, name="Activity student"):
    r = c.post(
        base + "/students",
        json={
            "name": name,
            "phone": "000",
            "group": "Test",
            "monthly_fee": "100",
            "start_month": "2026-01",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_active_payment_contract_matches_on_add_replay_history_and_statement(ledger):
    c, base, _ = ledger
    s = new_student(c, base)
    payload = {"student_id": s["id"], "amount": "25", "date": "2026-10-15"}
    headers = {"Idempotency-Key": "active-contract-retry-key"}
    payment = c.post(base + "/payments", json=payload, headers=headers).json()
    assert payment["voided_at"] is None and payment["void_reason"] is None
    assert c.post(base + "/payments", json=payload, headers=headers).json() == payment
    assert c.get(base + f"/students/{s['id']}/payments").json() == [payment]
    statement = c.get(base + f"/students/{s['id']}/statement?month=2026-10").json()
    assert statement["payments"] == [payment]
    event = c.get(base + "/activity").json()["items"][0]
    assert event["detail"]["payment"] == payment


@pytest.mark.parametrize("day", ["0001-01-01", "0099-12-31", "0999-07-15", "9999-12-31"])
def test_payment_month_supports_entire_calendar_range(ledger, day):
    c, base, _ = ledger
    s = new_student(c, base)
    student = {k: v for k, v in s.items() if k != "id"}
    assert (
        c.put(base + f"/students/{s['id']}", json={**student, "start_month": day[:7]}).status_code
        == 200
    )
    r = c.post(base + "/payments", json={"student_id": s["id"], "amount": "25", "date": day})
    assert r.status_code == 201, r.text
    statement = c.get(base + f"/students/{s['id']}/statement?month={day[:7]}").json()
    assert statement["paid"] == "25.00" and statement["debt"] == "75.00"


def test_legacy_cloud_payment_responses_preserve_stored_history():
    from cloud.domain import handle, seed

    state = seed()
    payment = state["payments"][0]
    payment.pop("voided_at")
    payment.pop("void_reason")
    payload = {"student_id": 1, "amount": payment["amount"], "date": payment["date"]}
    state["requests"]["legacy-contract-key"] = {
        "payload": f"1|40000000|{payment['date']}",
        "payment_id": payment["id"],
    }
    state["activity"] = [{"id": 1, "detail": {"payment": copy.deepcopy(payment)}}]
    before = copy.deepcopy(state)
    for method, path, kwargs in [
        ("GET", "/students/1/payments", {}),
        ("GET", "/students/1/statement", {"query": {"month": payment["date"][:7]}}),
        ("POST", "/payments", {"body": payload, "idempotency_key": "legacy-contract-key"}),
    ]:
        _, response, changed, returned = handle(state, method, path, **kwargs)
        result = (
            response[0] if isinstance(response, list) else response.get("payments", [response])[0]
        )
        assert result["voided_at"] is None and result["void_reason"] is None
        assert not changed and returned is state and state == before
    assert handle(state, "GET", "/activity")[1]["items"] == before["activity"]


@pytest.mark.parametrize(
    "operation", ["student.add", "student.update", "student.delete", "payment.add", "payment.void"]
)
def test_cloud_activity_limit_rolls_back_entire_write(request, monkeypatch, operation):
    c, _, db, _ = request.getfixturevalue("hosted")
    base = "/demos/vedomost"
    assert c.post(base + "/session", json={}).status_code == 200
    s = new_student(c, base)
    student = {k: v for k, v in s.items() if k != "id"}
    payload = {"student_id": s["id"], "amount": "25", "date": "2026-10-15"}
    if operation == "payment.void":
        payment = c.post(base + "/payments", json=payload).json()
        method, path, body = "POST", f"/payments/{payment['id']}/void", {"reason": "Wrong amount"}
    elif operation == "payment.add":
        method, path, body = "POST", "/payments", payload
    elif operation == "student.add":
        method, path, body = "POST", "/students", student
    elif operation == "student.update":
        method, path, body = "PUT", f"/students/{s['id']}", {**student, "name": "Changed"}
    else:
        method, path, body = "DELETE", f"/students/{s['id']}", None
    before = tuple(db.execute("SELECT state,version FROM sessions").fetchone())
    domain = sys.modules["domain"]
    with monkeypatch.context() as patch:
        patch.setattr(domain, "MAX_EVENTS", len(json.loads(before[0])["activity"]))
        failed = c.request(
            method, base + path, json=body, headers={"Idempotency-Key": "limit-retry-payment-key"}
        )
    assert failed.status_code == 422
    assert "Activity limit" in failed.text
    assert tuple(db.execute("SELECT state,version FROM sessions").fetchone()) == before
    retried = c.request(
        method, base + path, json=body, headers={"Idempotency-Key": "limit-retry-payment-key"}
    )
    assert retried.status_code in {200, 201, 204}, retried.text
    after = json.loads(db.execute("SELECT state FROM sessions").fetchone()[0])
    assert len(after["activity"]) == len(json.loads(before[0])["activity"]) + 1


def test_failed_schema_migration_rolls_back_columns_data_and_version(tmp_path, monkeypatch):
    database = Database(tmp_path / "migration-failure.sqlite3")
    with database.connect() as db:
        db.executescript("""
            CREATE TABLE students(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,
                group_name TEXT,monthly_fee_cents INTEGER);
            CREATE TABLE payments(id INTEGER PRIMARY KEY,student_id INTEGER,
                amount_cents INTEGER,paid_on TEXT);
            INSERT INTO students VALUES(1,'A','000','B',10000);
            INSERT INTO payments VALUES(1,1,5000,'2020-02-29');
            PRAGMA user_version=1;
        """)
        before = list(db.iterdump())
    connect = database.connect

    @contextmanager
    def failing_connect(**kwargs):
        with connect(**kwargs) as db:
            # Fail after all ALTERs and data backfills have run.
            db.set_authorizer(
                lambda action, name, *_: (
                    sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_CREATE_TABLE and name == "activity"
                    else sqlite3.SQLITE_OK
                )
            )
            yield db

    with monkeypatch.context() as patch:
        patch.setattr(database, "connect", failing_connect)
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            database.initialize()
    with database.connect() as db:
        assert list(db.iterdump()) == before
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    database.initialize()
    with database.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4
        row = db.execute("SELECT * FROM payments").fetchone()
        assert row["original_amount_cents"] == 5000 and row["voided_at"] is None
        assert db.execute("SELECT COUNT(*) FROM activity").fetchone()[0] == 0


def test_void_preserves_money_restores_debt_and_logs_once(ledger):
    c, base, other = ledger
    s = new_student(c, base)
    payload = {"student_id": s["id"], "amount": "150.25", "currency": "UZS", "date": "2026-10-15"}
    headers = {"Idempotency-Key": "activity-test-payment-key"}
    p = c.post(base + "/payments", json=payload, headers=headers).json()
    statement_url = base + f"/students/{s['id']}/statement?month=2026-10"
    assert c.get(statement_url).json()["debt"] == "0.00"
    url = base + f"/payments/{p['id']}/void"
    assert c.post(url, json={"reason": "   "}).status_code == 422
    assert c.post(url, json={"reason": "x" * 301}).status_code == 422
    voided = c.post(url, json={"reason": "Wrong currency"})
    assert voided.status_code == 200, voided.text
    voided = voided.json()
    for key in ["amount", "base_amount", "currency", "exchange_rate", "rate_date", "date"]:
        assert voided[key] == p[key]
    assert voided["void_reason"] == "Wrong currency" and voided["voided_at"]
    assert c.post(url, json={"reason": "Wrong currency"}).json() == voided
    assert c.post(url, json={"reason": "Changed reason"}).status_code == 409
    # Replaying the original add must not recreate or unvoid its payment.
    assert c.post(base + "/payments", json=payload, headers=headers).json()["voided_at"]
    statement = c.get(statement_url).json()
    assert statement["paid"] == "0.00" and statement["debt"] == "100.00"
    assert len(statement["payments"]) == 1
    report = c.get(base + "/debtors?month=2026-10").json()
    assert next(d for d in report["debtors"] if d["id"] == s["id"])["debt"] == "100.00"
    events = c.get(base + "/activity").json()["items"]
    assert [e["action"] for e in events] == ["payment.void", "payment.add", "student.add"]
    assert not events[1]["detail"]["payment"].get("voided_at")
    assert events[0]["detail"]["payment"]["void_reason"] == "Wrong currency"
    assert c.delete(base + f"/students/{s['id']}").status_code == 409
    if other:
        assert other.get(base + "/activity").json()["items"] == []
        assert other.post(url, json={"reason": "Other visitor"}).status_code == 404


def test_concurrent_void_has_one_event(ledger):
    c, base, _ = ledger
    s = new_student(c, base)
    p = c.post(
        base + "/payments", json={"student_id": s["id"], "amount": "50", "date": "2026-10-15"}
    ).json()

    def cancel(_):
        return c.post(base + f"/payments/{p['id']}/void", json={"reason": "Duplicate"})

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(cancel, range(4)))
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()["voided_at"] for r in results}) == 1
    assert (
        sum(e["action"] == "payment.void" for e in c.get(base + "/activity").json()["items"]) == 1
    )


def test_activity_pagination_and_deleted_student_snapshot(ledger):
    c, base, _ = ledger
    s = new_student(c, base, "<script>old</script>")
    for i in range(52):
        r = c.put(
            base + f"/students/{s['id']}",
            json={
                "name": f"Renamed {i}",
                "phone": "000",
                "group": "Test",
                "monthly_fee": "100",
                "start_month": "2026-01",
            },
        )
        assert r.status_code == 200, r.text
    assert c.delete(base + f"/students/{s['id']}").status_code == 204
    first = c.get(base + "/activity").json()
    second = c.get(base + f"/activity?before={first['next_before']}").json()
    ids = [e["id"] for e in first["items"] + second["items"]]
    assert len(ids) == 54 and len(set(ids)) == 54
    assert first["items"][0]["action"] == "student.delete"
    assert second["items"][-1]["student_name"] == "<script>old</script>"
    assert second["next_before"] is None
    assert c.get(base + "/activity?before=bad").status_code == 422


def test_schema_migration_keeps_existing_payment_and_does_not_forge_events(tmp_path):
    database = Database(tmp_path / "old.sqlite3")
    database.initialize()
    with database.connect(write=True) as db:
        db.execute(
            "INSERT INTO students(name,phone,group_name,monthly_fee_cents,start_month) "
            "VALUES('A','000','B',10000,'2026-01')"
        )
        db.execute(
            "INSERT INTO payments(student_id,amount_cents,paid_on,original_amount_cents) "
            "VALUES(1,5000,'2026-10-15',5000)"
        )
        db.execute("DROP TABLE activity")
        db.execute("ALTER TABLE payments DROP COLUMN voided_at")
        db.execute("ALTER TABLE payments DROP COLUMN void_reason")
        db.execute("PRAGMA user_version=3")
    database.initialize()
    database.initialize()
    with database.connect() as db:
        row = db.execute("SELECT * FROM payments").fetchone()
        assert row["amount_cents"] == 5000 and row["voided_at"] is None
        assert db.execute("SELECT COUNT(*) FROM activity").fetchone()[0] == 0
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4


def test_foreign_void_and_replacement_freeze_each_rate(ledger, request, monkeypatch):
    c, base, _ = ledger
    quote = {
        "status": "fresh",
        "source": "CBR",
        "rate_date": "2026-10-29",
        "rates": {"UZS": "1", "RUB": "150", "USD": "12000"},
    }
    if base:
        module = request.getfixturevalue("hosted")[3]

        async def fx(_db):
            return quote

        monkeypatch.setattr(module, "quote", fx)
    else:
        from app.exchange_rates import ExchangeRateService

        monkeypatch.setattr(ExchangeRateService, "get", lambda _self: quote)
    s = new_student(c, base)
    payload = {"student_id": s["id"], "amount": "1.25", "currency": "RUB", "date": "2026-10-15"}
    p = c.post(base + "/payments", json=payload).json()
    assert p["base_amount"] == "187.50"
    quote["rates"]["RUB"] = "200"
    old = c.post(base + f"/payments/{p['id']}/void", json={"reason": "Correction"}).json()
    new = c.post(base + "/payments", json=payload).json()
    assert old["base_amount"] == "187.50" and old["exchange_rate"] == "150"
    assert new["base_amount"] == "250.00" and new["exchange_rate"] == "200"
    result = c.get(base + f"/students/{s['id']}/statement?month=2026-10").json()
    assert result["paid"] == "250.00" and len(result["payments"]) == 2


def test_void_limits_and_failed_writes_do_not_change_ledger(ledger):
    c, base, other = ledger
    s = new_student(c, base)
    p = c.post(
        base + "/payments", json={"student_id": s["id"], "amount": "25.10", "date": "2026-10-15"}
    ).json()
    before = c.get(base + "/activity").json()
    url = base + f"/payments/{p['id']}/void"
    assert c.post(url, json={"reason": "", "amount": "99"}).status_code == 422
    assert (
        c.post(base + "/payments/9223372036854775808/void", json={"reason": "Invalid"}).status_code
        == 422
    )
    assert c.get(base + "/activity?before=0").status_code == 422
    assert c.get(base + "/activity").json() == before
    history = c.get(base + f"/students/{s['id']}/payments").json()
    assert not history[0].get("voided_at")
    if other:
        assert (
            other.post(
                url, json={"reason": "CSRF"}, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        other.delete(base + "/session")
        assert other.get(base + "/activity").status_code == 401
        assert other.post(url, json={"reason": "No session"}).status_code == 401
