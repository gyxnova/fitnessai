from copy import deepcopy
from datetime import date

import pytest

from app import sessions
from app.plan_generator import build_session
from app.sessions import (
    SessionLockedError,
    get_session,
    list_versions,
    revert_session,
    save_session,
    update_session,
)


def _build_and_save(conn, user_id, area="legs"):
    generated = build_session(conn, user_id, area, 60)
    assert generated["exercises"]
    session_id = save_session(
        conn, user_id, date(2026, 11, 20), generated
    )
    return session_id, generated


def _with_minutes(exercises, increment=1):
    return [
        {
            "exercise_id": item["exercise_id"],
            "planned_minutes": item["planned_minutes"] + increment,
        }
        for item in exercises
    ]


def _expected_snapshot(exercises):
    return [
        {
            "exercise_id": item["exercise_id"],
            "position": position,
            "planned_minutes": item["planned_minutes"],
        }
        for position, item in enumerate(exercises, start=1)
    ]


def _live_rows(conn, session_id):
    return conn.execute(
        """
        SELECT exercise_id, position, planned_minutes, completed
        FROM session_exercises
        WHERE session_id = %s
        ORDER BY position
        """,
        (session_id,),
    ).fetchall()


# Protects that the initial version snapshots the saved exercise order and minutes.
def test_save_session_writes_matching_version_one_snapshot(conn):
    session_id, generated = _build_and_save(conn, 4)

    versions = list_versions(conn, session_id)
    assert [version["version"] for version in versions] == [1]
    assert versions[0]["exercises"] == _expected_snapshot(
        generated["exercises"]
    )


# Protects that updates append a version and keep live duration in sync.
def test_update_session_appends_version_and_updates_live_session(conn):
    session_id, generated = _build_and_save(conn, 4)
    updated = build_session(conn, 4, "chest", 60)["exercises"]

    assert update_session(conn, session_id, updated) == 2
    assert [version["version"] for version in list_versions(conn, session_id)] == [
        1,
        2,
    ]
    saved = get_session(conn, session_id)
    assert saved is not None
    assert [
        (item["exercise_id"], item["planned_minutes"], item["position"])
        for item in saved["exercises"]
    ] == [
        (item["exercise_id"], item["planned_minutes"], position)
        for position, item in enumerate(updated, start=1)
    ]
    assert saved["duration"] == sum(
        item["planned_minutes"] for item in updated
    )


# Protects that reverting creates a new version while restoring prior live data.
def test_revert_appends_version_three_and_restores_version_one(conn):
    session_id, generated = _build_and_save(conn, 1)
    initial_snapshot = list_versions(conn, session_id)[0]["exercises"]
    update_session(conn, session_id, _with_minutes(generated["exercises"]))

    assert revert_session(conn, session_id, 1) == 3

    versions = list_versions(conn, session_id)
    assert versions[2]["version"] == 3
    assert versions[2]["exercises"] == initial_snapshot
    saved = get_session(conn, session_id)
    assert saved is not None
    assert _live_rows(conn, session_id) == [
        (
            item["exercise_id"],
            item["position"],
            item["planned_minutes"],
            False,
        )
        for item in initial_snapshot
    ]
    assert saved["duration"] == sum(
        item["planned_minutes"] for item in initial_snapshot
    )


# Protects that a revert is re-checked for safety and rejected whole.
def test_revert_rejected_when_old_version_became_unsafe(conn):
    session_id, _ = _build_and_save(conn, 2, "arms")
    initial_snapshot = list_versions(conn, session_id)[0]["exercises"]
    assert any(
        "dumbbells"
        in {
            equipment
            for (equipment,) in conn.execute(
                "SELECT equipment FROM exercise_equipment WHERE exercise_id = %s",
                (item["exercise_id"],),
            ).fetchall()
        }
        for item in initial_snapshot
    )

    update_session(conn, session_id, build_session(conn, 2, "chest", 60)["exercises"])
    conn.execute(
        "DELETE FROM user_equipments WHERE user_id = %s",
        (2,),
    )
    conn.commit()
    before_rows = _live_rows(conn, session_id)
    before_version_count = len(list_versions(conn, session_id))

    with pytest.raises(ValueError):
        revert_session(conn, session_id, 1)

    assert _live_rows(conn, session_id) == before_rows
    assert len(list_versions(conn, session_id)) == before_version_count


