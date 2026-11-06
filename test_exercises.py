from exercises import safe_exercises

def test_user_1_gets_safe_exercises(conn):
    result = safe_exercises(conn, 1)
    names = sorted(name for _id, name in result)
    assert names == [ "Jumping jacks", "Squats"] #"Burpees" is never in user 1’s results 

def test_user_2_gets_safe_exercises(conn):
    result = safe_exercises(conn, 2)
    names = sorted(name for _id, name in result)
    assert names == ["Jumping jacks", "Light dumbbell curls", "Wall push-ups"]

def test_user_3_gets_safe_exercises(conn):
    result = safe_exercises(conn, 3)
    names = sorted(name for _id, name in result)
    assert names == ["Jumping jacks", "Wall push-ups"]  

def test_unknown_user_gets_no_exercises(conn):
    assert safe_exercises(conn, 999) == []