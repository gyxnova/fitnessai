SELECT e.exercise_id, e.exercise
FROM exercises e
JOIN users u ON u.user_id = 999
JOIN exercise_goals g ON g.exercise_id = e.exercise_id AND g.goal = u.goal
WHERE CASE e.fitness_level WHEN 'beginner' THEN 1 WHEN 'intermediate' THEN 2 WHEN 'advanced' THEN 3 END
   <= CASE u.fitness_level WHEN 'beginner' THEN 1 WHEN 'intermediate' THEN 2 WHEN 'advanced' THEN 3 END
    AND NOT EXISTS (
    SELECT 1
    FROM exercise_equipment ee
    WHERE ee.exercise_id = e.exercise_id
      AND ee.equipment <> 'none'
      AND ee.equipment NOT IN (
        SELECT ue.equipment
        FROM user_equipments ue
        WHERE ue.user_id = u.user_id
      )
);