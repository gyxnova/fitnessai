-- seed_exercises3.sql: additional leg and strength exercises. Run after seed_areas.sql.

INSERT INTO exercises (exercise, fitness_level, default_minutes) VALUES
  ('Bulgarian split squat', 'advanced',     20),
  ('Barbell deadlift',      'advanced',     20),
  ('Dumbbell overhead press', 'advanced',    15),
  ('Pike push-up',          'intermediate', 15),
  ('Step-ups',              'intermediate', 15),
  ('Glute bridge',          'intermediate', 15);

INSERT INTO exercise_goals (exercise_id, goal)
SELECT exercise_id, goal FROM exercises
JOIN (VALUES
  ('Bulgarian split squat', 'lose_weight'),
  ('Bulgarian split squat', 'general_exercise'),
  ('Barbell deadlift',      'gain_weight'),
  ('Barbell deadlift',      'general_exercise'),
  ('Dumbbell overhead press', 'gain_weight'),
  ('Pike push-up',          'general_exercise'),
  ('Step-ups',              'lose_weight'),
  ('Glute bridge',          'lose_weight')
) AS g(name, goal) ON exercises.exercise = g.name;

INSERT INTO exercise_equipment (exercise_id, equipment)
SELECT exercise_id, equipment FROM exercises
JOIN (VALUES
  ('Bulgarian split squat', 'dumbbells'),
  ('Barbell deadlift',      'barbell'),
  ('Dumbbell overhead press', 'dumbbells'),
  ('Pike push-up',          'none'),
  ('Step-ups',              'none'),
  ('Glute bridge',          'mat')
) AS e(name, equipment) ON exercises.exercise = e.name;

INSERT INTO exercise_areas (exercise_id, area)
SELECT exercise_id, area FROM exercises
JOIN (VALUES
  ('Bulgarian split squat', 'legs'),
  ('Bulgarian split squat', 'core'),
  ('Barbell deadlift',      'legs'),
  ('Barbell deadlift',      'back'),
  ('Dumbbell overhead press', 'shoulders'),
  ('Dumbbell overhead press', 'arms'),
  ('Pike push-up',          'shoulders'),
  ('Pike push-up',          'chest'),
  ('Step-ups',              'legs'),
  ('Glute bridge',          'legs'),
  ('Glute bridge',          'core')
) AS a(name, area) ON exercises.exercise = a.name;
