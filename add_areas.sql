CREATE TABLE exercise_areas (
    exercise_id  INTEGER NOT NULL REFERENCES exercises (exercise_id) ON DELETE CASCADE,
    area         TEXT NOT NULL
        CHECK (area IN ('legs', 'chest', 'back', 'shoulders', 'arms', 'core')),
    PRIMARY KEY (exercise_id, area)
);