import json
import sqlite3
import threading
import time
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.exchange_rates import (
    MAX_BYTES,
    ExchangeRateService,
    normalize_cbr,
    normalize_cbu,
)

CBU = json.dumps(
    [
        {"Ccy": "USD", "Nominal": "1", "Rate": "12000", "Date": "28.10.2026"},
        {"Ccy": "RUB", "Nominal": "10", "Rate": "1500", "Date": "28.10.2026"},
    ]
).encode()
CBR = (
    b'<ValCurs Date="28.10.2026">'
    b"<Valute><CharCode>USD</CharCode><Nominal>1</Nominal><Value>80,00</Value></Valute>"
    b"<Valute><CharCode>UZS</CharCode><Nominal>1000</Nominal><Value>6,67</Value></Valute>"
    b"</ValCurs>"
)
NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def test_cbu_and_cbr_normalization():
    rates, d = normalize_cbu(CBU, date(2026, 10, 28))
    assert rates == {"USD": 12000, "RUB": 150}
    assert d == date(2026, 10, 28)
    rates, d = normalize_cbr(CBR, date(2026, 10, 28))
    assert round(rates["RUB"]) == 150 and round(rates["USD"]) == 11994
    assert d == date(2026, 10, 28)


def test_reject_invalid_dates_values_and_unsafe_or_oversized_xml():
    requested = date(2026, 10, 28)
    with pytest.raises(ValueError):
        normalize_cbu(CBU.replace(b"28.10.2026", b"29.10.2026"), requested)
    with pytest.raises(ValueError):
        normalize_cbu(CBU.replace(b"1500", b"-1500"), requested)
    with pytest.raises(ValueError):
        normalize_cbu(b" " * (MAX_BYTES + 1), requested)
    with pytest.raises(ValueError):
        normalize_cbr(b'<!DOCTYPE x [<!ENTITY e "x">]><ValCurs/>', requested)
    with pytest.raises(ValueError):
        normalize_cbr(b"x" * (MAX_BYTES + 1), requested)
    with pytest.raises(ValueError):
        normalize_cbr(CBR.replace(b"6,67", b"-6,67"), requested)


def test_valid_year_boundary_rate_older_than_one_week():
    rows = json.loads(CBU)
    for row in rows:
        row["Date"] = "31.12.2025"
    rates, rate_date = normalize_cbu(json.dumps(rows).encode(), date(2026, 1, 1))
    assert rates["USD"] == 12000
    assert rate_date == date(2025, 12, 31)


def test_dated_cbr_query(monkeypatch):
    from app import exchange_rates

    urls = []

    def open_url(url):
        urls.append(url)
        if "cbu.uz" in url:
            raise OSError("stubbed outage")
        return CBR

    monkeypatch.setattr(exchange_rates, "_safe_open", open_url)
    rates, rate_date, source = ExchangeRateService._fetch(
        ExchangeRateService.__new__(ExchangeRateService), date(2026, 10, 28)
    )
    assert source == "CBR" and rate_date == date(2026, 10, 28)
    assert "date_req=28/10/2026" in urls[1]


def test_persistence_restart_and_stale_fallback_backoff(tmp_path):
    path = tmp_path / "rates.json"
    service = ExchangeRateService(
        path,
        lambda _: ({"RUB": 151, "USD": 12001}, date(2026, 10, 28), "CBU"),
        lambda: NOW,
    )
    assert service.get()["status"] == "fresh"
    restarted = ExchangeRateService(path, lambda _: (_ for _ in ()).throw(OSError()), lambda: NOW)
    result = restarted.get()
    assert result["status"] == "stale" and result["rates"]["RUB"] == 151
    fallback = ExchangeRateService(
        tmp_path / "missing.json",
        lambda _: (_ for _ in ()).throw(OSError()),
        lambda: NOW,
    )
    assert fallback.get()["status"] == "fallback"
    assert fallback.get()["status"] == "fallback"


def test_invalid_cache_shapes_and_oversized_cache_fall_back(tmp_path):
    cache = tmp_path / "rates.json"
    for content in ("[]", " " * (MAX_BYTES + 1)):
        cache.write_text(content)
        service = ExchangeRateService(
            cache, lambda _: (_ for _ in ()).throw(OSError()), lambda: NOW
        )
        assert service.get()["status"] == "fallback"


