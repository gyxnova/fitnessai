from exercises import safe_exercises
from db import get_connection

def build_session(conn, user_id, area, minutes_available, min_minutes_per_exercise=5):
    """Build a time-bounded session from exercises safe for the user."""
    allowed_areas = {"legs", "chest", "back", "shoulders", "arms", "core"}
    if area not in allowed_areas:
        raise ValueError(f"Unsupported exercise area: {area}")
    if minutes_available < 1:
        raise ValueError("minutes_available must be at least 1")

    safe = safe_exercises(conn, user_id)
    exercise_ids = [exercise_id for exercise_id, _ in safe]

    query = """
        SELECT e.exercise_id, e.exercise, e.default_minutes
        FROM exercises e
        JOIN exercise_areas ea ON ea.exercise_id = e.exercise_id
        WHERE ea.area = %s AND e.exercise_id = ANY(%s)
        ORDER BY e.exercise_id
    """
    with conn.cursor() as cur:
        cur.execute(query, (area, exercise_ids))
        exercises = cur.fetchall()

    if not exercises:
        return {
            "exercises": [],
            "message": f"No {area} exercises fit your level, goal and equipment yet.",
        }

    total_minutes = sum(default_minutes for _, _, default_minutes in exercises)
    if total_minutes <= minutes_available:
        planned = [
            {
                "exercise_id": exercise_id,
                "name": name,
                "planned_minutes": default_minutes,
            }
            for exercise_id, name, default_minutes in exercises
        ]
    else:
        scale = minutes_available / total_minutes
        planned = [
            {
                "exercise_id": exercise_id,
                "name": name,
                "planned_minutes": max(
                    min_minutes_per_exercise, round(default_minutes * scale)
                ),
            }
            for exercise_id, name, default_minutes in exercises
        ]

        while planned and sum(item["planned_minutes"] for item in planned) > minutes_available:
            planned.pop()

        if not planned:
            return {
                "exercises": [],
                "message": (
                    f"Not enough time for a {area} session; "
                    f"try at least {min_minutes_per_exercise} minutes."
                ),
            }

    return {"exercises": planned, "message": None}

if __name__ == "__main__":
    conn = get_connection()
    print(build_session(conn, 1, "legs", 15))
    print(build_session(conn, 2, "chest", 10))
    print(build_session(conn, 3, "back", 20))
    conn.close()