SELECT recipes.* 
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