from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "ledger.sqlite3"), base_url="http://127.0.0.1") as c:
        yield c


def student(client, fee="1000.00", **changes):
    data = dict(name="Анна", phone="+7 000 000-00-00", group="А2", monthly_fee=fee)
    data.update(changes)
    response = client.post("/students", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def pay(client, sid, amount, date="2026-10-15"):
    return client.post("/payments", json=dict(student_id=sid, amount=amount, date=date))


def report(client, month="2026-10"):
    response = client.get("/debtors", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def test_crud_and_history_protection(client):
    s = student(client)
    assert client.get("/students").json() == [s]
    data = {k: v for k, v in s.items() if k != "id"}
    data.update(name="Анна Петрова", monthly_fee="1200.50")
    assert client.put(f"/students/{s['id']}", json=data).json()["name"] == "Анна Петрова"
    assert pay(client, s["id"], "200.00").status_code == 201
    assert client.delete(f"/students/{s['id']}").status_code == 409
    assert client.get(f"/students/{s['id']}/payments").json()[0]["amount"] == "200.00"
    other = student(client, name="Борис")
    assert client.delete(f"/students/{other['id']}").status_code == 204
    assert client.get(f"/students/{other['id']}").status_code == 404


def test_partial_full_overpayment_and_zero_fee(client):
    s = student(client)
    student(client, "0")
    assert report(client)["total_debt"] == "1000.00"
    pay(client, s["id"], "300.10")
    pay(client, s["id"], "199.90")
    r = report(client)
    assert len(r["debtors"]) == 1
    assert r["debtors"][0]["paid"] == "500.00"
    assert r["total_debt"] == "500.00"
    pay(client, s["id"], "500")
    assert report(client)["debtors"] == []
    pay(client, s["id"], "50")
    assert report(client)["debtors"] == []
    assert report(client, "2026-11")["total_debt"] == "1000.00"


def test_month_boundaries_and_decimal_precision(client):
    s = student(client, "0.30")
    for amount, day in [
        ("9", "2026-11-30"),
        ("0.1", "2026-12-01"),
        ("0.1", "2026-12-31"),
        ("9", "2027-01-01"),
    ]:
        assert pay(client, s["id"], amount, day).status_code == 201
    assert report(client, "2026-12")["total_debt"] == "0.10"
    pay(client, s["id"], "0.10", "2026-12-15")
    assert report(client, "2026-12")["debtors"] == []


@pytest.mark.parametrize("amount", ["0", "-1", "0.001", "NaN", "Infinity", "10000000000"])
def test_invalid_amount(client, amount):
    s = student(client)
    assert pay(client, s["id"], amount).status_code == 422


@pytest.mark.parametrize(
    "month", ["2026-13", "2026-00", "2026-1", "0000-01", "invalid", "2026-10-01"]
)
def test_invalid_month(client, month):
    assert client.get("/debtors", params={"month": month}).status_code == 422


def test_not_found_and_bad_fields(client):
    assert pay(client, 999, "10").status_code == 404
    assert client.get("/students/999/payments").status_code == 404
    assert client.delete("/students/999").status_code == 404
    s = student(client)
    assert pay(client, s["id"], "10", "2026-02-30").status_code == 422
    assert (
        client.post(
            "/students", json=dict(name=" ", phone="123", group="A", monthly_fee="1")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/students", json=dict(name="A", phone="123", group="A", monthly_fee="-1")
        ).status_code
        == 422
    )


def test_total_sort_and_current_tariff(client):
    a = student(client, "100")
    b = student(client, "200")
    rows = report(client)["debtors"]
    assert [r["id"] for r in rows] == [b["id"], a["id"]]
    assert Decimal(report(client)["total_debt"]) == Decimal("300")
    data = {k: v for k, v in a.items() if k != "id"}
    data["monthly_fee"] = "150"
    client.put(f"/students/{a['id']}", json=data)
    assert report(client, "2025-01")["total_debt"] == "350.00"


def test_persistence_after_restart(tmp_path):
    path = tmp_path / "db.sqlite3"
    with TestClient(create_app(path), base_url="http://127.0.0.1") as c:
        s = student(c)
        pay(c, s["id"], "25")
    with TestClient(create_app(path), base_url="http://127.0.0.1") as c:
        assert len(c.get("/students").json()) == 1
        assert report(c)["total_debt"] == "975.00"


def test_static_page_and_docs(client):
    assert client.get("/").status_code == 200
    assert "Ведомость" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_demo_does_not_duplicate_or_overwrite(tmp_path):
    import subprocess
    import sys

    path = tmp_path / "demo.sqlite3"
    command = [sys.executable, "-m", "app.demo", "--database", str(path)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    assert subprocess.run(command, capture_output=True).returncode != 0
    with TestClient(create_app(path), base_url="http://127.0.0.1") as c:
        assert len(c.get("/students").json()) == 4
        assert len(report(c, date.today().strftime("%Y-%m"))["debtors"]) == 3
