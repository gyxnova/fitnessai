CREATE TABLE session_versions (
    session_id  INTEGER NOT NULL REFERENCES workout_sessions (session_id) ON DELETE CASCADE,
    version     INTEGER NOT NULL CHECK (version > 0),
    saved_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    exercises   JSONB NOT NULL,
    PRIMARY KEY (session_id, version)
);