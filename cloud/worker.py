"""Hosted, isolated demo. Durable state is in D1, never in the Worker filesystem."""

import asyncio
import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from domain import DomainError, handle, seed
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fx_source import FALLBACK, normalize_cbr, normalize_cbu
from workers import asgi, fetch

BASE = "/demos/vedomost"
COOKIE = "__Secure-vedomost-demo"
TTL = 90 * 86400
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def field(obj, key, default=None):
    if obj is None:
        return default
    try:
        return obj[key]
    except (KeyError, TypeError):
        return getattr(obj, key, default)


def output(data=None, status=200):
    return Response(status_code=status) if status == 204 else JSONResponse(data, status_code=status)


def session_response(token, expires):
    response = output({"expires_at": expires, "mode": "demo"})
    response.set_cookie(
        COOKIE,
        token,
        max_age=TTL,
        secure=True,
        httponly=True,
        samesite="strict",
        path=BASE + "/",
    )
    return response


async def quota(db, key, maximum, seconds):
    now = int(datetime.now(timezone.utc).timestamp())
    bucket = hashlib.sha256(f"{key}:{now // seconds}".encode()).hexdigest()
    row = (
        await db.prepare(
            "INSERT INTO rate_buckets(id,count,expires) VALUES(?,1,?) "
            "ON CONFLICT(id) DO UPDATE SET count=count+1 RETURNING count"
        )
        .bind(bucket, now + seconds + 3600)
        .first()
    )
    return int(field(row, "count")) <= maximum


async def read_session(request):
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        return None
    return (
        await request.scope["env"]
        .DB.prepare("SELECT state,version,expires FROM sessions WHERE id=? AND expires>?")
        .bind(token, int(datetime.now(timezone.utc).timestamp()))
        .first()
    )


async def quote(db):
    now = datetime.now(timezone.utc)
    epoch = int(now.timestamp())
    today = now.astimezone(timezone(timedelta(hours=3))).date()
    row = await db.prepare("SELECT snapshot,fetched FROM fx_cache WHERE id=1").first()
    prior = json.loads(field(row, "snapshot")) if row else None
    if (
        row
        and epoch - int(field(row, "fetched")) < (3600 if prior.get("status") == "fresh" else 300)
        and prior.get("checked_day") == today.isoformat()
    ):
        return {k: v for k, v in prior.items() if k != "checked_day"}
    sources = [
        (
            f"https://cbu.uz/ru/arkhiv-kursov-valyut/json/all/{today.isoformat()}/",
            normalize_cbu,
            "CBU",
        ),
        (
            f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={today:%d/%m/%Y}",
            normalize_cbr,
            "CBR",
        ),
    ]
    for url, normalize, source in sources:
        try:

            async def load():
                result = await fetch(url, redirect="manual")
                if not result.ok:
                    raise ValueError("Rate source unavailable")
                return (await result.text()).encode()

            data = await asyncio.wait_for(load(), timeout=5)
            rates, effective = normalize(data, today)
            item = {
                "base": "UZS",
                "rates": {"UZS": 1, **{k: float(v) for k, v in rates.items()}},
                "booking_rates": {"UZS": "1", **{k: format(v, "f") for k, v in rates.items()}},
                "rate_date": effective.isoformat(),
                "fetched_at": now.isoformat(),
                "source": source,
                "status": "fresh",
                "checked_day": today.isoformat(),
            }
            await (
                db.prepare(
                    "INSERT INTO fx_cache(id,snapshot,fetched) VALUES(1,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot,"
                    "fetched=excluded.fetched"
                )
                .bind(json.dumps(item), epoch)
                .run()
            )
            return {k: v for k, v in item.items() if k != "checked_day"}
        except Exception as error:
            print(f"FX source {source}: {type(error).__name__}: {error}")
            continue
    failed = dict(prior or FALLBACK)
    failed["status"] = "stale" if failed.get("source") != "reference" else "fallback"
    failed["checked_day"] = today.isoformat()
    await (
        db.prepare(
            "INSERT INTO fx_cache(id,snapshot,fetched) VALUES(1,?,?) "
            "ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot,fetched=excluded.fetched"
        )
        .bind(json.dumps(failed), epoch)
        .run()
    )
    return {k: v for k, v in failed.items() if k != "checked_day"}


@app.middleware("http")
async def boundary(request: Request, call_next):
    path = request.url.path
    if not path.startswith(BASE + "/") and path != BASE:
        return output({"detail": "Not found"}, 404)
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return output({"detail": "Cross-origin writes are not allowed"}, 403)
        if (
            request.method != "DELETE"
            and request.headers.get("content-type", "").split(";")[0] != "application/json"
        ):
            return output({"detail": "Content-Type must be application/json"}, 415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                return output({"detail": "Request too large"}, 413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            ),
        }
    )
    return response


