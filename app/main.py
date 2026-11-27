from collections.abc import Callable, Generator
from datetime import date
import logging
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.auth import (
    EmailTakenError,
    authenticate,
    create_access_token,
    create_user,
    decode_access_token,
)
from app.db import get_connection
from app.plan_generator import build_full_body_session, build_session
from app.sessions import (
    SessionLockedError,
    get_session,
    list_versions,
    revert_session,
    save_session,
    update_session,
)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    date_of_birth: date
    fitness_level: Literal["beginner", "intermediate", "advanced"]
    goal: Literal["lose_weight", "gain_weight", "general_exercise"]
    diet_type: Literal["veg", "non_veg"]


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: Literal["legs", "chest", "back", "shoulders", "arms", "core", "full_body"]
    minutes_available: int = Field(ge=1, le=240)


class ExerciseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: int = Field(gt=0)
    planned_minutes: Annotated[StrictInt, Field(ge=1, le=240)]


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_date: date
    exercises: list[ExerciseItem] = Field(min_length=1, max_length=20)


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercises: list[ExerciseItem] = Field(min_length=1, max_length=20)


app = FastAPI()
logger = logging.getLogger("fitnessai")


def get_conn() -> Generator:
    """Yield a database connection and close it afterwards."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_today() -> date:
    """Return today's date."""
    return date.today()


def get_current_user_id(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/login")),
    conn=Depends(get_conn),
) -> int:
    """Validate a bearer token and confirm its user still exists."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except ValueError:
        raise unauthorized from None

    row = conn.execute(
        "SELECT 1 FROM users WHERE user_id = %s", (user_id,)
    ).fetchone()
    if row is None:
        raise unauthorized
    return user_id


def _require_owned_session(conn, session_id: int, user_id: int) -> dict:
    """Load a session only when it belongs to the authenticated user."""
    session = get_session(conn, session_id)
    if session is None or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _run_session_action(action: Callable):
    """Map session operation errors to safe HTTP responses."""
    try:
        return action()
    except LookupError:
        raise HTTPException(status_code=404, detail="Not found") from None
    except SessionLockedError:
        raise HTTPException(
            status_code=409, detail="Session can no longer be edited"
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    """Return request validation errors without echoing submitted values."""
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request, exc):
    logger.error(
        "Unhandled %s on %s %s",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error"}
    )


@app.get("/health")
def health() -> dict:
    """Report that the API is running."""
    return {"status": "ok"}


@app.post("/auth/signup", status_code=201)
def signup(
    request: SignupRequest,
    conn=Depends(get_conn),
    today: date = Depends(get_today),
) -> dict:
    """Create an account."""
    try:
        user_id = create_user(
            conn,
            request.email,
            request.password,
            request.date_of_birth,
            request.fitness_level,
            request.goal,
            request.diet_type,
            today=today,
        )
    except EmailTakenError:
        raise HTTPException(status_code=409, detail="Email already registered") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"user_id": user_id}


@app.post("/auth/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    conn=Depends(get_conn),
) -> dict:
    """Authenticate and return a bearer token."""
    user_id = authenticate(conn, form.username, form.password)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user_id),
        "token_type": "bearer",
    }


@app.get("/me")
def me(
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Return the authenticated user's profile."""
    row = conn.execute(
        """
        SELECT fitness_level, goal, diet_type
        FROM users
        WHERE user_id = %s
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "user_id": user_id,
        "fitness_level": row[0],
        "goal": row[1],
        "diet_type": row[2],
    }


@app.post("/plans/preview")
def preview_plan(
    request: PlanRequest,
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Build a session preview without saving it."""
    try:
        if request.area == "full_body":
            return build_full_body_session(
                conn, user_id, request.minutes_available
            )
        return build_session(
            conn, user_id, request.area, request.minutes_available
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@app.post("/sessions", status_code=201)
def create_saved_session(
    request: SaveRequest,
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Save a planned session."""
    session = {
        "exercises": [
            item.model_dump() for item in request.exercises
        ],
        "message": None,
    }
    try:
        session_id = save_session(
            conn, user_id, request.planned_date, session
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"session_id": session_id}


@app.get("/sessions/{session_id}")
def read_session(
    session_id: int,
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
):
    """Return a session owned by the authenticated user."""
    return _require_owned_session(conn, session_id, user_id)


@app.put("/sessions/{session_id}")
def edit_session(
    session_id: int,
    request: UpdateRequest,
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Replace a session's exercises."""
    _require_owned_session(conn, session_id, user_id)
    exercises = [item.model_dump() for item in request.exercises]
    version = _run_session_action(
        lambda: update_session(conn, session_id, exercises)
    )
    return {"version": version}


@app.get("/sessions/{session_id}/versions")
def read_session_versions(
    session_id: int,
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
):
    """List versions of a session owned by the authenticated user."""
    _require_owned_session(conn, session_id, user_id)
    return _run_session_action(lambda: list_versions(conn, session_id))


@app.post("/sessions/{session_id}/revert/{version}")
def restore_session_version(
    session_id: int,
    version: int,
    conn=Depends(get_conn),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Restore a prior session version."""
    _require_owned_session(conn, session_id, user_id)
    new_version = _run_session_action(
        lambda: revert_session(conn, session_id, version)
    )
    return {"version": new_version}
