from exercises import safe_exercises
from db import get_connection


def _area_candidates(conn, matched_ids, general_ids, area, target_count):
    query = """
        SELECT e.exercise_id, e.exercise, e.default_minutes
        FROM exercises e
        JOIN exercise_areas ea ON ea.exercise_id = e.exercise_id
        WHERE e.exercise_id = ANY(%s::int[]) AND ea.area = %s
        ORDER BY e.exercise_id
    """
    with conn.cursor() as cur:
        cur.execute(query, (matched_ids, area))
        main = cur.fetchall()

        top_up = []
        if len(main) < target_count:
            main_ids = {exercise_id for exercise_id, _, _ in main}
            fallback_ids = [
                exercise_id
                for exercise_id in general_ids
                if exercise_id not in main_ids
            ]
            cur.execute(query, (fallback_ids, area))
            top_up = cur.fetchall()

    return [
        (exercise_id, name, default_minutes, False)
        for exercise_id, name, default_minutes in main
    ] + [
        (exercise_id, name, default_minutes, True)
        for exercise_id, name, default_minutes in top_up
    ]


def _select_and_allocate(candidates, minutes_available, target_count):
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
        return selected, []

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
    return selected, planned_minutes


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

    matched_ids = [exercise_id for exercise_id, _ in matched]
    general_ids = [exercise_id for exercise_id, _ in general]
    candidates = _area_candidates(
        conn, matched_ids, general_ids, area, target_count
    )
    if not candidates:
        return {
            "exercises": [],
            "message": f"No {area} exercises fit your level and equipment yet.",
        }

    selected, planned_minutes = _select_and_allocate(
        candidates, minutes_available, target_count
    )
    if not selected:
        first_minimum = max(2, round(0.4 * candidates[0][2]))
        return {
            "exercises": [],
            "message": (
                f"Not enough time for a {area} session; "
                f"try at least {first_minimum} minutes."
            ),
        }

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


def build_full_body_session(conn, user_id, minutes_available, per_area=1):
    """Build a time-bounded session spanning available exercise areas."""
    if minutes_available < 1:
        raise ValueError("minutes_available must be at least 1")
    if per_area < 1:
        raise ValueError("per_area must be at least 1")

    areas = ("legs", "chest", "back", "shoulders", "arms", "core")
    matched = safe_exercises(conn, user_id)
    general = safe_exercises(conn, user_id, goal="general_exercise")
    matched_ids = [exercise_id for exercise_id, _ in matched]
    matched_id_set = set(matched_ids)
    general_ids = [
        exercise_id for exercise_id, _ in general
        if exercise_id not in matched_id_set
    ]

    candidates = []
    skipped_areas = []
    used_ids = set()
    for area in areas:
        area_candidates = _area_candidates(
            conn,
            matched_ids,
            general_ids,
            area,
            per_area + len(used_ids),
        )
        area_candidates = [
            candidate
            for candidate in area_candidates
            if candidate[0] not in used_ids
        ][:per_area]
        if not area_candidates:
            skipped_areas.append(area)
            continue
        used_ids.update(candidate[0] for candidate in area_candidates)
        candidates.extend(
            (exercise_id, name, default_minutes, from_fallback, area)
            for exercise_id, name, default_minutes, from_fallback in area_candidates
        )

    selected, planned_minutes = _select_and_allocate(
        [candidate[:4] for candidate in candidates],
        minutes_available,
        len(candidates),
    )
    if not selected:
        if candidates:
            first_minimum = max(2, round(0.4 * candidates[0][2]))
            message = (
                "Not enough time for a full body session; "
                f"try at least {first_minimum} minutes."
            )
        else:
            message = (
                "No exercises available yet for: "
                f"{', '.join(skipped_areas)}."
            )
        return {"exercises": [], "message": message}

    planned = [
        {
            "exercise_id": exercise_id,
            "name": name,
            "area": area,
            "planned_minutes": minutes,
            "from_fallback": from_fallback,
        }
        for (exercise_id, name, _, from_fallback, _), minutes, area in zip(
            selected,
            planned_minutes,
            [candidate[4] for candidate in candidates],
        )
    ]

    if skipped_areas:
        message = f"No exercises available yet for: {', '.join(skipped_areas)}."
    else:
        included_areas = {item["area"] for item in planned}
        if len(included_areas) < len(areas):
            message = (
                f"A {minutes_available}-minute full body session covers "
                f"{len(included_areas)} of 6 areas; try more time for all six."
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