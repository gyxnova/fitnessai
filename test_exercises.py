import pytest
from exercises import safe_exercises

LEVEL_RANK = {"beginner": 1, "intermediate": 2, "advanced": 3}


def names_for(conn, user_id):
    return sorted(name for _id, name in safe_exercises(conn, user_id))


# ---- Rule tests: stay valid however much the seed data grows ----

@pytest.mark.parametrize("user_id", [1, 2, 3, 4])
def test_every_exercise_follows_the_rules(conn, user_id):
    level, goal = conn.execute(
        "SELECT fitness_level, goal FROM users WHERE user_id = %s", (user_id,)
    ).fetchone()
    owned = {
        e for (e,) in conn.execute(
            "SELECT equipment FROM user_equipments WHERE user_id = %s", (user_id,)
        ).fetchall()
    }

    result = safe_exercises(conn, user_id)
    assert result, "each test user should get at least one exercise"

    for exercise_id, name in result:
        ex_level = conn.execute(
            "SELECT fitness_level FROM exercises WHERE exercise_id = %s", (exercise_id,)
        ).fetchone()[0]
        goals = {
            g for (g,) in conn.execute(
                "SELECT goal FROM exercise_goals WHERE exercise_id = %s", (exercise_id,)
            ).fetchall()
        }
        needs = {
            e for (e,) in conn.execute(
                "SELECT equipment FROM exercise_equipment WHERE exercise_id = %s", (exercise_id,)
            ).fetchall()
        } - {"none"}

        assert LEVEL_RANK[ex_level] <= LEVEL_RANK[level], f"{name} is too hard"
        assert goal in goals, f"{name} does not match the goal"
        assert needs <= owned, f"{name} needs equipment the user lacks"


# ---- Specific cases: a few names we are sure about ----

def test_user_1_intermediate_lose_weight_no_equipment(conn):
    names = names_for(conn, 1)
    assert "Jumping jacks" in names          # beginner exercises are allowed
    assert "Step-ups" in names               # intermediate is allowed
    assert "Burpees" not in names            # advanced is too hard
    assert "Goblet squat" not in names       # needs dumbbells


def test_user_2_beginner_with_dumbbells(conn):
    names = names_for(conn, 2)
    assert "Light dumbbell curls" in names   # dumbbells unlock this
    assert "Wall push-ups" in names
    assert "Push-ups" not in names           # intermediate


def test_user_3_same_as_user_2_but_no_equipment(conn):
    names = names_for(conn, 3)
    assert "Wall push-ups" in names
    assert "Light dumbbell curls" not in names
    # owning dumbbells can only ever add exercises
    assert set(names) <= set(names_for(conn, 2))
    assert "Light dumbbell curls" in set(names_for(conn, 2)) - set(names)


def test_user_4_advanced_gets_all_levels(conn):
    names = names_for(conn, 4)
    assert "Barbell deadlift" in names       # advanced
    assert "Push-ups" in names               # intermediate
    assert "Squats" in names                 # beginner
    assert "Band pull-apart" not in names    # needs a band, user 4 has none


def test_unknown_user_gets_no_exercises(conn):
    assert safe_exercises(conn, 999) == []