from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import create_access_token
from app.main import app, get_conn, get_today


@pytest.fixture
def client(conn):
    def override_conn():
        yield conn

    app.dependency_overrides[get_conn] = override_conn
    app.dependency_overrides[get_today] = lambda: date(2026, 11, 21)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def signup_and_login(client, email, password="correct-horse-1", dob="1990-01-01"):
    signup = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "date_of_birth": dob,
            "fitness_level": "beginner",
            "goal": "general_exercise",
            "diet_type": "veg",
        },
    )
    assert signup.status_code == 201
    user_id = signup.json()["user_id"]
    login = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def preview_exercises(client, headers, area="legs", minutes=30):
    response = client.post(
        "/plans/preview",
        json={"area": area, "minutes_available": minutes},
        headers=headers,
    )
    assert response.status_code == 200
    return [
        {
            "exercise_id": item["exercise_id"],
            "planned_minutes": item["planned_minutes"],
        }
        for item in response.json()["exercises"]
    ]


def save_preview(client, headers, planned_date="2026-11-20"):
    exercises = preview_exercises(client, headers)
    response = client.post(
        "/sessions",
        json={"planned_date": planned_date, "exercises": exercises},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["session_id"], exercises


# The health endpoint is public and does not require authentication.
def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# Signup validates uniqueness, age, allowed fields, and extra fields.
def test_signup_validation_and_duplicates(client):
    signup = client.post(
        "/auth/signup",
        json={
            "email": "signup@example.com",
            "password": "correct-horse-1",
            "date_of_birth": "1990-01-01",
            "fitness_level": "beginner",
            "goal": "general_exercise",
            "diet_type": "veg",
        },
    )
    assert signup.status_code == 201
    assert isinstance(signup.json()["user_id"], int)

    duplicate = client.post(
        "/auth/signup",
        json={
            "email": "SIGNUP@EXAMPLE.COM",
            "password": "correct-horse-1",
            "date_of_birth": "1990-01-01",
            "fitness_level": "beginner",
            "goal": "general_exercise",
            "diet_type": "veg",
        },
    )
    assert duplicate.status_code == 409

    underage = client.post(
        "/auth/signup",
        json={
            "email": "underage@example.com",
            "password": "correct-horse-1",
            "date_of_birth": "2009-11-21",
            "fitness_level": "beginner",
            "goal": "general_exercise",
            "diet_type": "veg",
        },
    )
    assert underage.status_code == 422

    extra_field = client.post(
        "/auth/signup",
        json={
            "email": "extra@example.com",
            "password": "correct-horse-1",
            "date_of_birth": "1990-01-01",
            "fitness_level": "beginner",
            "goal": "general_exercise",
            "diet_type": "veg",
            "user_id": 123,
        },
    )
    assert extra_field.status_code == 422

    invalid_level = client.post(
        "/auth/signup",
        json={
            "email": "level@example.com",
            "password": "correct-horse-1",
            "date_of_birth": "1990-01-01",
            "fitness_level": "expert",
            "goal": "general_exercise",
            "diet_type": "veg",
        },
    )
    assert invalid_level.status_code == 422


# Login returns a token and uses the same failure response for both bad credentials.
def test_login_success_and_failures(client):
    email = "login@example.com"
    password = "correct-horse-1"
    signup_and_login(client, email, password)

    success = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert success.status_code == 200
    assert success.json()["access_token"]

    wrong_password = client.post(
        "/auth/login", data={"username": email, "password": "wrong-password"}
    )
    unknown_email = client.post(
        "/auth/login",
        data={"username": "unknown@example.com", "password": password},
    )
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# The profile requires a valid, unexpired token for an existing user.
def test_me_requires_an_existing_authenticated_user(client, conn):
    user_id, headers = signup_and_login(client, "profile@example.com")
    profile = client.get("/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json() == {
        "user_id": user_id,
        "fitness_level": "beginner",
        "goal": "general_exercise",
        "diet_type": "veg",
    }

    assert client.get("/me").status_code == 401
    assert (
        client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code
        == 401
    )
    expired = create_access_token(user_id, expires_minutes=-1)
    assert (
        client.get(
            "/me", headers={"Authorization": f"Bearer {expired}"}
        ).status_code
        == 401
    )

    conn.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    conn.commit()
    assert client.get("/me", headers=headers).status_code == 401


# Plan previews require auth, validate input, and do not persist sessions or versions.
def test_plan_preview_auth_validation_and_read_only(client, conn):
    user_id, headers = signup_and_login(client, "preview@example.com")
    assert (
        client.post(
            "/plans/preview",
            json={"area": "legs", "minutes_available": 30},
        ).status_code
        == 401
    )

    sessions_before = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s", (user_id,)
    ).fetchone()[0]
    versions_before = conn.execute(
        """
        SELECT COUNT(*)
        FROM session_versions sv
        JOIN workout_sessions ws ON ws.session_id = sv.session_id
        WHERE ws.user_id = %s
        """,
        (user_id,),
    ).fetchone()[0]

    legs = client.post(
        "/plans/preview",
        json={"area": "legs", "minutes_available": 30},
        headers=headers,
    )
    assert legs.status_code == 200
    full_body = client.post(
        "/plans/preview",
        json={"area": "full_body", "minutes_available": 30},
        headers=headers,
    )
    assert full_body.status_code == 200
    assert (
        client.post(
            "/plans/preview",
            json={"area": "hands", "minutes_available": 30},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/plans/preview",
            json={"area": "legs", "minutes_available": 0},
            headers=headers,
        ).status_code
        == 422
    )

    sessions_after = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s", (user_id,)
    ).fetchone()[0]
    versions_after = conn.execute(
        """
        SELECT COUNT(*)
        FROM session_versions sv
        JOIN workout_sessions ws ON ws.session_id = sv.session_id
        WHERE ws.user_id = %s
        """,
        (user_id,),
    ).fetchone()[0]
    assert sessions_after == sessions_before
    assert versions_after == versions_before


