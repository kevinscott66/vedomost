"""Build an isolated teaching example using the real ledger rules, without a database."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloud.domain import handle, seed  # noqa: E402


def build_example():
    original = seed(date(2026, 10, 28))
    query = {"month": "2026-10"}
    _, before, _, _ = handle(original, "GET", "/students/1/statement", query=query)
    # Synthetic rates are test inputs, never requested from or attributed to a bank.
    quote = {
        "status": "fresh",
        "source": "CBU",
        "rate_date": "2026-10-28",
        "booking_rates": {"USD": "12000"},
    }
    _, payment, _, booked_state = handle(
        original,
        "POST",
        "/payments",
        quote=quote,
        body={"student_id": 1, "amount": "10.00", "currency": "USD", "date": "2026-10-28"},
    )
    _, booked, _, _ = handle(booked_state, "GET", "/students/1/statement", query=query)
    changed_quote = deepcopy(quote)
    changed_quote["booking_rates"]["USD"] = "15000"
    _, changed, _, _ = handle(
        booked_state, "GET", "/students/1/statement", query=query, quote=changed_quote
    )
    assert changed == booked

    def totals(statement):
        return {key: statement[key] for key in ("charge", "paid", "debt")}

    def dollars(rate):
        return format(
            (Decimal(booked["debt"]) / Decimal(rate)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            "f",
        )

    return {
        "kind": "fictional_teaching_example",
        "initial": totals(before),
        "booked": totals(booked),
        "changed": totals(changed),
        "payment": {
            key: payment[key] for key in ("amount", "currency", "base_amount", "exchange_rate")
        },
        "rates": {"booked": "12000", "changed": "15000"},
        "display": {"booked_usd": dollars("12000"), "changed_usd": dollars("15000")},
    }


def render_asset():
    return (
        '"use strict";\nwindow.VEDOMOST_SCENARIO = '
        + json.dumps(build_example(), ensure_ascii=False, indent=2)
        + ";\n"
    )


if __name__ == "__main__":
    target = ROOT / "app" / "static" / "scenario-data.js"
    target.write_text(render_asset(), encoding="utf-8")
