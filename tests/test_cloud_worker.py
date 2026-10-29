"""Hosted boundary and D1 persistence, using SQLite as an async binding test double."""

import importlib.util
import sqlite3
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BASE = "/demos/vedomost"


class Statement:
    def __init__(self, db, sql):
        self.db, self.sql, self.args = db, sql, ()

    def bind(self, *args):
        self.args = args
        return self

    async def first(self):
        with self.db:
            row = self.db.execute(self.sql, self.args).fetchone()
        return dict(row) if row else None

    async def run(self):
        with self.db:
            cursor = self.db.execute(self.sql, self.args)
        return {"meta": {"changes": cursor.rowcount}}


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    db = sqlite3.connect(tmp_path / "d1.sqlite3", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript((ROOT / "cloud/schema.sql").read_text())
    monkeypatch.syspath_prepend(str(ROOT / "cloud"))
    fake = types.ModuleType("workers")
    fake.asgi = types.SimpleNamespace(entrypoint=lambda app: object)
    fake.fetch = None
    monkeypatch.setitem(sys.modules, "workers", fake)
    # Use canonical FX functions directly; generated build files aren't required in CI.
    from app import exchange_rates

    monkeypatch.setitem(sys.modules, "fx_source", exchange_rates)
    spec = importlib.util.spec_from_file_location("hosted_test_worker", ROOT / "cloud/worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = types.SimpleNamespace(DB=types.SimpleNamespace(prepare=lambda sql: Statement(db, sql)))

    async def asgi(scope, receive, send):
        scope["env"] = env
        await module.app(scope, receive, send)

    with (
        TestClient(asgi, base_url="https://demo.example") as a,
        TestClient(asgi, base_url="https://demo.example") as b,
    ):
        yield a, b, db, module
    db.close()


def init(client):
    result = client.post(BASE + "/session", json={})
    assert result.status_code == 200, result.text
    cookie = result.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie


def test_hosted_sessions_are_isolated_and_writes_persist(hosted):
    a, b, db, _ = hosted
    init(a)
    init(b)
    initial = a.get(BASE + "/students").json()
    created = a.post(
        BASE + "/students",
        json={
            "name": "Demo",
            "phone": "000",
            "group": "X",
            "monthly_fee": "100",
            "start_month": "2026-01",
        },
    )
    assert created.status_code == 201, created.text
    assert len(a.get(BASE + "/students").json()) == len(initial) + 1
    assert len(b.get(BASE + "/students").json()) == len(initial)
    sid = created.json()["id"]
    payload = {"student_id": sid, "amount": "12.50", "date": "2026-10-28"}
    headers = {"Idempotency-Key": "hosted-retry-key-1234"}
    first = a.post(BASE + "/payments", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    assert a.post(BASE + "/payments", json=payload, headers=headers).json() == first.json()
    assert len(a.get(BASE + f"/students/{sid}/payments").json()) == 1
    assert b.get(BASE + f"/students/{sid}").status_code == 404
    assert db.execute("select count(*) from sessions").fetchone()[0] == 2
    assert a.delete(BASE + "/session").status_code == 204
    assert a.get(BASE + "/students").status_code == 401


def test_hosted_csrf_limits_and_expiry(hosted):
    a, _, db, _ = hosted
    assert (
        a.post(BASE + "/session", json={}, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert a.post(BASE + "/session", content="{}").status_code == 415
    assert (
        a.post(
            BASE + "/session",
            content='"' + "x" * 17000 + '"',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert a.get("/students").status_code == 404
    init(a)
    db.execute("update sessions set expires=0")
    db.commit()
    assert a.get(BASE + "/students").status_code == 401


def test_reopening_demo_renews_cookie_and_preserves_ledger(hosted):
    a, _, db, module = hosted
    init(a)
    token = a.cookies.get(module.COOKIE)
    created = a.post(
        BASE + "/students",
        json={
            "name": "Returning visitor",
            "phone": "000",
            "group": "QA",
            "monthly_fee": "100",
            "start_month": "2026-01",
        },
    )
    assert created.status_code == 201
    now = int(module.datetime.now(module.timezone.utc).timestamp())
    db.execute("UPDATE sessions SET expires=?", (now + 60,))
    db.commit()
    before = db.execute("SELECT state,version FROM sessions").fetchone()
    resumed = a.post(BASE + "/session", json={})
    assert resumed.status_code == 200
    assert a.cookies.get(module.COOKIE) == token
    assert f"Max-Age={90 * 86400}" in resumed.headers["set-cookie"]
    assert resumed.json()["expires_at"] >= now + 90 * 86400
    after = db.execute("SELECT state,version FROM sessions").fetchone()
    assert tuple(after) == tuple(before)
    assert len(a.get(BASE + "/students").json()) == 5
    db.execute("UPDATE sessions SET expires=0")
    db.commit()
    assert a.post(BASE + "/session", json={}).status_code == 200
    assert a.cookies.get(module.COOKIE) != token
    assert len(a.get(BASE + "/students").json()) == 4


def test_bootstrap_without_cross_tab_lock_only_renews_existing_session(hosted):
    a, _, db, _ = hosted
    headers = {"X-Demo-Require-Session": "1"}
    assert a.post(BASE + "/session", json={}, headers=headers).status_code == 409
    assert db.execute("select count(*) from sessions").fetchone()[0] == 0
    init(a)
    assert a.post(BASE + "/session", json={}, headers=headers).status_code == 200
    assert db.execute("select count(*) from sessions").fetchone()[0] == 1
