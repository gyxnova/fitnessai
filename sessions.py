from datetime import date, datetime


def save_session(conn, user_id, planned_date, session):
    """Save a non-empty generated session and return its ID."""
    exercises = session["exercises"]
    if not exercises:
        raise ValueError("Cannot save an empty session.")
    if not isinstance(planned_date, date) or isinstance(planned_date, datetime):
        raise ValueError("planned_date must be a datetime.date.")

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
        conn.commit()
    except Exception as error:
        try:
            conn.rollback()
        except Exception as rollback_error:
            raise error from rollback_error
        raise

    return int(session_id)


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