def test_ttl_expiry_failure_backoff_and_persistence_failure(tmp_path, monkeypatch):
    ticks = iter([10.0, 3611.0, 3700.0, 3912.0])
    monkeypatch.setattr("app.exchange_rates.time.monotonic", lambda: next(ticks))
    calls = []

    def fetch(_):
        calls.append(1)
        if len(calls) > 1:
            raise OSError("stubbed outage")
        return {"RUB": 150, "USD": 12000}, date(2026, 10, 28), "CBU"

    service = ExchangeRateService(tmp_path / "rates.json", fetch, lambda: NOW)
    assert service.get()["status"] == "fresh"
    assert service.get()["status"] == "stale"  # TTL elapsed; failed refresh
    assert service.get()["status"] == "stale"  # backoff avoids another fetch
    assert len(calls) == 2
    assert service.get()["status"] == "stale"  # retry after backoff also fails
    assert len(calls) == 3

    monkeypatch.setattr("app.exchange_rates.time.monotonic", lambda: 5000.0)
    broken = ExchangeRateService(
        tmp_path / "unwritable" / "rates.json",
        lambda _: ({"RUB": 150, "USD": 12000}, date(2026, 10, 28), "CBU"),
        lambda: NOW,
    )
    monkeypatch.setattr(broken, "_persist", lambda _: (_ for _ in ()).throw(OSError()))
    assert broken.get()["status"] == "fresh"


def test_moscow_midnight_invalidates_fresh_ttl_cache(tmp_path, monkeypatch):
    clock = [datetime(2026, 10, 28, 20, 59, tzinfo=timezone.utc)]
    days = []

    def fetch(requested):
        days.append(requested)
        if len(days) == 1:
            clock[0] = datetime(2026, 10, 28, 21, 0, tzinfo=timezone.utc)
        return {"RUB": 150, "USD": 12000}, requested, "CBU"

    monkeypatch.setattr("app.exchange_rates.time.monotonic", lambda: 100.0)
    service = ExchangeRateService(tmp_path / "rates.json", fetch, lambda: clock[0])
    first = service.get()
    assert first["rate_date"] == "2026-10-28"
    assert first["fetched_at"] == "2026-10-28T21:00:00+00:00"
    clock[0] = datetime(2026, 10, 28, 21, 0, tzinfo=timezone.utc)
    assert service.get()["rate_date"] == "2026-10-29"
    assert days == [date(2026, 10, 28), date(2026, 10, 29)]


def test_ttl_backoff_and_concurrent_requests_fetch_once(tmp_path, monkeypatch):
    calls = []
    barrier = threading.Barrier(6)

    def fetch(_):
        calls.append(1)
        time.sleep(0.02)
        return {"RUB": 150, "USD": 12000}, date(2026, 10, 28), "CBU"

    service = ExchangeRateService(tmp_path / "rates.json", fetch, lambda: NOW)
    monkeypatch.setattr("app.exchange_rates.time.monotonic", lambda: 100.0)
    results = []

    def call():
        barrier.wait()
        results.append(service.get())

    threads = [threading.Thread(target=call) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1 and len(results) == 6
    assert service.get()["status"] == "fresh"


def test_api_returns_contract_without_network(tmp_path, monkeypatch):
    from app.exchange_rates import ExchangeRateService

    monkeypatch.setattr(
        ExchangeRateService,
        "_fetch",
        lambda self, _: ({"RUB": 150, "USD": 12000}, date(2026, 10, 28), "CBU"),
    )
    from app.main import create_app

    with TestClient(create_app(tmp_path / "db.sqlite3"), base_url="http://localhost") as client:
        response = client.get("/exchange-rates")
    assert response.status_code == 200
    assert response.json()["base"] == "UZS"
    assert response.json()["rates"] == {"UZS": 1.0, "RUB": 150, "USD": 12000}


def test_rate_cache_cannot_overwrite_database_with_matching_name(tmp_path, monkeypatch):
    from app.exchange_rates import ExchangeRateService
    from app.main import create_app

    monkeypatch.setattr(
        ExchangeRateService,
        "_fetch",
        lambda self, _: ({"RUB": 150, "USD": 12000}, date(2026, 10, 28), "CBU"),
    )
    db_path = tmp_path / "exchange-rates.json"
    cache_path = tmp_path / "exchange-rates.json.exchange-rates.json"
    with TestClient(create_app(db_path), base_url="http://localhost") as client:
        created = client.post(
            "/students",
            json={
                "name": "Test Student",
                "phone": "+998900000000",
                "group": "A",
                "monthly_fee": "100",
                "start_month": "2026-10",
            },
        )
        assert created.status_code == 201
        assert client.get("/exchange-rates").status_code == 200
        students = client.get("/students")
        assert students.status_code == 200 and len(students.json()) == 1

    with sqlite3.connect(db_path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert cache_path.is_file()
