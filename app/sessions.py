from datetime import date, datetime

from psycopg.types.json import Jsonb

from app.exercises import safe_exercises


class SessionLockedError(Exception):
    """Raised when a session is not editable."""


def _check_safe(conn, user_id, exercise_ids):
    safe_ids = {
        exercise_id
        for exercise_id, _ in safe_exercises(conn, user_id)
    }
    safe_ids.update(
        exercise_id
        for exercise_id, _ in safe_exercises(
            conn, user_id, goal="general_exercise"
        )
    )
    unsafe_ids = [
        exercise_id
        for exercise_id in exercise_ids
        if exercise_id not in safe_ids
    ]
    if unsafe_ids:
        raise ValueError(f"Unsafe exercise IDs: {unsafe_ids}")


def _validate_items(exercises):
    """Validate exercise presence, uniqueness, and planned minutes."""
    if not exercises:
        raise ValueError("A session must contain at least one exercise.")

    exercise_ids = [item["exercise_id"] for item in exercises]
    if len(exercise_ids) != len(set(exercise_ids)):
        raise ValueError("Exercise IDs must not be repeated.")
    if any(
        type(item["planned_minutes"]) is not int
        or item["planned_minutes"] <= 0
        for item in exercises
    ):
        raise ValueError("planned_minutes must be a positive integer.")


def save_session(conn, user_id, planned_date, session):
    """Save a non-empty generated session and return its ID."""
    exercises = session["exercises"]
    if not exercises:
        raise ValueError("Cannot save an empty session.")
    if not isinstance(planned_date, date) or isinstance(planned_date, datetime):
        raise ValueError("planned_date must be a datetime.date.")

    _validate_items(exercises)
    _check_safe(
        conn, user_id, [item["exercise_id"] for item in exercises]
    )

    duration = sum(item["planned_minutes"] for item in exercises)
    exercise_rows = [
        (
            item["exercise_id"],
            position,
            item["planned_minutes"],
            False,
        )
        for position, item in enumerate(exercises, start=1)
    ]

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workout_sessions (user_id, planned_date, status, duration)
                VALUES (%s, %s, %s, %s)
                RETURNING session_id
                """,
                (user_id, planned_date, "planned", duration),
            )
            session_id = cur.fetchone()[0]
            cur.executemany(
                """
                INSERT INTO session_exercises
                    (session_id, exercise_id, position, planned_minutes, completed)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [(session_id, *row) for row in exercise_rows],
            )
            snapshot = [
                {
                    "exercise_id": exercise_id,
                    "position": position,
                    "planned_minutes": planned_minutes,
                }
                for exercise_id, position, planned_minutes, _ in exercise_rows
            ]
            cur.execute(
                """
                INSERT INTO session_versions (session_id, version, exercises)
                VALUES (%s, %s, %s)
                """,
                (session_id, 1, Jsonb(snapshot)),
            )
        conn.commit()
    except Exception as error:
        try:
            conn.rollback()
        except Exception as rollback_error:
            raise error from rollback_error
        raise

    return int(session_id)


def _apply_session_update(
    conn, session_id, new_exercises=None, version=None, restore_version=False
):
    """Apply and record a session revision in one transaction."""
    try:
        with conn.cursor() as cur:
            if restore_version:
                cur.execute(
                    """
                    SELECT exercises
                    FROM session_versions
                    WHERE session_id = %s AND version = %s
                    """,
                    (session_id, version),
                )
                snapshot_row = cur.fetchone()
                if snapshot_row is None:
                    raise LookupError(
                        f"Session version {version} does not exist."
                    )
                new_exercises = [
                    {
                        "exercise_id": item["exercise_id"],
                        "planned_minutes": item["planned_minutes"],
                    }
                    for item in snapshot_row[0]
                ]

            cur.execute(
                """
                SELECT user_id, status
                FROM workout_sessions
                WHERE session_id = %s
                FOR UPDATE
                """,
                (session_id,),
            )
            session_row = cur.fetchone()
            if session_row is None:
                raise LookupError(f"Session {session_id} does not exist.")
            user_id, status = session_row
            if status != "planned":
                raise SessionLockedError(
                    f"Session {session_id} is not editable."
                )

            _validate_items(new_exercises)
            exercise_ids = [item["exercise_id"] for item in new_exercises]

            _check_safe(conn, user_id, exercise_ids)

            exercise_rows = [
                (
                    session_id,
                    item["exercise_id"],
                    position,
                    item["planned_minutes"],
                    False,
                )
                for position, item in enumerate(new_exercises, start=1)
            ]
            duration = sum(item["planned_minutes"] for item in new_exercises)

            cur.execute(
                "DELETE FROM session_exercises WHERE session_id = %s",
                (session_id,),
            )
            cur.executemany(
                """
                INSERT INTO session_exercises
                    (session_id, exercise_id, position, planned_minutes, completed)
                VALUES (%s, %s, %s, %s, %s)
                """,
                exercise_rows,
            )
            cur.execute(
                "UPDATE workout_sessions SET duration = %s WHERE session_id = %s",
                (duration, session_id),
            )
            cur.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM session_versions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            new_version = cur.fetchone()[0]
            snapshot = [
                {
                    "exercise_id": item["exercise_id"],
                    "position": position,
                    "planned_minutes": item["planned_minutes"],
                }
                for position, item in enumerate(new_exercises, start=1)
            ]
            cur.execute(
                """
                INSERT INTO session_versions (session_id, version, exercises)
                VALUES (%s, %s, %s)
                """,
                (session_id, new_version, Jsonb(snapshot)),
            )
        conn.commit()
        return int(new_version)
    except Exception as error:
        try:
            conn.rollback()
        except Exception as rollback_error:
            raise error from rollback_error
        raise


def update_session(conn, session_id, new_exercises):
    """Replace a planned session and return its new version."""
    return _apply_session_update(conn, session_id, new_exercises=new_exercises)


def revert_session(conn, session_id, version):
    """Restore a prior snapshot as a new session version."""
    return _apply_session_update(
        conn, session_id, version=version, restore_version=True
    )


def list_versions(conn, session_id):
    """Return a session's saved versions in order."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT version, saved_at, exercises
            FROM session_versions
            WHERE session_id = %s
            ORDER BY version ASC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
    return [
        {"version": row[0], "saved_at": row[1], "exercises": row[2]}
        for row in rows
    ]


def get_session(conn, session_id):
    """Return a saved session with its exercises, or None."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ws.session_id, ws.user_id, ws.planned_date, ws.status, ws.duration,
                   se.exercise_id, e.exercise, se.position, se.planned_minutes,
                   se.completed
            FROM workout_sessions ws
            LEFT JOIN session_exercises se ON se.session_id = ws.session_id
            LEFT JOIN exercises e ON e.exercise_id = se.exercise_id
            WHERE ws.session_id = %s
            ORDER BY se.position
            """,
            (session_id,),
        )
        rows = cur.fetchall()

    if not rows:
        return None

    first = rows[0]
    return {
        "session_id": first[0],
        "user_id": first[1],
        "planned_date": first[2],
        "status": first[3],
        "duration": first[4],
        "exercises": [
            {
                "exercise_id": row[5],
                "name": row[6],
                "position": row[7],
                "planned_minutes": row[8],
                "completed": row[9],
            }
            for row in rows
            if row[5] is not None
        ],
    }
