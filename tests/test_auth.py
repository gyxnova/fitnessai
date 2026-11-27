from datetime import date, datetime, timezone

import jwt
import psycopg
import pytest

from app.auth import (
    EmailTakenError,
    authenticate,
    create_access_token,
    create_user,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.config import JWT_SECRET


def make_user(
    conn,
    email="a@example.com",
    password="correct-horse-1",
    dob=date(1990, 1, 1),
):
    return create_user(
        conn,
        email,
        password,
        dob,
        fitness_level="beginner",
        goal="general_exercise",
        diet_type="veg",
        today=date(2026, 11, 21),
    )


# Passwords are hashed, and mismatches or malformed hashes do not verify.
def test_password_hashing_and_verification():
    password = "correct-horse-1"
    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert not verify_password(password, "garbage")


# User and credential records use a normalized email and a password hash.
def test_create_user_stores_normalized_email_and_password_hash(conn):
    password = "correct-horse-1"
    user_id = make_user(conn, email="  A@Example.COM  ", password=password)

    user_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = %s", (user_id,)
    ).fetchone()[0]
    credential = conn.execute(
        "SELECT email, password_hash FROM user_credentials WHERE user_id = %s",
        (user_id,),
    ).fetchone()

    assert user_count == 1
    assert credential[0] == "a@example.com"
    assert credential[1] != password


# The 18th birthday is inclusive; an underage signup leaves no user row.
def test_age_boundary(conn):
    make_user(conn, email="turns18@example.com", dob=date(2008, 11, 21))
    before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    with pytest.raises(ValueError):
        make_user(conn, email="underage@example.com", dob=date(2008, 11, 22))

    after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert after == before


# Signup enforces password length and requires an email address separator.
def test_signup_input_validation(conn):
    with pytest.raises(ValueError):
        make_user(conn, email="short@example.com", password="123456789")

    make_user(conn, email="minimum@example.com", password="1234567890")

    with pytest.raises(ValueError):
        make_user(conn, email="long@example.com", password="p" * 129)

    with pytest.raises(ValueError):
        make_user(conn, email="invalid-email")


# A duplicate normalized email rolls back the second user insert.
def test_duplicate_email_does_not_leave_orphan_user(conn):
    make_user(conn, email="a@example.com")
    before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    with pytest.raises(EmailTakenError):
        make_user(conn, email="A@EXAMPLE.COM")

    after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert after == before


# A failed database constraint rolls back both inserts and leaves the connection usable.
def test_create_user_rolls_back_on_database_error(conn):
    users_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    credentials_before = conn.execute(
        "SELECT COUNT(*) FROM user_credentials"
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.CheckViolation):
        create_user(
            conn,
            "invalid-level@example.com",
            "correct-horse-1",
            date(1990, 1, 1),
            fitness_level="expert",
            goal="general_exercise",
            diet_type="veg",
            today=date(2026, 11, 21),
        )

    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == users_before
    assert (
        conn.execute("SELECT COUNT(*) FROM user_credentials").fetchone()[0]
        == credentials_before
    )
    assert conn.execute("SELECT 1").fetchone() == (1,)


# Authentication normalizes email and rejects incorrect or unknown credentials.
def test_authenticate(conn):
    user_id = make_user(conn, email="a@example.com")

    assert authenticate(conn, "a@example.com", "correct-horse-1") == user_id
    assert authenticate(conn, "A@EXAMPLE.COM", "correct-horse-1") == user_id
    assert authenticate(conn, "a@example.com", "wrong-password") is None
    assert authenticate(conn, "missing@example.com", "correct-horse-1") is None


# Access tokens decode to the user ID that was signed into the subject.
def test_access_token_round_trip():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


# Access tokens past their expiry are rejected.
def test_expired_access_token_is_rejected():
    with pytest.raises(ValueError):
        decode_access_token(create_access_token(42, expires_minutes=-1))


# Access tokens with a modified signature are rejected.
def test_tampered_access_token_is_rejected():
    token = create_access_token(42)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    final_index = alphabet.index(token[-1])
    tampered_token = token[:-1] + alphabet[final_index ^ 16]
    with pytest.raises(ValueError):
        decode_access_token(tampered_token)


# Access tokens signed by a different secret are rejected.
def test_wrong_secret_access_token_is_rejected():
    token = create_access_token(42)
    payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
        algorithms=["HS256"],
    )
    wrong_secret_token = jwt.encode(
        payload,
        "different-secret-that-is-not-the-configured-secret",
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_access_token(wrong_secret_token)


# Access tokens without an expiration claim are rejected.
def test_access_token_without_exp_is_rejected():
    missing_exp_token = jwt.encode({"sub": "42"}, JWT_SECRET, algorithm="HS256")
    with pytest.raises(ValueError):
        decode_access_token(missing_exp_token)


# Access tokens using the unsigned "none" algorithm are rejected.
def test_none_algorithm_access_token_is_rejected():
    token = create_access_token(42)
    payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
        algorithms=["HS256"],
    )
    unsigned_token = jwt.encode(payload, "", algorithm="none")
    with pytest.raises(ValueError):
        decode_access_token(unsigned_token)


# Malformed tokens or invalid subject claims are rejected.
@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-token",
        jwt.encode(
            {"exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
            JWT_SECRET,
            algorithm="HS256",
        ),
        jwt.encode(
            {"sub": "abc", "exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
            JWT_SECRET,
            algorithm="HS256",
        ),
        jwt.encode(
            {"sub": 42, "exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
            JWT_SECRET,
            algorithm="HS256",
        ),
    ],
)
def test_decode_rejects_malformed_tokens(token):
    with pytest.raises(ValueError):
        decode_access_token(token)
