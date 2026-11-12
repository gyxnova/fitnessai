from db import get_connection

def safe_exercises(conn, user_id, goal=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.exercise_id, e.exercise
            FROM exercises e
            JOIN users u ON u.user_id = %s
            JOIN exercise_goals g ON g.exercise_id = e.exercise_id AND g.goal = COALESCE(%s::text, u.goal)
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
            """,
            (user_id, goal)
        )
        result = cur.fetchall()
        
        return result

if __name__ == "__main__":
    conn = get_connection()
    print(safe_exercises(conn, 1))
    print(safe_exercises(conn, 2))
    print(safe_exercises(conn, 3))
    conn.close()