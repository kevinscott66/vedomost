"""Regression tests for the local browser boundary and payment retries."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.database import STATIC, Database, database_path
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "db.sqlite3"), base_url="http://127.0.0.1:8773") as c:
        yield c


def create_student(client):
    r = client.post(
        "/students",
        json={
            "name": "Demo",
            "phone": "000",
            "group": "A",
            "monthly_fee": "800000.00",
            "start_month": "2026-10",
        },
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_rebinding_and_cross_origin_requests_rejected(client):
    assert client.get("/students", headers={"Host": "attacker.example:8773"}).status_code == 400
    for origin in ["https://attacker.example", "null", "http://127.0.0.1:9999"]:
        r = client.post("/students", headers={"Origin": origin}, json={})
        assert r.status_code == 403
    assert client.post("/students", content="{}").status_code == 415
    assert client.get("/students").json() == []
    r = client.post("/students", headers={"Origin": "http://127.0.0.1:8773"}, json={})
    assert r.status_code == 422  # accepted origin, invalid model
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_idempotent_payment_retries_are_atomic(client):
    sid = create_student(client)
    payload = {"student_id": sid, "amount": "200000.00", "date": "2026-10-28"}
    headers = {"Idempotency-Key": "same-retry-key-123456"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies = list(
            pool.map(lambda _: client.post("/payments", json=payload, headers=headers), range(4))
        )
    assert all(r.status_code == 201 for r in replies)
    assert len({r.json()["id"] for r in replies}) == 1
    assert len(client.get(f"/students/{sid}/payments").json()) == 1
    payload["amount"] = "200000.0"  # equivalent decimal spelling is the same request
    assert (
        client.post("/payments", json=payload, headers=headers).json()["id"]
        == replies[0].json()["id"]
    )
    payload["amount"] = "1.00"
    assert client.post("/payments", json=payload, headers=headers).status_code == 409
    assert client.get("/debtors?month=2026-10").json()["total_debt"] == "600000.00"


def test_database_configuration_cannot_publish_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "configured.sqlite3"))
    assert database_path() == tmp_path / "configured.sqlite3"
    assert database_path(tmp_path / "explicit.sqlite3") == tmp_path / "explicit.sqlite3"
    with pytest.raises(ValueError):
        Database(STATIC / "ledger.sqlite3")


def test_schema_upgrade_preserves_records_and_constraints(tmp_path):
    path = tmp_path / "old.sqlite3"
    # Recreate the original schema without the retry table/version marker.
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE students(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                phone TEXT NOT NULL, group_name TEXT NOT NULL,
                monthly_fee_cents INTEGER NOT NULL CHECK(monthly_fee_cents >= 0));
            CREATE TABLE payments(id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0), paid_on TEXT NOT NULL);
            INSERT INTO students VALUES(1,'Demo','000','A',80000000);
            INSERT INTO payments VALUES(1,1,20000000,'2026-10-28');
        """)
    database = Database(path)
    database.initialize()
    database.initialize()
    with database.connect(write=True) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT amount_cents FROM payments").fetchone()[0] == 20000000
        legacy = db.execute(
            "SELECT original_amount_cents,currency,exchange_rate,rate_date,rate_source "
            "FROM payments"
        ).fetchone()
        assert tuple(legacy) == (20000000, "UZS", "1", None, None)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM students WHERE id=1")


def test_concurrent_delete_and_payment_preserve_references(client):
    sid = create_student(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        payment = pool.submit(
            client.post,
            "/payments",
            json={"student_id": sid, "amount": "1.00", "date": "2026-10-28"},
        )
        deletion = pool.submit(client.delete, f"/students/{sid}")
        codes = payment.result().status_code, deletion.result().status_code
    assert codes in {(201, 409), (404, 204)}
