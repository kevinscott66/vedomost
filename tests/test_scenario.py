"""The teaching asset is derived from ledger rules and cannot drift silently."""

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from scripts.build_scenario import build_example, render_asset


def test_example_preserves_booking_and_changes_only_reference_display():
    data = build_example()
    assert data["kind"] == "fictional_teaching_example"
    assert data["initial"]["debt"] == "400000.00"
    assert data["payment"] == {
        "amount": "10.00",
        "currency": "USD",
        "base_amount": "120000.00",
        "exchange_rate": "12000",
    }
    assert data["booked"]["paid"] == "520000.00"
    assert data["booked"]["debt"] == "280000.00"
    assert data["changed"] == data["booked"]
    assert data["display"] == {"booked_usd": "23.33", "changed_usd": "18.67"}
    assert Decimal(data["payment"]["base_amount"]) == (
        Decimal(data["payment"]["amount"]) * Decimal(data["payment"]["exchange_rate"])
    )
    assert "CBU" not in render_asset()  # No synthetic quote is presented as an official quote.
    assert "CBR" not in render_asset()


def test_committed_fixture_matches_current_domain_rules():
    assert Path("app/static/scenario-data.js").read_text() == render_asset()


def test_tour_route_preserves_ledger(tmp_path):
    with TestClient(
        create_app(tmp_path / "ledger.sqlite3"),
        client=("127.0.0.1", 50200),
        base_url="http://127.0.0.1",
    ) as client:
        assert client.get("/students").json() == []
        assert client.get("/try").status_code == 200
        assert client.get("/static/scenario-data.js").status_code == 200
        assert client.get("/students").json() == []
