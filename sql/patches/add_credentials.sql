CREATE TABLE user_credentials(
    user_id  INTEGER NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    email    TEXT NOT NULL UNIQUE,CHECK (email = lower(email)),
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id)
);