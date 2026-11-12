from collections import Counter

import pytest

from exercises import safe_exercises
from plan_generator import build_full_body_session


# Protects full-body sessions from exceeding their time or safety limits.
@pytest.mark.parametrize("user_id", [1, 2, 3, 4])
@pytest.mark.parametrize("minutes_available", [10, 45, 90])
def test_full_body_session_obeys_invariants(conn, user_id, minutes_available):
    per_area = 1
    result = build_full_body_session(
        conn, user_id, minutes_available, per_area=per_area
    )
    planned = result["exercises"]
    exercise_ids = [item["exercise_id"] for item in planned]
    allowed_ids = {
        exercise_id for exercise_id, _ in safe_exercises(conn, user_id)
    } | {
        exercise_id
        for exercise_id, _ in safe_exercises(
            conn, user_id, goal="general_exercise"
        )
    }

    assert sum(item["planned_minutes"] for item in planned) <= minutes_available
    assert len(exercise_ids) == len(set(exercise_ids))
    assert set(exercise_ids) <= allowed_ids
    assert all(
        count <= per_area
        for count in Counter(item["area"] for item in planned).values()
    )
    if not planned:
        assert result["message"] is not None


# Protects against one exercise tagged with two areas being chosen twice.
@pytest.mark.parametrize("user_id", [1, 2])
def test_full_body_session_does_not_repeat_exercises_across_areas(conn, user_id):
    result = build_full_body_session(conn, user_id, 90)
    exercise_ids = [item["exercise_id"] for item in result["exercises"]]

    assert len(exercise_ids) == len(set(exercise_ids))


# Protects a sufficiently long advanced-user session from omitting any area.
def test_advanced_user_gets_all_six_areas(conn):
    result = build_full_body_session(conn, 4, 90)

    assert len(result["exercises"]) == 6
    assert {item["area"] for item in result["exercises"]} == {
        "legs",
        "chest",
        "back",
        "shoulders",
        "arms",
        "core",
    }
    assert result["message"] is None


# Protects the minimum-time explanation when no exercise fits.
def test_one_minute_session_returns_not_enough_time_message(conn):
    result = build_full_body_session(conn, 4, 1)

    assert result["exercises"] == []
    assert result["message"].startswith(
        "Not enough time for a full body session"
    )


# Protects unknown users from receiving an empty session without explanation.
def test_unknown_user_gets_empty_session_with_message(conn):
    result = build_full_body_session(conn, 999, 60)

    assert result["exercises"] == []
    assert result["message"] is not None


# Protects validation of session duration and per-area target.
@pytest.mark.parametrize(
    "minutes_available, per_area",
    [(0, 1), (60, 0)],
)
def test_invalid_full_body_inputs_raise_value_error(
    conn, minutes_available, per_area
):
    with pytest.raises(ValueError):
        build_full_body_session(conn, 1, minutes_available, per_area)
