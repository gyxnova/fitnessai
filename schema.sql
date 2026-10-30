-- FitnessAI v1 schema (PostgreSQL)
-- Translated from the ER diagram. The columns on session_exercises and
-- exercises (plus exercise_goals) are starting proposals: review them and
-- change anything that does not fit your three v1 targets.

-- Note: "user" is a reserved word in PostgreSQL, so the table is named "users".

CREATE TABLE avatars (
    avatar_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    avatar_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE users (
    user_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    avatar_id      INTEGER REFERENCES avatars (avatar_id),
    -- Store date of birth, not age. The 18+ check is enforced in application
    -- code at signup (also keep a test for it).
    date_of_birth  DATE NOT NULL,
    fitness_level  TEXT NOT NULL
        CHECK (fitness_level IN ('beginner', 'intermediate', 'advanced')),
    goal           TEXT NOT NULL
        CHECK (goal IN ('lose_weight', 'gain_weight', 'general_exercise')),
    diet_type      TEXT NOT NULL
        CHECK (diet_type IN ('veg', 'non_veg'))
);

-- One row per allergen per user (many allergies per user).
CREATE TABLE user_allergies (
    user_id   INTEGER NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    allergen  TEXT NOT NULL,
    PRIMARY KEY (user_id, allergen)
);

-- One row per piece of equipment a user has.
CREATE TABLE user_equipments (
    user_id    INTEGER NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    equipment  TEXT NOT NULL,
    PRIMARY KEY (user_id, equipment)
);

CREATE TABLE exercises (
    exercise_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exercise       TEXT NOT NULL,
    fitness_level  TEXT NOT NULL
        CHECK (fitness_level IN ('beginner', 'intermediate', 'advanced')),
    -- Default time for this exercise; "shorter session" scales from this.
    default_minutes  INTEGER NOT NULL CHECK (default_minutes > 0)
);

-- Goals an exercise suits (many goals per exercise). The recommender matches
-- these against users.goal, together with fitness level and equipment.
CREATE TABLE exercise_goals (
    exercise_id  INTEGER NOT NULL REFERENCES exercises (exercise_id) ON DELETE CASCADE,
    goal         TEXT NOT NULL
        CHECK (goal IN ('lose_weight', 'gain_weight', 'general_exercise')),
    PRIMARY KEY (exercise_id, goal)
);

-- Equipment an exercise needs (compared against user_equipments by the filter).
CREATE TABLE exercise_equipment (
    exercise_id  INTEGER NOT NULL REFERENCES exercises (exercise_id) ON DELETE CASCADE,
    equipment    TEXT NOT NULL,
    PRIMARY KEY (exercise_id, equipment)
);

CREATE TABLE workout_sessions (
    session_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    planned_date  DATE NOT NULL,
    completed_at  DATE,  -- stays NULL until the session is completed
    status        TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'completed', 'missed')),
    duration      INTEGER CHECK (duration > 0)  -- minutes
);

-- Speeds up the missed-workout check (find a user's recent sessions by date).
CREATE INDEX idx_workout_sessions_user_date
    ON workout_sessions (user_id, planned_date);

-- Link table: a session has many exercises, an exercise appears in many sessions.
CREATE TABLE session_exercises (
    session_id   INTEGER NOT NULL REFERENCES workout_sessions (session_id) ON DELETE CASCADE,
    exercise_id  INTEGER NOT NULL REFERENCES exercises (exercise_id),
    position         INTEGER NOT NULL CHECK (position > 0),  -- order within the session
    planned_minutes  INTEGER NOT NULL CHECK (planned_minutes > 0),  -- lowered for a shorter session
    completed        BOOLEAN NOT NULL DEFAULT FALSE,  -- per-exercise completion
    PRIMARY KEY (session_id, exercise_id)
);

CREATE TABLE recipes (
    recipe_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dish_name  TEXT NOT NULL,
    diet_type  TEXT NOT NULL
        CHECK (diet_type IN ('veg', 'non_veg')),
    cost       INTEGER CHECK (cost >= 0),
    steps      TEXT NOT NULL
);

-- One row per allergen contained in a recipe. The allergy filter excludes any
-- recipe that has a row matching one of the user's rows in user_allergies.
CREATE TABLE recipe_allergens (
    recipe_id  INTEGER NOT NULL REFERENCES recipes (recipe_id) ON DELETE CASCADE,
    allergen   TEXT NOT NULL,
    PRIMARY KEY (recipe_id, allergen)
);
