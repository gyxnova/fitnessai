-- seed4.sql: user 4, advanced, owns dumbbells and a barbell.
INSERT INTO users (avatar_id, date_of_birth, fitness_level, goal, diet_type)
VALUES (1, '1992-01-20', 'advanced', 'gain_weight', 'veg');

INSERT INTO user_equipments (user_id, equipment)
VALUES (4, 'dumbbells'), (4, 'barbell');