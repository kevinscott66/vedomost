from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(tmp_path / "dates.sqlite3"),
        client=("127.0.0.1", 50000),
        base_url="http://127.0.0.1",
    ) as c:
        yield c


def add(client, start="2026-09"):
    r = client.post(
        "/students",
        json={
            "name": "Demo",
            "phone": "000",
            "group": "A",
            "monthly_fee": "800000",
            "start_month": start,
        },
    )
    assert r.status_code == 201
    return r.json()


def test_no_infinite_historical_charges_and_backdating(client):
    s = add(client)
    for month in ["0001-01", "0099-12", "1900-01", "2026-08"]:
        r = client.get("/debtors", params={"month": month})
        assert r.status_code == 200
        assert r.json()["debtors"] == []
        assert r.json()["total_debt"] == "0.00"
    assert client.get("/debtors?month=2026-09").json()["total_debt"] == "800000.00"
    payload = {"student_id": s["id"], "amount": "300000", "date": "2026-09-15"}
    headers = {"Idempotency-Key": "0" * 32}
    assert client.post("/payments", json=payload, headers=headers).status_code == 201
    assert client.post("/payments", json=payload, headers=headers).status_code == 201
    assert client.get("/debtors?month=2026-09").json()["total_debt"] == "500000.00"
    assert client.get("/debtors?month=2026-10").json()["total_debt"] == "800000.00"
    payload["date"] = "2026-08-31"
    assert client.post("/payments", json=payload).status_code == 422
    data = {k: v for k, v in s.items() if k != "id"}
    data["start_month"] = "2026-10"
    assert client.put(f"/students/{s['id']}", json=data).status_code == 409


def test_default_start_and_legacy_updates_preserve_start(client):
    s = add(client, None)
    assert s["start_month"] == date.today().strftime("%Y-%m")
    data = {k: v for k, v in s.items() if k not in {"id", "start_month"}}
    data["name"] = "Updated"
    assert client.put(f"/students/{s['id']}", json=data).json()["start_month"] == s["start_month"]


@pytest.mark.parametrize("start", ["0000-01", "2026-13", "2026-1", "1900-02-29", "10000-01"])
def test_bad_enrollment_month(client, start):
    r = client.post(
        "/students",
        json={
            "name": "Demo",
            "phone": "000",
            "group": "A",
            "monthly_fee": "1",
            "start_month": start,
        },
    )
    assert r.status_code == 422


def test_final_calendar_month_and_id_bounds(client):
    s = add(client, "9999-12")
    assert client.get("/debtors?month=9999-12").json()["total_debt"] == "800000.00"
    r = client.post("/payments", json={"student_id": s["id"], "amount": "1", "date": "9999-12-31"})
    assert r.status_code == 201
    assert client.get("/debtors?month=9999-12").json()["total_debt"] == "799999.00"
    for sid in [0, -1, 2**63, 10**100]:
        for route in [f"/students/{sid}", f"/students/{sid}/payments"]:
            assert client.get(route).status_code == 422
        assert (
            client.post(
                "/payments", json={"student_id": sid, "amount": "1", "date": "2026-10-28"}
            ).status_code
            == 422
        )


def test_enrollment_migration_keeps_earliest_known_history(tmp_path):
    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE students(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,
                group_name TEXT,monthly_fee_cents INTEGER);
            CREATE TABLE payments(id INTEGER PRIMARY KEY,student_id INTEGER,
                amount_cents INTEGER,paid_on TEXT);
            INSERT INTO students VALUES(1,'Demo','000','A',100);
            INSERT INTO payments VALUES(1,1,50,'2020-02-29');
            """
        )
    database = Database(path)
    database.initialize()
    database.initialize()
    with database.connect() as db:
        assert db.execute("SELECT start_month FROM students").fetchone()[0] == "2020-02"
        assert db.execute("SELECT paid_on FROM payments").fetchone()[0] == "2020-02-29"
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert tuple(
            db.execute(
                "SELECT original_amount_cents,currency,exchange_rate FROM payments"
            ).fetchone()
        ) == (50, "UZS", "1")
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
