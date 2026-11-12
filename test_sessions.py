from datetime import date, datetime

import pytest
from psycopg.errors import ForeignKeyViolation

from exercises import safe_exercises
from plan_generator import build_full_body_session, build_session
from sessions import get_session, save_session


def assert_session_round_trip(conn, user_id, generated_session):
    planned_date = date(2026, 11, 20)
    session_id = save_session(conn, user_id, planned_date, generated_session)
    saved = get_session(conn, session_id)

    assert saved is not None
    assert saved["session_id"] == session_id
    assert saved["user_id"] == user_id
    assert saved["planned_date"] == planned_date
    assert saved["status"] == "planned"
    assert saved["duration"] == sum(
        item["planned_minutes"] for item in generated_session["exercises"]
    )
    assert [item["exercise_id"] for item in saved["exercises"]] == [
        item["exercise_id"] for item in generated_session["exercises"]
    ]
    assert [item["planned_minutes"] for item in saved["exercises"]] == [
        item["planned_minutes"] for item in generated_session["exercises"]
    ]
    assert [item["position"] for item in saved["exercises"]] == list(
        range(1, len(saved["exercises"]) + 1)
    )
    assert all(not item["completed"] for item in saved["exercises"])


# Protects persistence and retrieval of a standard generated session.
def test_build_session_round_trip(conn):
    generated = build_session(conn, 3, "core", 30)

    assert generated["exercises"]
    assert_session_round_trip(conn, 3, generated)


# Protects persistence and retrieval of a full-body generated session.
def test_full_body_session_round_trip(conn):
    generated = build_full_body_session(conn, 4, 90)

    assert generated["exercises"]
    assert_session_round_trip(conn, 4, generated)


# Protects lookup behavior for an ID that does not exist.
def test_get_session_returns_none_for_unknown_id(conn):
    assert get_session(conn, 999999) is None


# Protects against persisting an empty generated session.
def test_save_empty_session_raises_without_inserting(conn):
    before = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions"
    ).fetchone()[0]

    with pytest.raises(ValueError):
        save_session(conn, 3, date(2026, 11, 20), {"exercises": []})

    after = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions"
    ).fetchone()[0]
    assert after == before


# Protects the requirement that planned dates are date-only values.
@pytest.mark.parametrize(
    "planned_date",
    ["2026-11-20", datetime(2026, 11, 20)],
)
def test_save_session_rejects_invalid_planned_date(conn, planned_date):
    generated = build_session(conn, 3, "core", 30)

    with pytest.raises(ValueError):
        save_session(conn, 3, planned_date, generated)


# Protects atomicity when any exercise insert fails.
def test_save_session_rolls_back_on_invalid_exercise_id(conn):
    valid_exercise_id = safe_exercises(conn, 3)[0][0]
    session = {
        "exercises": [
            {"exercise_id": valid_exercise_id, "planned_minutes": 5},
            {"exercise_id": 999999, "planned_minutes": 5},
        ],
        "message": None,
    }
    sessions_before = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s", (3,)
    ).fetchone()[0]
    exercises_before = conn.execute(
        "SELECT COUNT(*) FROM session_exercises"
    ).fetchone()[0]

    with pytest.raises(ForeignKeyViolation):
        save_session(conn, 3, date(2026, 11, 20), session)

    sessions_after = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s", (3,)
    ).fetchone()[0]
    exercises_after = conn.execute(
        "SELECT COUNT(*) FROM session_exercises"
    ).fetchone()[0]
    assert sessions_after == sessions_before
    assert exercises_after == exercises_before
