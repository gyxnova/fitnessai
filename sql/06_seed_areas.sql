-- seed_areas.sql
-- Body-area tags per exercise. Run after seed_exercises.sql.

INSERT INTO exercise_areas (exercise_id, area)
SELECT exercise_id, area FROM exercises
JOIN (VALUES
  ('Wall push-ups',        'chest'),
  ('Wall push-ups',        'arms'),
  ('Push-ups',             'chest'),
  ('Push-ups',             'arms'),
  ('Push-ups',             'core'),
  ('Jumping jacks',        'legs'),
  ('Jumping jacks',        'shoulders'),
  ('Squats',               'legs'),
  ('Squats',               'core'),
  ('Light dumbbell curls', 'arms'),
  ('Dumbbell curls',       'arms'),
  ('Mat plank',            'core'),
  ('Mat plank',            'shoulders'),
  ('Burpees',              'legs'),
  ('Burpees',              'chest'),
  ('Burpees',              'core')
) AS a(name, area) ON exercises.exercise = a.name;