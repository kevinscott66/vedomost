from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from cloud.domain import MAX_ID, DomainError, handle, seed


def test_seed_and_debtors_use_only_current_month():
    state = seed(date(2026, 10, 28))
    status, report, changed, new_state = handle(state, "GET", "/debtors", {"month": "2026-10"})
    assert (status, changed) == (200, False)
    assert report["total_debt"] == "1350000.00"
    assert [s["id"] for s in report["debtors"]] == [2, 4, 1]
    assert new_state is state
    assert state["next_payment"] == 4


def test_mixed_currency_payment_freezes_exact_conversion_and_replays_without_quote():
    state = seed(date(2026, 10, 28))
    quote = {
        "status": "fresh",
        "source": "CBU",
        "rate_date": "2026-10-27",
        "booking_rates": {"USD": "1.005"},
    }
    body = {"student_id": 4, "amount": "12.34", "currency": "USD", "date": "2026-10-28"}
    status, booked, changed, new_state = handle(
        state, "POST", "/payments", body=body, idempotency_key="retry-key-123456", quote=quote
    )
    assert (status, changed) == (201, True)
    assert booked["base_amount"] == "12.40"
    assert booked["exchange_rate"] == "1.005"
    status, replay, changed, replay_state = handle(
        new_state, "POST", "/payments", body=body, idempotency_key="retry-key-123456"
    )
    assert status == 201 and changed is False and replay == booked


def test_idempotency_normalizes_currency_default_and_blocks_payload_reuse():
    state = seed(date(2026, 10, 28))
    body = {"student_id": 4, "amount": "1.00", "date": "2026-10-28"}
    _, payment, _, changed = handle(
        state, "POST", "/payments", body=body, idempotency_key="same-key-0000000"
    )
    _, replay, did_change, replay_state = handle(
        changed,
        "POST",
        "/payments",
        body={**body, "currency": "UZS"},
        idempotency_key="same-key-0000000",
    )
    assert replay == payment and not did_change
    assert replay_state is changed and replay_state["next_payment"] == 5
    with pytest.raises(DomainError) as exc:
        handle(
            changed,
            "POST",
            "/payments",
            body={**body, "amount": "2.00"},
            idempotency_key="same-key-0000000",
        )
    assert exc.value.status == 409


def test_enrollment_boundary_and_student_delete_constraints():
    state = seed(date(2026, 10, 28))
    with pytest.raises(DomainError) as exc:
        handle(
            state, "POST", "/payments", body={"student_id": 1, "amount": "1", "date": "2026-09-30"}
        )
    assert exc.value.status == 422
    with pytest.raises(DomainError) as exc:
        handle(state, "DELETE", "/students/1")
    assert exc.value.status == 409
    with pytest.raises(DomainError) as exc:
        handle(
            state,
            "PUT",
            "/students/1",
            body={
                "name": "A",
                "phone": "123",
                "group": "G",
                "monthly_fee": "4",
                "start_month": "2026-11",
            },
        )
    assert exc.value.status == 409


def test_invalid_requests_do_not_mutate_input_state():
    state = seed(date(2026, 10, 28))
    original = deepcopy(state)
    with pytest.raises(DomainError):
        handle(
            state,
            "POST",
            "/students",
            body={"name": "X", "phone": "123", "group": "G", "monthly_fee": "1", "unexpected": 1},
        )
    with pytest.raises(DomainError):
        handle(
            state,
            "POST",
            "/payments",
            body={"student_id": 999, "amount": "1", "date": "2026-10-28"},
        )
    assert state == original


def test_create_student_returns_persistable_updated_state():
    state = seed(date(2026, 10, 28))
    status, student, changed, updated = handle(
        state,
        "POST",
        "/students",
        body={"name": "  Test Student  ", "phone": "123", "group": "G", "monthly_fee": "1"},
    )
    assert status == 201 and changed
    assert student["name"] == "Test Student"
    assert len(updated["students"]) == len(state["students"]) + 1
    assert updated["students"][-1] == student
    assert len(state["students"]) == 4


def test_payment_sum_limit_and_collection_limits():
    state = seed(date(2026, 10, 28))
    state["payments"] = [p for p in state["payments"] if p["student_id"] != 4]
    state["payments"].append(
        {
            "id": 4,
            "student_id": 4,
            "amount": "1.00",
            "base_amount": str(Decimal(MAX_ID - 50) / 100),
            "currency": "UZS",
            "exchange_rate": "1",
            "rate_date": None,
            "rate_source": None,
            "date": "2026-10-01",
        }
    )
    with pytest.raises(DomainError) as exc:
        handle(
            state, "POST", "/payments", body={"student_id": 4, "amount": "1", "date": "2026-10-28"}
        )
    assert exc.value.status == 422
    full = seed(date(2026, 10, 28))
    full["students"] *= 25
    with pytest.raises(DomainError) as exc:
        handle(
            full,
            "POST",
            "/students",
            body={"name": "X", "phone": "123", "group": "G", "monthly_fee": "1"},
        )
    assert exc.value.status == 422
