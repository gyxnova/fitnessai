from datetime import date, datetime, timedelta, timezone

import jwt
import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from psycopg.errors import UniqueViolation

from app.config import JWT_SECRET


_password_hasher = PasswordHasher()
_DUMMY_PASSWORD_HASH = _password_hasher.hash("dummy-password-for-unknown-users")


class EmailTakenError(Exception):
    """Raised when an account already uses the email address."""


def hash_password(password: str) -> str:
    """Hash a password with Argon2."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against an Argon2 hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_user(
    conn: psycopg.Connection,
    email: str,
    password: str,
    date_of_birth: date,
    fitness_level: str,
    goal: str,
    diet_type: str,
    today: date,
) -> int:
    """Create a user and credentials in one transaction."""
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Email must contain '@'")
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters long")

    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    if age < 18:
        raise ValueError("User must be at least 18 years old")

    password_hash = hash_password(password)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (date_of_birth, fitness_level, goal, diet_type)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id
                """,
                (date_of_birth, fitness_level, goal, diet_type),
            )
            user_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO user_credentials (user_id, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (user_id, email, password_hash),
            )
        conn.commit()
    except UniqueViolation as exc:
        conn.rollback()
        raise EmailTakenError("An account already uses this email") from exc
    except Exception:
        conn.rollback()
        raise

    return user_id


def authenticate(conn: psycopg.Connection, email: str, password: str) -> int | None:
    """Return the matching user ID when credentials are valid."""
    email = email.strip().lower()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT user_id, password_hash FROM user_credentials WHERE email = %s",
            (email,),
        )
        row = cursor.fetchone()

    if row is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    user_id, password_hash = row
    if verify_password(password, password_hash):
        return user_id
    return None


def create_access_token(user_id: int, expires_minutes: int = 30) -> str:
    """Create a signed JWT access token."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        JWT_SECRET,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> int:
    """Validate a JWT access token and return its user ID."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp"]},
        )
        subject = payload["sub"]
        if not isinstance(subject, str):
            raise ValueError("Invalid token subject")
        return int(subject)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid access token") from exc