# Protects contiguous version history and immutability of the original snapshot.
def test_mixed_updates_and_reverts_keep_contiguous_versions(conn):
    session_id, generated = _build_and_save(conn, 2)
    initial_snapshot = deepcopy(
        list_versions(conn, session_id)[0]["exercises"]
    )

    update_session(conn, session_id, _with_minutes(generated["exercises"], 1))
    revert_session(conn, session_id, 1)
    update_session(conn, session_id, _with_minutes(generated["exercises"], 2))
    revert_session(conn, session_id, 2)

    versions = list_versions(conn, session_id)
    assert [version["version"] for version in versions] == [1, 2, 3, 4, 5]
    assert versions[0]["exercises"] == initial_snapshot


# Protects that completed and missed sessions reject edits without changing data.
@pytest.mark.parametrize("status", ["completed", "missed"])
def test_locked_status_rejects_update_and_revert_without_changes(conn, status):
    session_id, generated = _build_and_save(conn, 1)
    conn.execute(
        "UPDATE workout_sessions SET status = %s WHERE session_id = %s",
        (status, session_id),
    )
    conn.commit()
    before_rows = _live_rows(conn, session_id)
    before_version_count = len(list_versions(conn, session_id))

    with pytest.raises(SessionLockedError):
        update_session(conn, session_id, _with_minutes(generated["exercises"]))
    with pytest.raises(SessionLockedError):
        revert_session(conn, session_id, 1)

    assert _live_rows(conn, session_id) == before_rows
    assert len(list_versions(conn, session_id)) == before_version_count


# Protects that unsafe exercises cannot enter a session through update or save.
def test_unsafe_exercise_is_rejected_by_update_and_save(conn):
    session_id, generated = _build_and_save(conn, 3)
    barbell_id = conn.execute(
        "SELECT exercise_id FROM exercises WHERE exercise = %s",
        ("Barbell deadlift",),
    ).fetchone()[0]
    before_session = get_session(conn, session_id)
    before_versions = list_versions(conn, session_id)
    unsafe_update = _with_minutes(generated["exercises"], 0)
    unsafe_update[0]["exercise_id"] = barbell_id

    with pytest.raises(ValueError):
        update_session(conn, session_id, unsafe_update)

    assert get_session(conn, session_id) == before_session
    assert list_versions(conn, session_id) == before_versions

    before_count = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s",
        (3,),
    ).fetchone()[0]
    with pytest.raises(ValueError):
        save_session(
            conn,
            3,
            date(2026, 11, 20),
            {
                "exercises": [
                    {"exercise_id": barbell_id, "planned_minutes": 5}
                ],
                "message": None,
            },
        )
    after_count = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s",
        (3,),
    ).fetchone()[0]
    assert after_count == before_count


# Protects transaction rollback when version snapshot serialization fails.
def test_update_rolls_back_when_snapshot_serialization_fails(conn, monkeypatch):
    session_id, generated = _build_and_save(conn, 4)
    before_rows = _live_rows(conn, session_id)
    before_versions = list_versions(conn, session_id)

    def fail_jsonb(value):
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(sessions, "Jsonb", fail_jsonb)
    with pytest.raises(RuntimeError, match="serialization failed"):
        update_session(conn, session_id, _with_minutes(generated["exercises"]))

    assert _live_rows(conn, session_id) == before_rows
    assert list_versions(conn, session_id) == before_versions
    assert conn.execute("SELECT 1").fetchone()[0] == 1


# Protects lookup errors for missing sessions and versions.
def test_unknown_session_and_version_lookups(conn):
    session_id, generated = _build_and_save(conn, 1)

    with pytest.raises(LookupError):
        update_session(conn, 999999, _with_minutes(generated["exercises"]))
    with pytest.raises(LookupError):
        revert_session(conn, session_id, 999999)

    assert list_versions(conn, 999999) == []


# Protects that an empty update cannot erase a session.
def test_update_rejects_empty_exercise_list(conn):
    session_id, _ = _build_and_save(conn, 1)

    with pytest.raises(ValueError):
        update_session(conn, session_id, [])


# Protects that an update cannot repeat an exercise ID.
def test_update_rejects_repeated_exercise_ids(conn):
    session_id, generated = _build_and_save(conn, 1)
    exercise_id = generated["exercises"][0]["exercise_id"]

    with pytest.raises(ValueError):
        update_session(
            conn,
            session_id,
            [
                {"exercise_id": exercise_id, "planned_minutes": 5},
                {"exercise_id": exercise_id, "planned_minutes": 5},
            ],
        )


# Protects that planned minutes must be a positive integer.
@pytest.mark.parametrize("planned_minutes", [0, True, "5"])
def test_update_rejects_invalid_planned_minutes(conn, planned_minutes):
    session_id, generated = _build_and_save(conn, 1)
    updated = _with_minutes(generated["exercises"])
    updated[0]["planned_minutes"] = planned_minutes

    with pytest.raises(ValueError):
        update_session(conn, session_id, updated)
