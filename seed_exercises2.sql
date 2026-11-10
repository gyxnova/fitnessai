-- seed_exercises2.sql: back exercises. Run after seed_areas.sql.

INSERT INTO exercises (exercise, fitness_level, default_minutes) VALUES
  ('Reverse snow angels',   'beginner',     10),
  ('Resistance band rows',  'intermediate', 15);

INSERT INTO exercise_goals (exercise_id, goal)
SELECT exercise_id, goal FROM exercises
JOIN (VALUES
  ('Reverse snow angels',  'general_exercise'),
  ('Reverse snow angels',  'lose_weight'),
  ('Resistance band rows', 'gain_weight'),
  ('Resistance band rows', 'general_exercise')
) AS g(name, goal) ON exercises.exercise = g.name;

INSERT INTO exercise_equipment (exercise_id, equipment)
SELECT exercise_id, equipment FROM exercises
JOIN (VALUES
  ('Reverse snow angels',  'none'),
  ('Resistance band rows', 'resistance band')
) AS e(name, equipment) ON exercises.exercise = e.name;

INSERT INTO exercise_areas (exercise_id, area)
SELECT exercise_id, area FROM exercises
JOIN (VALUES
  ('Reverse snow angels',  'back'),
  ('Reverse snow angels',  'shoulders'),
  ('Resistance band rows', 'back'),
  ('Resistance band rows', 'arms')
) AS a(name, area) ON exercises.exercise = a.name;