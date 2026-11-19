-- seed_exercises.sql
-- Convention: every exercise has at least one equipment row;
-- 'none' means no equipment needed.

INSERT INTO exercises (exercise, fitness_level, default_minutes) VALUES
  ('Wall push-ups',        'beginner',     10),
  ('Push-ups',             'intermediate', 15),
  ('Jumping jacks',        'beginner',     10),
  ('Squats',               'beginner',     15),
  ('Light dumbbell curls', 'beginner',     10),
  ('Dumbbell curls',       'intermediate', 15),
  ('Mat plank',            'intermediate', 10),
  ('Burpees',              'advanced',     20);

INSERT INTO exercise_goals (exercise_id, goal)
SELECT exercise_id, goal FROM exercises
JOIN (VALUES
  ('Wall push-ups',        'general_exercise'),
  ('Push-ups',             'gain_weight'),
  ('Push-ups',             'general_exercise'),
  ('Jumping jacks',        'lose_weight'),
  ('Jumping jacks',        'general_exercise'),
  ('Squats',               'lose_weight'),
  ('Squats',               'gain_weight'),
  ('Light dumbbell curls', 'general_exercise'),
  ('Dumbbell curls',       'gain_weight'),
  ('Mat plank',            'general_exercise'),
  ('Burpees',              'lose_weight')
) AS g(name, goal) ON exercises.exercise = g.name;

INSERT INTO exercise_equipment (exercise_id, equipment)
SELECT exercise_id, equipment FROM exercises
JOIN (VALUES
  ('Wall push-ups',        'none'),
  ('Push-ups',             'none'),
  ('Jumping jacks',        'none'),
  ('Squats',               'none'),
  ('Light dumbbell curls', 'dumbbells'),
  ('Dumbbell curls',       'dumbbells'),
  ('Mat plank',            'mat'),
  ('Burpees',              'none')
) AS e(name, equipment) ON exercises.exercise = e.name;