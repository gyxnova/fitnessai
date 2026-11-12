from exercises import safe_exercises
from db import get_connection

def build_session(conn, user_id, area, minutes_available, target_count=5):
    """Build a time-bounded session from goal-matched and general exercises."""
    allowed_areas = {"legs", "chest", "back", "shoulders", "arms", "core"}
    if area not in allowed_areas:
        raise ValueError(f"Unsupported exercise area: {area}")
    if minutes_available < 1:
        raise ValueError("minutes_available must be at least 1")
    if target_count < 1:
        raise ValueError("target_count must be at least 1")

    matched = safe_exercises(conn, user_id)
    general = safe_exercises(conn, user_id, goal="general_exercise")
    if not matched and not general:
        return {
            "exercises": [],
            "message": f"No {area} exercises fit your level and equipment yet.",
        }

    query = """
        SELECT e.exercise_id, e.exercise, e.default_minutes
        FROM exercises e
        JOIN exercise_areas ea ON ea.exercise_id = e.exercise_id
        WHERE e.exercise_id = ANY(%s) AND ea.area = %s
        ORDER BY e.exercise_id
    """
    matched_ids = [exercise_id for exercise_id, _ in matched]
    with conn.cursor() as cur:
        cur.execute(query, (matched_ids, area))
        main = cur.fetchall()

        top_up = []
        if len(main) < target_count:
            main_ids = {exercise_id for exercise_id, _, _ in main}
            general_ids = [
                exercise_id
                for exercise_id, _ in general
                if exercise_id not in main_ids
            ]
            cur.execute(query, (general_ids, area))
            top_up = cur.fetchall()

    candidates = [
        (exercise_id, name, default_minutes, False)
        for exercise_id, name, default_minutes in main
    ] + [
        (exercise_id, name, default_minutes, True)
        for exercise_id, name, default_minutes in top_up
    ]
    if not candidates:
        return {
            "exercises": [],
            "message": f"No {area} exercises fit your level and equipment yet.",
        }

    selected = []
    selected_minimum = 0
    for candidate in candidates:
        exercise_id, name, default_minutes, from_fallback = candidate
        minimum = max(2, round(0.4 * default_minutes))
        if len(selected) >= target_count:
            break
        if selected_minimum + minimum > minutes_available:
            break
        selected.append((exercise_id, name, default_minutes, from_fallback, minimum))
        selected_minimum += minimum

    if not selected:
        first_minimum = max(2, round(0.4 * candidates[0][2]))
        return {
            "exercises": [],
            "message": (
                f"Not enough time for a {area} session; "
                f"try at least {first_minimum} minutes."
            ),
        }

    default_total = sum(default_minutes for _, _, default_minutes, _, _ in selected)
    if default_total <= minutes_available:
        planned_minutes = [
            default_minutes
            for _, _, default_minutes, _, _ in selected
        ]
    else:
        spread = sum(
            default_minutes - minimum
            for _, _, default_minutes, _, minimum in selected
        )
        remaining = minutes_available - selected_minimum
        planned_minutes = [
            minimum
            + (
                (remaining * (default_minutes - minimum)) // spread
                if spread
                else 0
            )
            for _, _, default_minutes, _, minimum in selected
        ]

    planned = [
        {
            "exercise_id": exercise_id,
            "name": name,
            "planned_minutes": minutes,
            "from_fallback": from_fallback,
        }
        for (exercise_id, name, _, from_fallback, _), minutes in zip(
            selected, planned_minutes
        )
    ]

    matched_count = sum(not item["from_fallback"] for item in planned)
    fallback_count = len(planned) - matched_count
    if fallback_count and matched_count:
        message = (
            f"Only {matched_count} {area} exercises match your goal, so "
            f"{fallback_count} general {area} exercises were added."
        )
    elif fallback_count:
        message = (
            f"No {area} exercises match your goal yet, so "
            f"{fallback_count} general {area} exercises were added."
        )
    elif len(selected) < target_count and len(selected) < len(candidates):
        message = (
            f"A {minutes_available}-minute session fits only {len(planned)} "
            f"{area} exercises; try more time for {target_count}."
        )
    elif len(selected) < target_count and len(selected) == len(candidates):
        message = (
            f"Only {len(planned)} {area} exercises fit your level, goal and "
            "equipment so far."
        )
    else:
        message = None

    return {"exercises": planned, "message": message}

if __name__ == "__main__":
    conn = get_connection()
    print(build_session(conn, 1, "legs", 15))
    print(build_session(conn, 2, "chest", 10))
    print(build_session(conn, 3, "back", 20))
    conn.close()