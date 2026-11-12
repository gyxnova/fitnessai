import pytest

from exercises import safe_exercises
from plan_generator import build_session


# Protects session safety, time, ordering, and messaging invariants across supported inputs.
@pytest.mark.parametrize("user_id", [1, 2, 3, 4])
@pytest.mark.parametrize(
    "area", ["legs", "chest", "back", "shoulders", "arms", "core"]
)
@pytest.mark.parametrize("minutes_available", [10, 45, 90])
def test_build_session_invariants(conn, user_id, area, minutes_available):
    result = build_session(conn, user_id, area, minutes_available)
    planned = result["exercises"]
    exercise_ids = [item["exercise_id"] for item in planned]

    assert sum(item["planned_minutes"] for item in planned) <= minutes_available
    for item in planned:
        row = conn.execute(
            "SELECT default_minutes FROM exercises WHERE exercise_id = %s",
            (item["exercise_id"],),
        ).fetchone()
        assert row is not None
        default_minutes = row[0]
        minimum = max(2, round(0.4 * default_minutes))
        assert minimum <= item["planned_minutes"] <= default_minutes

    assert len(planned) <= 5
    assert len(exercise_ids) == len(set(exercise_ids))

    allowed_ids = {
        exercise_id for exercise_id, _ in safe_exercises(conn, user_id)
    } | {
        exercise_id
        for exercise_id, _ in safe_exercises(
            conn, user_id, goal="general_exercise"
        )
    }
    assert set(exercise_ids) <= allowed_ids
    fallback_flags = [item["from_fallback"] for item in planned]
    assert fallback_flags == sorted(fallback_flags)

    if not planned:
        assert result["message"] is not None
    if len(planned) == 5 and not any(fallback_flags):
        assert result["message"] is None


# Protects goal-matched exercises from being displaced by general fallback exercises.
def test_fallback_is_added_after_goal_matches(conn):
    result = build_session(conn, 1, "arms", 60)
    planned = result["exercises"]

    assert len(planned) == 5
    assert [item["from_fallback"] for item in planned] == [
        False,
        False,
        False,
        True,
        True,
    ]
    assert "match your goal" in result["message"]


# Protects sessions from using fallback exercises when goal-matched options suffice.
def test_no_fallback_needed(conn):
    result = build_session(conn, 3, "core", 60)

    assert all(not item["from_fallback"] for item in result["exercises"])


# Protects the user-facing explanation when a short session cannot reach its target.
def test_short_session_reports_time_limit(conn):
    result = build_session(conn, 1, "legs", 10)

    assert len(result["exercises"]) < 5
    assert "10-minute" in result["message"]


# Protects empty sessions when the available time is below every exercise minimum.
def test_not_enough_time_returns_empty_session(conn):
    result = build_session(conn, 4, "legs", 1)

    assert result["exercises"] == []
    assert result["message"].startswith("Not enough time")


# Protects unknown users from receiving exercises that cannot be safety-checked.
def test_unknown_user_returns_no_exercises(conn):
    result = build_session(conn, 999, "legs", 30)

    assert result["exercises"] == []
    assert "No legs exercises fit" in result["message"]


# Protects input validation for invalid areas, durations, and target counts.
@pytest.mark.parametrize(
    "area, minutes_available, target_count",
    [
        ("hands", 30, 5),
        ("legs", 0, 5),
        ("legs", 30, 0),
    ],
)
def test_invalid_inputs_raise_value_error(
    conn, area, minutes_available, target_count
):
    with pytest.raises(ValueError):
        build_session(conn, 1, area, minutes_available, target_count)
