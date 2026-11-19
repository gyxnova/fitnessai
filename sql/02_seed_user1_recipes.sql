-- Tiny test data for the allergy-filter slice.
-- Run after schema.sql: psql -U postgres -d fitnessai -f seed.sql

INSERT INTO avatars (avatar_name) VALUES ('Avatar 1'), ('Avatar 2');

-- User 1: vegetarian, allergic to peanut.
INSERT INTO users (avatar_id, date_of_birth, fitness_level, goal, diet_type)
VALUES (1, '1995-05-10', 'intermediate', 'lose_weight', 'veg');

INSERT INTO user_allergies (user_id, allergen) VALUES (1, 'peanut');

INSERT INTO recipes (dish_name, diet_type, cost, steps) VALUES
    ('Poha',                      'veg',     40,  'Soak poha, fry with onion and spices.'),
    ('Peanut chutney sandwich',   'veg',     50,  'Spread peanut chutney on bread.'),
    ('Paneer bhurji',             'veg',     90,  'Crumble paneer and cook with spices.'),
    ('Chicken curry',             'non_veg', 150, 'Cook chicken in a spiced gravy.');

-- Recipes 2 and 3 contain allergens; 1 and 4 contain none listed.
INSERT INTO recipe_allergens (recipe_id, allergen) VALUES
    (2, 'peanut'),
    (3, 'milk');
