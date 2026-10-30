from db import get_connection

def safe_recipes(conn,user_id):
    with conn.cursor() as cur:
        cur.execute(
            """
        SELECT recipes.recipe_id, recipes.dish_name 
        FROM recipes,users
        WHERE users.user_id = %s AND users.diet_type = recipes.diet_type
        AND NOT EXISTS (
            SELECT 1
            FROM user_allergies ua
            WHERE ua.user_id = users.user_id AND ua.allergen IN (
                SELECT ra.allergen
                FROM recipe_allergens ra
                WHERE ra.recipe_id = recipes.recipe_id
            )
        );
            """,
            (user_id,)
        )
        result = cur.fetchall()
        
        return result

if __name__ == "__main__":
    conn = get_connection()
    print(safe_recipes(conn, 1))
    print(safe_recipes(conn, 2))
    conn.close()