@app.api_route(BASE + "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def dispatch(path: str, request: Request):
    db = request.scope["env"].DB
    if path == "session":
        if request.method == "POST":
            existing = await read_session(request)
            if existing:
                token = request.cookies[COOKIE]
                now = int(datetime.now(timezone.utc).timestamp())
                renewed = await (
                    db.prepare(
                        "UPDATE sessions SET expires=MAX(expires,?) "
                        "WHERE id=? AND expires>? RETURNING expires"
                    )
                    .bind(now + TTL, token, now)
                    .first()
                )
                if renewed:
                    return session_response(token, int(field(renewed, "expires")))
            ip = request.headers.get("cf-connecting-ip", "local")
            if not await quota(db, "create:" + ip, 20, 3600) or not await quota(
                db, "global-create", 300, 3600
            ):
                return output({"detail": "Try again later"}, 429)
            token = secrets.token_hex(32)
            expires = int(datetime.now(timezone.utc).timestamp()) + TTL
            today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3))).date()
            await (
                db.prepare("INSERT INTO sessions(id,state,version,expires) VALUES(?,?,0,?)")
                .bind(token, json.dumps(seed(today), ensure_ascii=False), expires)
                .run()
            )
            return session_response(token, expires)
        if request.method == "DELETE":
            token = request.cookies.get(COOKIE, "")
            if re.fullmatch(r"[a-f0-9]{64}", token):
                await db.prepare("DELETE FROM sessions WHERE id=?").bind(token).run()
            response = output(status=204)
            response.delete_cookie(
                COOKIE, path=BASE + "/", secure=True, httponly=True, samesite="strict"
            )
            return response
        return output({"detail": "Method not allowed"}, 405)
    if path == "exchange-rates" and request.method == "GET":
        return output(await quote(db))
    api_path = "/" + path.rstrip("/")
    if (
        path == "debtors"
        or path == "payments"
        or path == "students"
        or path.startswith("students/")
    ):
        row = await read_session(request)
        if row is None:
            return output({"detail": "Demo session expired; reload the page"}, 401)
        token = request.cookies[COOKIE]
        if not await quota(db, "request:" + token, 120, 60):
            return output({"detail": "Try again later"}, 429)
        body = None
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                body = await request.json()
            except ValueError:
                return output({"detail": "Invalid JSON"}, 422)
            if not isinstance(body, dict):
                return output({"detail": "JSON object required"}, 422)
        current_quote = None
        # Replays do not depend on a current rate. Fetch only if a new foreign write needs it.
        state = json.loads(field(row, "state"))
        key = request.headers.get("idempotency-key")
        if (
            path == "payments"
            and request.method == "POST"
            and body.get("currency", "UZS") != "UZS"
            and key not in state["requests"]
        ):
            current_quote = await quote(db)
        for _attempt in range(4):
            state = json.loads(field(row, "state"))
            try:
                status, data, changed, updated = handle(
                    state,
                    request.method,
                    api_path,
                    dict(request.query_params),
                    body,
                    key,
                    current_quote,
                )
            except DomainError as error:
                return output({"detail": error.detail}, error.status)
            if not changed:
                return output(data, status)
            serialized = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
            if len(serialized.encode()) > 1000000:
                return output({"detail": "Demo storage limit reached"}, 422)
            result = (
                await db.prepare(
                    "UPDATE sessions SET state=?,version=version+1 "
                    "WHERE id=? AND version=? AND expires>?"
                )
                .bind(
                    serialized,
                    token,
                    int(field(row, "version")),
                    int(datetime.now(timezone.utc).timestamp()),
                )
                .run()
            )
            if int(field(field(result, "meta"), "changes", 0)) == 1:
                return output(data, status)
            row = await read_session(request)
            if row is None:
                return output({"detail": "Demo session expired; reload the page"}, 401)
        return output({"detail": "Database busy; retry later"}, 503)
    if request.method != "GET":
        return output({"detail": "Not found"}, 404)
    page = path.rstrip("/") or "index.html"
    if page.startswith("static/"):
        page = page[len("static/") :]
    if page in {"privacy", "terms", "rights", "docs", "case", "try"}:
        page += ".html"
    if ".." in page or "\\" in page:
        return output({"detail": "Not found"}, 404)
    asset = await request.scope["env"].ASSETS.fetch(f"https://assets.local/{page}")
    return Response(
        bytes(await asset.bytes()), status_code=asset.status, headers=dict(asset.headers)
    )


class Default(asgi.entrypoint(app)):
    async def scheduled(self, controller, env, ctx):
        now = int(datetime.now(timezone.utc).timestamp())
        await self.env.DB.prepare("DELETE FROM sessions WHERE expires<=?").bind(now).run()
        await self.env.DB.prepare("DELETE FROM rate_buckets WHERE expires<=?").bind(now).run()
