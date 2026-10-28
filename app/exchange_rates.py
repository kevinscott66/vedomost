"""Cached official FX snapshots for indicative display and payment booking."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

FALLBACK = {
    "base": "UZS",
    "rates": {"UZS": 1.0, "RUB": 148.04, "USD": 11918.98},
    "rate_date": "2026-10-28",
    "fetched_at": None,
    "status": "fallback",
    "source": "reference",
}
MAX_BYTES = 256 * 1024
# Official rate tables can skip dates across holidays and year boundaries; accept
# the latest published effective date for up to 31 days, while rejecting future data.
MAX_RATE_AGE = timedelta(days=31)


def _safe_open(url: str) -> bytes:
    host = "cbu.uz" if "cbu.uz/" in url else "www.cbr.ru"

    class FixedHostRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            from urllib.parse import urlparse

            parsed = urlparse(newurl)
            if parsed.scheme != "https" or parsed.hostname not in {host, "cbu.uz", "www.cbr.ru"}:
                raise urllib.error.URLError("Unexpected redirect host")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(FixedHostRedirect)
    with opener.open(url, timeout=3) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Rate response too large")
    return data


def _as_decimal(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Invalid rate")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid rate") from None
    if not result.is_finite():
        raise ValueError("Invalid rate")
    return result


def _valid_rate(value) -> bool:
    try:
        rate = _as_decimal(value)
        return Decimal("0.000001") <= rate <= Decimal("1000000000")
    except ValueError:
        return False


def _public_rate(value: Decimal) -> float:
    return float(value)


def _booking_rate(value: Decimal) -> str:
    return format(value, "f")


def normalize_cbu(data: bytes, requested: date) -> tuple[dict[str, Decimal], date]:
    if len(data) > MAX_BYTES:
        raise ValueError("Rate response too large")
    rows = json.loads(data, parse_float=Decimal, parse_int=Decimal)
    if not isinstance(rows, list):
        raise ValueError("Invalid CBU response")
    result: dict[str, Decimal] = {}
    dates: list[date] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("Ccy") not in {"USD", "RUB"}:
            continue
        d = datetime.strptime(row["Date"], "%d.%m.%Y").date()
        nominal, rate = _as_decimal(row["Nominal"]), _as_decimal(row["Rate"])
        if not _valid_rate(nominal) or not _valid_rate(rate):
            raise ValueError("Invalid CBU nominal/rate")
        with localcontext() as ctx:
            ctx.prec = 60
            normalized = rate / nominal
        if d > requested or d < requested - MAX_RATE_AGE or not _valid_rate(normalized):
            raise ValueError("Invalid CBU rate date/value")
        code = row["Ccy"]
        if code in result:
            raise ValueError("Duplicate CBU currency")
        result[code] = normalized
        dates.append(d)
    if set(result) != {"USD", "RUB"} or len(set(dates)) != 1:
        raise ValueError("Incomplete CBU response")
    return result, dates[0]


def normalize_cbr(data: bytes, requested: date) -> tuple[dict[str, Decimal], date]:
    if len(data) > MAX_BYTES:
        raise ValueError("Rate response too large")
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)", data, re.I):
        raise ValueError("Unsafe XML")
    root = ET.fromstring(data)
    rate_date = datetime.strptime(root.attrib["Date"], "%d.%m.%Y").date()
    if rate_date > requested or rate_date < requested - MAX_RATE_AGE:
        raise ValueError("Invalid CBR rate date")
    values: dict[str, Decimal] = {}
    for item in root.findall("Valute"):
        code = item.findtext("CharCode")
        if code in {"USD", "UZS"}:
            nominal = _as_decimal(item.findtext("Nominal", "").replace(" ", "").replace(",", "."))
            value = _as_decimal(item.findtext("Value", "").replace(" ", "").replace(",", "."))
            if not _valid_rate(nominal) or not _valid_rate(value):
                raise ValueError("Invalid CBR nominal/value")
            with localcontext() as ctx:
                ctx.prec = 60
                normalized = nominal / value if code == "UZS" else value / nominal
            if not _valid_rate(normalized) or code in values:
                raise ValueError("Invalid CBR rate")
            values[code] = normalized
    if set(values) != {"USD", "UZS"}:
        raise ValueError("Incomplete CBR response")
    per_rub = values["UZS"]
    with localcontext() as ctx:
        ctx.prec = 60
        rates = {"RUB": per_rub, "USD": values["USD"] * per_rub}
    if not all(_valid_rate(v) for v in rates.values()):
        raise ValueError("Invalid CBR cross rate")
    return rates, rate_date


class ExchangeRateService:
    def __init__(self, cache_path: Path, fetcher=None, now=None):
        self.cache_path = Path(cache_path)
        self.fetcher = fetcher or self._fetch
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._snapshot = self._load()
        self._fetched_mono = 0.0
        self._fetched_day: date | None = None
        self._failed_mono = 0.0

    def _load(self):
        try:
            if self.cache_path.stat().st_size > MAX_BYTES:
                raise ValueError("Rate cache too large")
            item = json.loads(self.cache_path.read_text("utf-8"))
            if not isinstance(item, dict):
                raise ValueError("Invalid rate cache")
            raw_rates = item.get("rates")
            if (
                item.get("base") == "UZS"
                and item.get("source") in {"CBU", "CBR"}
                and item.get("status") in {"fresh", "stale"}
                and isinstance(raw_rates, dict)
                and set(raw_rates) == {"UZS", "RUB", "USD"}
                and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) and _valid_rate(v)
                    for v in raw_rates.values()
                )
                and raw_rates["UZS"] == 1
                and isinstance(item.get("rate_date"), str)
                and isinstance(item.get("fetched_at"), str)
            ):
                rate_date = date.fromisoformat(item["rate_date"])
                if rate_date.isoformat() != item["rate_date"]:
                    raise ValueError("Invalid cache date")
                fetched_at = datetime.fromisoformat(item["fetched_at"])
                if fetched_at.tzinfo is None or fetched_at.utcoffset() != timedelta(0):
                    raise ValueError("Cache timestamp must be UTC")
                now = self.now().astimezone(timezone.utc)
                moscow_today = now.astimezone(timezone(timedelta(hours=3))).date()
                if fetched_at > now or rate_date > moscow_today:
                    raise ValueError("Cache date is in the future")
                item["rates"] = {key: float(value) for key, value in raw_rates.items()}
                raw_booking_rates = item.get("booking_rates")
                if raw_booking_rates is not None:
                    if not isinstance(raw_booking_rates, dict) or set(raw_booking_rates) != {
                        "UZS",
                        "RUB",
                        "USD",
                    }:
                        raise ValueError("Invalid cached booking rates")
                    booking_rates = {}
                    for key, value in raw_booking_rates.items():
                        if not isinstance(value, str) or len(value) > 128:
                            raise ValueError("Invalid cached booking rate")
                        booking_rates[key] = _as_decimal(value)
                    if (
                        booking_rates["UZS"] != 1
                        or any(not _valid_rate(value) for value in booking_rates.values())
                        or any(
                            float(booking_rates[key]) != item["rates"][key] for key in booking_rates
                        )
                    ):
                        raise ValueError("Inconsistent cached booking rates")
                    item["booking_rates"] = {
                        key: _booking_rate(value) for key, value in booking_rates.items()
                    }
                item["status"] = "stale"
                return item
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, RecursionError):
            pass
        return dict(FALLBACK, rates=dict(FALLBACK["rates"]))

    def _fetch(self, requested: date):
        stamp = requested.strftime("%d/%m/%Y")
        try:
            payload = _safe_open(
                f"https://cbu.uz/ru/arkhiv-kursov-valyut/json/all/{requested:%Y-%m-%d}/"
            )
            rates, rate_date = normalize_cbu(payload, requested)
            return rates, rate_date, "CBU"
        except Exception:
            payload = _safe_open(f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={stamp}")
            rates, rate_date = normalize_cbr(payload, requested)
            return rates, rate_date, "CBR"

    def _persist(self, item):
        temp_path = None
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.cache_path.parent,
                prefix=f".{self.cache_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp:
                temp_path = Path(temp.name)
                temp.write(json.dumps(item, separators=(",", ":")))
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, self.cache_path)
        except OSError:
            pass
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _copy_snapshot(self):
        copy = dict(self._snapshot, rates=dict(self._snapshot["rates"]))
        if "booking_rates" in copy:
            copy["booking_rates"] = dict(copy["booking_rates"])
        return copy

    def get(self):
        with self._lock:
            now = self.now().astimezone(timezone.utc)
            requested = now.astimezone(timezone(timedelta(hours=3))).date()
            mono = time.monotonic()
            if (
                self._snapshot["status"] == "fresh"
                and self._fetched_day == requested
                and mono - self._fetched_mono < 3600
            ):
                return self._copy_snapshot()
            if self._failed_mono and mono - self._failed_mono < 300:
                return self._current_stale()
            try:
                rates, rate_date, source = self.fetcher(requested)
                if (
                    source not in {"CBU", "CBR"}
                    or not isinstance(rate_date, date)
                    or isinstance(rate_date, datetime)
                ):
                    raise ValueError("Invalid source or rate date")
                if rate_date > requested:
                    raise ValueError("Fetched rate date is in the future")
                rates = {k: _as_decimal(v) for k, v in rates.items()}
                if set(rates) != {"RUB", "USD"} or not all(_valid_rate(v) for v in rates.values()):
                    raise ValueError("Invalid fetched rates")
                item = {
                    "base": "UZS",
                    "rates": {"UZS": 1.0, **{k: _public_rate(v) for k, v in rates.items()}},
                    "booking_rates": {
                        "UZS": "1",
                        **{k: _booking_rate(v) for k, v in rates.items()},
                    },
                    "rate_date": rate_date.isoformat(),
                    "fetched_at": self.now().astimezone(timezone.utc).isoformat(),
                    "status": "fresh",
                    "source": source,
                }
                self._snapshot = item
                self._fetched_mono = mono
                self._fetched_day = requested
                self._failed_mono = 0.0
                try:
                    self._persist(item)
                except OSError:
                    pass
            except Exception:
                self._failed_mono = mono
                self._snapshot["status"] = (
                    "stale" if self._snapshot["source"] != "reference" else "fallback"
                )
            return self._copy_snapshot()

    def _current_stale(self):
        if self._snapshot["source"] != "reference":
            self._snapshot["status"] = "stale"
        return self._copy_snapshot()