# A generated session can be saved and read back with its initial version.
def test_save_and_read_session(client):
    _, headers = signup_and_login(client, "roundtrip@example.com")
    exercises = preview_exercises(client, headers)
    assert exercises

    created = client.post(
        "/sessions",
        json={"planned_date": "2026-11-20", "exercises": exercises},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    saved = client.get(f"/sessions/{session_id}", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["planned_date"] == "2026-11-20"
    assert [
        {
            "exercise_id": item["exercise_id"],
            "planned_minutes": item["planned_minutes"],
        }
        for item in saved.json()["exercises"]
    ] == exercises

    versions = client.get(
        f"/sessions/{session_id}/versions", headers=headers
    )
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [1]


# Session existence and ownership failures are indistinguishable and do not mutate data.
def test_session_ownership_hides_other_users_sessions(client, conn):
    user_a, headers_a = signup_and_login(client, "owner@example.com")
    user_b, headers_b = signup_and_login(client, "other@example.com")
    session_id, exercises = save_preview(client, headers_a)
    missing_id = 99999999

    session_count_before = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0]
    version_count_before = conn.execute(
        "SELECT COUNT(*) FROM session_versions WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0]

    for method, path, body in (
        ("get", f"/sessions/{session_id}", None),
        (
            "put",
            f"/sessions/{session_id}",
            {"exercises": exercises},
        ),
        ("get", f"/sessions/{session_id}/versions", None),
        ("post", f"/sessions/{session_id}/revert/1", None),
    ):
        foreign = client.request(
            method.upper(), path, json=body, headers=headers_b
        )
        missing_path = path.replace(str(session_id), str(missing_id), 1)
        missing = client.request(
            method.upper(), missing_path, json=body, headers=headers_b
        )
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()

    assert client.get(f"/sessions/{session_id}", headers=headers_a).status_code == 200
    assert conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0] == session_count_before
    assert conn.execute(
        "SELECT COUNT(*) FROM session_versions WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0] == version_count_before
    assert user_a != user_b


# Updates append a version, and reverting creates another version from the old snapshot.
def test_update_and_revert_session(client):
    _, headers = signup_and_login(client, "revision@example.com")
    session_id, exercises = save_preview(client, headers)

    updated = client.put(
        f"/sessions/{session_id}",
        json={"exercises": exercises},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json() == {"version": 2}

    reverted = client.post(
        f"/sessions/{session_id}/revert/1", headers=headers
    )
    assert reverted.status_code == 200
    assert reverted.json() == {"version": 3}

    versions = client.get(
        f"/sessions/{session_id}/versions", headers=headers
    )
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [1, 2, 3]


# Completed sessions cannot be updated or reverted.
def test_completed_session_is_locked(client, conn):
    _, headers = signup_and_login(client, "completed@example.com")
    session_id, exercises = save_preview(client, headers)
    conn.execute(
        "UPDATE workout_sessions SET status = %s WHERE session_id = %s",
        ("completed", session_id),
    )
    conn.commit()

    update = client.put(
        f"/sessions/{session_id}",
        json={"exercises": exercises},
        headers=headers,
    )
    revert = client.post(
        f"/sessions/{session_id}/revert/1", headers=headers
    )
    assert update.status_code == 409
    assert revert.status_code == 409


# Unsafe exercises are rejected without changing existing sessions or saving new ones.
def test_unsafe_exercise_is_rejected_for_update_and_create(client, conn):
    _, headers = signup_and_login(client, "unsafe@example.com")
    session_id, exercises = save_preview(client, headers)
    unsafe_id = conn.execute(
        "SELECT exercise_id FROM exercises WHERE exercise = %s",
        ("Barbell deadlift",),
    ).fetchone()[0]
    unsafe_exercises = [{"exercise_id": unsafe_id, "planned_minutes": 5}]

    sessions_before = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions"
    ).fetchone()[0]
    items_before = conn.execute(
        "SELECT COUNT(*) FROM session_exercises WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0]
    versions_before = conn.execute(
        "SELECT COUNT(*) FROM session_versions WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0]

    update = client.put(
        f"/sessions/{session_id}",
        json={"exercises": unsafe_exercises},
        headers=headers,
    )
    create = client.post(
        "/sessions",
        json={"planned_date": "2026-11-20", "exercises": unsafe_exercises},
        headers=headers,
    )
    assert update.status_code == 422
    assert create.status_code == 422

    assert conn.execute(
        "SELECT COUNT(*) FROM workout_sessions"
    ).fetchone()[0] == sessions_before
    assert conn.execute(
        "SELECT COUNT(*) FROM session_exercises WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0] == items_before
    assert conn.execute(
        "SELECT COUNT(*) FROM session_versions WHERE session_id = %s",
        (session_id,),
    ).fetchone()[0] == versions_before
    assert client.get(f"/sessions/{session_id}", headers=headers).status_code == 200
    assert exercises


# Session creation rejects extra fields, invalid exercise counts, and non-strict minutes.
def test_save_session_request_validation(client):
    _, headers = signup_and_login(client, "invalid-save@example.com")
    exercises = preview_exercises(client, headers)
    assert exercises
    planned_date = "2026-11-20"

    bodies = [
        {
            "planned_date": planned_date,
            "exercises": exercises,
            "user_id": 123,
        },
        {"planned_date": planned_date, "exercises": []},
        {"planned_date": planned_date, "exercises": [exercises[0]] * 21},
        {
            "planned_date": planned_date,
            "exercises": [
                {"exercise_id": exercises[0]["exercise_id"], "planned_minutes": "5"}
            ],
        },
        {
            "planned_date": planned_date,
            "exercises": [
                {"exercise_id": exercises[0]["exercise_id"], "planned_minutes": 0}
            ],
        },
    ]
    for body in bodies:
        assert (
            client.post("/sessions", json=body, headers=headers).status_code
            == 422
        )


# Repeated exercise IDs are rejected before creating a session.
def test_save_session_rejects_repeated_exercise_ids(client, conn):
    user_id, headers = signup_and_login(client, "repeated@example.com")
    exercises = preview_exercises(client, headers)
    assert exercises
    repeated = [exercises[0], exercises[0]]
    before = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s", (user_id,)
    ).fetchone()[0]

    response = client.post(
        "/sessions",
        json={"planned_date": "2026-11-20", "exercises": repeated},
        headers=headers,
    )

    after = conn.execute(
        "SELECT COUNT(*) FROM workout_sessions WHERE user_id = %s", (user_id,)
    ).fetchone()[0]
    assert response.status_code == 422
    assert after == before


# Unexpected save failures are logged by type only and return a generic error.
def test_session_save_error_does_not_leak_details(client, monkeypatch, caplog):
    _, headers = signup_and_login(client, "error@.com")
    exercises = preview_exercises(client, headers)

    def raise_secret_error(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(main, "save_session", raise_secret_error)
    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.post(
            "/sessions",
            json={"planned_date": "2026-11-20", "exercises": exercises},
            headers=headers,
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "RuntimeError" in caplog.text
    assert "secret internal detail" not in caplog.text
